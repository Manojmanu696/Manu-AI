import csv
import io
import json
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from ..models import CatalogueItem, FilmReview, LocalAIRecord, MediaItem, Memory, RecommendationFeedback, ResearchSource, ViewingCheckpoint
from ..config import BACKUP_DIR, DATA_DIR
from .local_ai_records import serialize_record
from .rating_feedback import record_feedback

PORTABLE_VERSION = "1.0"


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
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def build_zip(db: Session) -> Path:
    payload = export_payload(db)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = BACKUP_DIR / f"ManuAI_Backup_{stamp}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manu-ai-data.json", json.dumps(payload, indent=2))
        archive.writestr("media-items.csv", csv_text(payload["media_items"]))
        archive.writestr("memories.csv", csv_text(payload["memories"]))
        archive.writestr("viewing-checkpoints.csv", csv_text(payload["viewing_checkpoints"]))
        archive.writestr("film-reviews.csv", csv_text(payload["film_reviews"]))
        archive.writestr("local-ai-history.json", json.dumps(payload["local_ai_records"], indent=2, ensure_ascii=False))
        archive.writestr("README.txt", "Manu AI portable backup v1.0. Import this ZIP with Manu AI's Data page.\n")
    return path


def _parse_date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None) if value else None


def restore_payload(db: Session, payload: dict, replace: bool = False):
    if payload.get("format") != "manu-ai-portable-data":
        raise ValueError("This does not look like a Manu AI portable backup.")
    if replace:
        db.query(MediaItem).delete()
        db.query(Memory).delete()
        db.query(LocalAIRecord).delete()
    ai_ids = {value for (value,) in db.query(LocalAIRecord.id)}
    for record in payload.get("local_ai_records", []):
        try:
            record_id = str(UUID(record["id"]))
            timestamp = _parse_date(record["created_at"])
            kind = record["kind"]
            data = record["data"]
            if timestamp is None or kind not in {"chat", "assistant_chat", "prediction", "preference"} or not isinstance(data, dict):
                raise ValueError()
            if kind in {"chat", "assistant_chat"} and (data.get("role") not in {"user", "assistant"} or not isinstance(data.get("content"), str)):
                raise ValueError()
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ValueError("Invalid local AI record in this backup.") from exc
        if record_id not in ai_ids:
            db.add(LocalAIRecord(id=record_id, kind=kind, created_at=timestamp, data=data))
            ai_ids.add(record_id)
    id_map = {}
    for raw in payload.get("media_items", []):
        values = {key: raw.get(key) for key in ("media_type","title","description","genres","personal_rating","sentiment","status","notes","tags","runtime","release_year","external_id","external_url","image_url","ai_metadata","is_demo")}
        values["date_added"] = _parse_date(raw.get("date_added")) or datetime.now(timezone.utc).replace(tzinfo=None)
        values["date_completed"] = _parse_date(raw.get("date_completed"))
        if replace and type(raw.get("id")) is int and raw["id"] > 0:
            values["id"] = raw["id"]
        item = MediaItem(**values)
        db.add(item)
        id_map[raw.get("id")] = item
    db.flush()
    for raw in payload.get("viewing_checkpoints", []):
        item = id_map.get(raw["media_item_id"])
        if item is not None:
            details = {key: value for key, value in raw.items() if key not in {"id", "media_item_id", "viewing_date"}}
            db.add(ViewingCheckpoint(media_item_id=item.id, viewing_date=date.fromisoformat(raw["viewing_date"]), details=details))
    for raw in payload.get("film_reviews", []):
        item = id_map.get(raw["media_item_id"])
        if item is not None:
            details = {key: value for key, value in raw.items() if key not in {"media_item_id", "finalized_at", "updated_at"}}
            db.add(FilmReview(media_item_id=item.id, finalized_at=_parse_date(raw["finalized_at"]),
                              updated_at=_parse_date(raw["updated_at"]), details=details))
    for raw in payload.get("memories", []):
        values = {key: raw.get(key) for key in ("category","content","source","confidence","is_demo")}
        values["created_at"] = _parse_date(raw.get("created_at")) or datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(Memory(**values))
    db.commit()


def db_size():
    db_file = DATA_DIR / "manu_ai.db"
    return db_file.stat().st_size if db_file.exists() else 0
