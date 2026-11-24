import csv
import io
import json
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from ..models import CatalogueItem, FilmReview, LocalAIRecord, MediaItem, Memory, RecommendationFeedback, ResearchSource, ViewingCheckpoint
from ..config import BACKUP_DIR, DATA_DIR
from .local_ai_records import add_record, serialize_record
from .rating_feedback import record_feedback
from .evidence import flag_review, media_ref, normalized, now, same_work
from ..schemas import CheckpointCreate, MediaCreate, MemoryCreate, ReviewCreate

PORTABLE_VERSION = "1.1"
EVENT_KINDS = {"chat", "assistant_chat", "prediction", "preference", "rating_revision", "status_revision",
               "memory_revision", "data_review", "recommendation_shown"}


def serialize_media(item: MediaItem):
    return {
        "id": item.id, "media_type": item.media_type, "title": item.title,
        "description": item.description, "genres": item.genres, "personal_rating": item.personal_rating,
        "sentiment": item.sentiment, "status": item.status, "notes": item.notes, "tags": item.tags,
        "runtime": item.runtime, "release_year": item.release_year, "external_id": item.external_id,
        "external_url": item.external_url, "image_url": item.image_url, "ai_metadata": item.ai_metadata,
        "is_demo": item.is_demo, "date_added": item.date_added.isoformat(),
        "date_completed": item.date_completed.isoformat() if item.date_completed else None,
    }


def serialize_memory(memory: Memory):
    return {"id": memory.id, "category": memory.category, "content": memory.content,
            "source": memory.source, "confidence": memory.confidence, "is_demo": memory.is_demo,
            "created_at": memory.created_at.isoformat()}


def export_payload(db: Session):
    records = db.query(LocalAIRecord).order_by(LocalAIRecord.created_at, LocalAIRecord.id).all()
    return {
        "format": "manu-ai-portable-data", "version": PORTABLE_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "media_items": [serialize_media(item) for item in db.query(MediaItem).all()],
        "memories": [serialize_memory(memory) for memory in db.query(Memory).all()],
        "local_ai_records": [serialize_record(record) for record in records],
        "rating_feedback_history": [
            {"chat_id": record.id, "created_at": serialize_record(record)["created_at"], **rating}
            for record in records if (rating := record_feedback(record))
        ],
        "viewing_checkpoints": [
            {**row.details, "id": row.id, "media_item_id": row.media_item_id, "viewing_date": row.viewing_date.isoformat()}
            for row in db.query(ViewingCheckpoint).order_by(ViewingCheckpoint.viewing_date, ViewingCheckpoint.id)
        ],
        "film_reviews": [
            {"media_item_id": row.media_item_id, "finalized_at": row.finalized_at.isoformat(),
             "updated_at": row.updated_at.isoformat(), **row.details}
            for row in db.query(FilmReview)
        ],
        "catalogue_items": jsonable_encoder(db.query(CatalogueItem).order_by(CatalogueItem.id).all()),
        "recommendation_feedback": jsonable_encoder(db.query(RecommendationFeedback).order_by(RecommendationFeedback.id).all()),
        "research_sources": jsonable_encoder(db.query(ResearchSource).order_by(ResearchSource.id).all()),
    }


def csv_text(rows: list[dict]):
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(dict.fromkeys(key for row in rows for key in row)))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def build_zip(db: Session) -> Path:
    payload = export_payload(db)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = BACKUP_DIR / f"ManuAI_Backup_{stamp}_{uuid4().hex[:8]}.zip"
    path.touch(mode=0o600, exist_ok=False)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manu-ai-data.json", json.dumps(payload, indent=2))
        archive.writestr("media-items.csv", csv_text(payload["media_items"]))
        archive.writestr("memories.csv", csv_text(payload["memories"]))
        archive.writestr("viewing-checkpoints.csv", csv_text(payload["viewing_checkpoints"]))
        archive.writestr("film-reviews.csv", csv_text(payload["film_reviews"]))
        archive.writestr("local-ai-history.json", json.dumps(payload["local_ai_records"], indent=2, ensure_ascii=False))
        archive.writestr("README.txt", "Manu AI portable backup. Import this ZIP with Manu AI's Data page.\n")
    return path


def _parse_date(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


def records(payload, dataset):
    rows = payload.get(dataset, [])
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"Invalid {dataset} dataset.")
    return rows


