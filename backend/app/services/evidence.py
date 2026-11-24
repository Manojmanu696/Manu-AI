"""Shared rules for active personal data and auditable user changes."""
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import text

from ..models import LocalAIRecord, MediaItem, Memory
from .local_ai_records import add_record

EXPLICIT_SOURCES = {"user", "approved"}
FRESH_EXCLUSIONS = {"completed", "dropped", "current"}


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def lock_writes(db):
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))


def personal_media(db):
    return db.query(MediaItem).filter_by(is_demo=False)


def personal_memories(db):
    return db.query(Memory).filter_by(is_demo=False)


def normalized(value):
    return " ".join(value.casefold().replace("’", "'").split())


def field(row, name):
    return row.get(name) if isinstance(row, dict) else getattr(row, name)


def external_key(row):
    external_id = (field(row, "external_id") or "").strip().lower()
    kind = field(row, "media_type")
    if match := re.fullmatch(r"tvmaze:(?:tv:)?(\d+)", external_id):
        return ("tvmaze", match[1])
    if match := re.fullmatch(r"tmdb:(?:(movie|tv):)?(\d+)", external_id):
        if match[1] or kind != "anime":
            return ("tmdb", match[1] or kind, match[2])
    if match := re.fullmatch(r"anilist:(anime|manga):(\d+)", external_id):
        return ("anilist", match[1], match[2])
    if match := re.fullmatch(r"imdb:(tt\d+)", external_id):
        return ("imdb", match[1])
    return (kind, external_id) if external_id else None


def same_work(first, second):
    first_id, second_id = external_key(first), external_key(second)
    if first_id and first_id == second_id:
        return True
    if first_id and second_id and first_id[0] == second_id[0]:
        return False
    year = field(first, "release_year")
    return (year is not None and year == field(second, "release_year")
            and field(first, "media_type") == field(second, "media_type")
            and normalized(field(first, "title")) == normalized(field(second, "title")))


def media_ref(item):
    return {key: getattr(item, key) for key in ("id", "media_type", "title", "release_year", "external_id")}


def change_rating(db, item, score, source, *, reason=""):
    if item.id is None:
        db.flush()
    previous = item.personal_rating
    if previous != score or reason:
        add_record(db, "rating_revision", {
            "media": media_ref(item), "source": source, "precision": "exact", "scale": 10,
            "previous": previous, "score": score, "unrated": score is None, "reason": reason,
        })
        item.personal_rating = score


def change_status(db, item, status, source):
    if item.id is None:
        db.flush()
    if item.status == status and (status != "completed" or item.date_completed):
        return
    previous = item.status
    item.status = status
    item.date_completed = now() if status == "completed" else None
    add_record(db, "status_revision", {
        "media": media_ref(item), "previous": previous, "status": status, "source": source,
        "completed_at": item.date_completed.isoformat() if item.date_completed else None,
    })


def flag_review(db, subject, details):
    existing = db.query(LocalAIRecord).filter(
        LocalAIRecord.kind == "data_review", LocalAIRecord.data["subject"].as_string() == subject,
    ).first()
    if not existing:
        add_record(db, "data_review", {"subject": subject, **details})


def save_memory(db, values, replace_id=None):
    previous = personal_memories(db).filter_by(id=replace_id).first() if replace_id is not None else None
    if replace_id is not None and previous is None:
        raise HTTPException(404, "Memory not found")
    category, content = (" ".join(values[key].split()) for key in ("category", "content"))
    for row in personal_memories(db):
        if row is not previous and normalized(row.category) == normalized(category) and normalized(row.content) == normalized(content):
            if previous:
                raise HTTPException(409, "That memory already exists.")
            if values["source"] in EXPLICIT_SOURCES and row.source not in EXPLICIT_SOURCES:
                return save_memory(db, values, row.id)
            return row
    if not previous:
        statement = re.fullmatch(r"(?:i )?(prefer|like|avoid|dislike) (.+?)[.!]?", normalized(content))
        if statement and values["source"] in EXPLICIT_SOURCES:
            for row in personal_memories(db):
                other = re.fullmatch(r"(?:i )?(prefer|like|avoid|dislike) (.+?)[.!]?", normalized(row.content))
                if (row.source in EXPLICIT_SOURCES and other and other[2] == statement[2]
                    and (other[1] in {"prefer", "like"}) != (statement[1] in {"prefer", "like"})):
                    flag_review(db, f"memory-conflict:{row.id}:{statement[2]}", {
                        "reason": "Two explicit memories disagree. Use a revision to resolve the conflict.",
                        "current": row.content, "proposed": content,
                    })
                    values = {**values, "source": "inferred", "confidence": None}
                    break
        previous = Memory(category=category, content=content, source=values["source"], confidence=values.get("confidence"))
        db.add(previous)
        return previous
    before = {key: getattr(previous, key) for key in ("category", "content", "source", "confidence")}
    previous.category, previous.content = category, content
    previous.source, previous.confidence = values["source"], values.get("confidence")
    after = {key: getattr(previous, key) for key in before}
    if before != after:
        previous.created_at = now()
        add_record(db, "memory_revision", {"memory_id": previous.id, "previous": before, "current": after})
    return previous


def taste_memories(db):
    rows = personal_memories(db).order_by(Memory.created_at.desc(), Memory.id.desc()).all()
    rows.sort(key=lambda row: 0 if row.source in EXPLICIT_SOURCES else 1 if row.source == "chatgpt_import" else 2)
    administrative = {"demo_data_removal", "completion_verification", "confidence_criteria", "technical_&_strategic_interest"}
    seen = set()
    result = []
    for row in rows:
        key = normalized(row.content)
        category = normalized(row.category).replace(" ", "_")
        if key not in seen and category not in administrative:
            seen.add(key)
            result.append(row)
    return result