def restore_payload(db: Session, payload: dict, replace: bool = False):
    if not isinstance(payload, dict) or payload.get("format") != "manu-ai-portable-data":
        raise ValueError("This does not look like a Manu AI portable backup.")
    if replace:
        for model in (ViewingCheckpoint, FilmReview, RecommendationFeedback, ResearchSource,
                      CatalogueItem, MediaItem, Memory, LocalAIRecord):
            db.query(model).delete()
    ai_rows = records(payload, "local_ai_records")
    ai_ids = {value for (value,) in db.query(LocalAIRecord.id)}
    id_map = {}
    conflicts = 0
    added_media = set()
    media = db.query(MediaItem).all()
    for raw in records(payload, "media_items"):
        old_id = raw["id"]
        if type(old_id) is not int or old_id < 1 or old_id in id_map:
            raise ValueError("Missing or duplicate media ID in the backup.")
        incoming_score = raw.get("personal_rating")
        scale = raw.get("rating_scale", 10)
        precision = raw.get("rating_precision", "exact")
        rating_source = raw.get("rating_source", "legacy_import")
        preserve_only = scale != 10 or precision != "exact" or rating_source in {"external", "inferred", "historical"}
        if type(scale) not in (int, float) or not 0 < scale <= 100:
            raise ValueError("Invalid rating scale.")
        if incoming_score is not None and (type(incoming_score) not in (int, float) or not 0 <= incoming_score <= scale):
            raise ValueError("A rating exceeds its original scale.")
        values = MediaCreate.model_validate({
            "status": "unknown", **raw, "personal_rating": None if preserve_only else incoming_score,
        }).model_dump()
        demo = raw.get("is_demo", False)
        if type(demo) is not bool:
            raise ValueError("Invalid media provenance.")
        added = _parse_date(raw.get("date_added")) or now()
        completed = _parse_date(raw.get("date_completed"))
        matches = [item for item in media if item.is_demo == demo and
                   (same_work(item, values) or (item.id == old_id and item.date_added == added
                    and normalized(item.title) == normalized(values["title"]) and item.media_type == values["media_type"]))]
        if len(matches) > 1:
            raise ValueError(f"Multiple existing entries match {values['title']}. Review duplicates before importing.")
        if matches:
            item = matches[0]
            score_conflict = not preserve_only and item.personal_rating != values["personal_rating"]
            if item.status != values["status"] or score_conflict:
                flag_review(db, f"import-media:{item.id}:{added.isoformat()}:{values['status']}:{values['personal_rating']}", {
                    "title": item.title, "reason": "The imported viewing status or rating conflicts with the current library.",
                    "current": serialize_media(item), "imported": raw,
                })
                conflicts += 1
        else:
            item = MediaItem(**values, is_demo=demo, date_added=added, date_completed=completed if values["status"] == "completed" else None)
            if replace:
                item.id = old_id
            db.add(item)
            db.flush()
            media.append(item)
            added_media.add(item.id)
            if not demo and item.status == "completed" and (completed is None or completed < added):
                has_confirmation = any(event.get("kind") == "status_revision"
                                       and event.get("data", {}).get("media", {}).get("id") == old_id
                                       and event["data"].get("status") == "completed" for event in ai_rows)
                if not has_confirmation:
                    flag_review(db, f"import-status:{item.id}:{added.isoformat()}", {
                        "title": item.title, "reason": "Imported completion date is missing or precedes addition.", "imported": raw,
                    })
                    item.status, item.date_completed = "unknown", None
                    conflicts += 1
        if preserve_only and incoming_score is not None and not demo:
            token = f"{item.id}:{added.isoformat()}:{incoming_score}:{scale}:{precision}"
            evidence = db.query(LocalAIRecord).filter(
                LocalAIRecord.kind == "rating_revision", LocalAIRecord.data["import_key"].as_string() == token,
            ).first()
            if evidence is None:
                add_record(db, "rating_revision", {"media": media_ref(item), "source": rating_source,
                           "precision": "historical" if scale != 10 and precision == "exact" else precision,
                           "scale": scale, "score": incoming_score, "import_key": token})
                db.flush()
        id_map[old_id] = item.id

    for raw in records(payload, "viewing_checkpoints"):
        item_id = id_map[raw["media_item_id"]]
        checkpoint = CheckpointCreate.model_validate(raw)
        details = checkpoint.model_dump(exclude={"viewing_date"})
        rows = db.query(ViewingCheckpoint).filter_by(media_item_id=item_id, viewing_date=checkpoint.viewing_date)
        if not any(row.details == details for row in rows):
            row = ViewingCheckpoint(media_item_id=item_id, viewing_date=checkpoint.viewing_date, details=details)
            if replace and type(raw.get("id")) is int:
                row.id = raw["id"]
            db.add(row)
            db.flush()
    for raw in records(payload, "film_reviews"):
        item_id = id_map[raw["media_item_id"]]
        details = ReviewCreate.model_validate(raw).model_dump()
        row = db.get(FilmReview, item_id)
        if row is None:
            db.add(FilmReview(media_item_id=item_id, finalized_at=_parse_date(raw["finalized_at"]),
                              updated_at=_parse_date(raw["updated_at"]), details=details))
        elif row.details != details:
            flag_review(db, f"import-review:{item_id}:{raw['updated_at']}", {
                "title": db.get(MediaItem, item_id).title, "reason": "The imported review differs from the current review.",
                "imported": raw,
            })
            conflicts += 1

    memory_map = {}
    memories = db.query(Memory).all()
    for raw in records(payload, "memories"):
        values = MemoryCreate.model_validate(raw).model_dump()
        demo = raw.get("is_demo", False)
        if type(demo) is not bool:
            raise ValueError("Invalid memory provenance.")
        row = next((memory for memory in memories if memory.is_demo == demo
                    and memory.source == values["source"]
                    and normalized(memory.category) == normalized(values["category"])
                    and normalized(memory.content) == normalized(values["content"])), None)
        if not row:
            row = Memory(**values, is_demo=demo, created_at=_parse_date(raw.get("created_at")) or now())
            if replace and type(raw.get("id")) is int:
                row.id = raw["id"]
            db.add(row)
            db.flush()
            memories.append(row)
        if type(raw.get("id")) is int:
            memory_map[raw["id"]] = row.id

    for raw in ai_rows:
        record_id = str(UUID(raw["id"]))
        timestamp = _parse_date(raw["created_at"])
        kind, data = raw["kind"], dict(raw["data"])
        if not timestamp or kind not in EVENT_KINDS:
            raise ValueError("Invalid local history record.")
        if kind in {"chat", "assistant_chat"} and (data.get("role") not in {"user", "assistant"} or not isinstance(data.get("content"), str)):
            raise ValueError("Invalid chat record.")
        if record_id in ai_ids:
            continue
        if kind in {"rating_revision", "status_revision"} and isinstance(data.get("media"), dict):
            old_id = data["media"].get("id")
            data["media"] = {**data["media"], "id": id_map.get(old_id)}
        if kind == "memory_revision":
            data["memory_id"] = memory_map.get(data.get("memory_id"))
        db.add(LocalAIRecord(id=record_id, kind=kind, created_at=timestamp, data=data))
        ai_ids.add(record_id)

    catalogue_map = {}
    catalogue = db.query(CatalogueItem).all()
    fields = {column.name for column in CatalogueItem.__table__.columns} - {"id"}
    for raw in records(payload, "catalogue_items"):
        old_id = raw["id"]
        values = {key: value for key, value in raw.items() if key in fields}
        if not values.get("title") or values.get("media_type") not in {"movie", "tv", "anime", "game", "book"}:
            raise ValueError("Invalid catalogue entry.")
        demo = raw.get("is_demo", False)
        if type(demo) is not bool:
            raise ValueError("Invalid catalogue provenance.")
        row = next((entry for entry in catalogue if entry.is_demo == demo and same_work(entry, values)), None)
        if not row:
            values.update(created_at=_parse_date(values.get("created_at")) or now(),
                          source_retrieved_at=_parse_date(values.get("source_retrieved_at")))
            row = CatalogueItem(**values)
            if replace:
                row.id = old_id
            db.add(row)
            db.flush()
            catalogue.append(row)
        catalogue_map[old_id] = row.id

    for key, model, time_key, fields in (
        ("recommendation_feedback", RecommendationFeedback, "created_at", ("action",)),
        ("research_sources", ResearchSource, "retrieved_at", ("provider", "query", "title", "url")),
    ):
        for raw in records(payload, key):
            parent = raw.get("catalogue_item_id")
            values = {field: raw[field] for field in fields}
            # Historical imports used "completed" without recording whether a user confirmed it.
            if model is RecommendationFeedback and values["action"] not in {"like", "not_for_me", "watchlist", "watched", "completed"}:
                raise ValueError("Invalid recommendation feedback.")
            values.update(catalogue_item_id=catalogue_map[parent] if parent is not None else None)
            values[time_key] = _parse_date(raw[time_key])
            if not db.query(model).filter_by(**values).first():
                row = model(**values)
                if replace and type(raw.get("id")) is int:
                    row.id = raw["id"]
                db.add(row)
                db.flush()
    db.commit()
    return {"conflicts": conflicts, "media_added": len(added_media)}


def db_size():
    db_file = DATA_DIR / "manu_ai.db"
    return db_file.stat().st_size if db_file.exists() else 0
