import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session
from ..models import CatalogueItem, MediaItem, Memory, RecommendationFeedback, TasteSignal
from ..config import BACKUP_DIR, DATA_DIR

PORTABLE_VERSION = "1.1"


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


def serialize_taste_signal(signal: TasteSignal):
    return {"id": signal.id, "dimension": signal.dimension, "value": signal.value, "direction": signal.direction,
            "strength": signal.strength, "confidence": signal.confidence, "source": signal.source, "evidence": signal.evidence,
            "confirmed_at": signal.confirmed_at.isoformat() if signal.confirmed_at else None,
            "created_at": signal.created_at.isoformat()}


def serialize_feedback(event: RecommendationFeedback):
    return {"id": event.id, "catalogue_item_id": event.catalogue_item_id, "action": event.action, "reason": event.reason,
            "context": event.context, "rating": event.rating, "undone": event.undone,
            "library_item_id": event.library_item_id, "library_item_created": event.library_item_created,
            "previous_library_state_json": event.previous_library_state_json, "taste_signal_id": event.taste_signal_id,
            "created_at": event.created_at.isoformat()}


def serialize_catalogue_item(item: CatalogueItem):
    return {column.name: getattr(item, column.name) for column in CatalogueItem.__table__.columns if column.name not in {"created_at", "is_demo"}} | {"id": item.id}


def export_payload(db: Session):
    feedback = db.query(RecommendationFeedback).all()
    catalogue_ids = {event.catalogue_item_id for event in feedback}
    catalogue = db.query(CatalogueItem).filter(CatalogueItem.id.in_(catalogue_ids)).all() if catalogue_ids else []
    return {
        "format": "manu-ai-portable-data", "version": PORTABLE_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "media_items": [serialize_media(item) for item in db.query(MediaItem).all()],
        "memories": [serialize_memory(memory) for memory in db.query(Memory).all()],
        "taste_signals": [serialize_taste_signal(signal) for signal in db.query(TasteSignal).all()],
        "catalogue_items": [serialize_catalogue_item(item) for item in catalogue],
        "feedback_events": [serialize_feedback(event) for event in feedback],
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
        archive.writestr("README.txt", "Manu AI portable backup v1.1. Import this ZIP with Manu AI's Data page.\n")
    return path


def _parse_date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None) if value else None


def restore_payload(db: Session, payload: dict, replace: bool = False):
    if payload.get("format") != "manu-ai-portable-data":
        raise ValueError("This does not look like a Manu AI portable backup.")
    if replace:
        db.query(RecommendationFeedback).delete()
        db.query(TasteSignal).delete()
        db.query(MediaItem).delete()
        db.query(Memory).delete()
    media_ids = {}
    for raw in payload.get("media_items", []):
        values = {key: raw.get(key) for key in ("media_type","title","description","genres","personal_rating","sentiment","status","notes","tags","runtime","release_year","external_id","external_url","image_url","ai_metadata","is_demo")}
        values["date_added"] = _parse_date(raw.get("date_added")) or datetime.now(timezone.utc).replace(tzinfo=None)
        values["date_completed"] = _parse_date(raw.get("date_completed"))
        item = MediaItem(**values)
        db.add(item); db.flush()
        if raw.get("id") is not None:
            media_ids[raw["id"]] = item.id
    for raw in payload.get("memories", []):
        values = {key: raw.get(key) for key in ("category","content","source","confidence","is_demo")}
        values["created_at"] = _parse_date(raw.get("created_at")) or datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(Memory(**values))
    db.flush()
    signal_ids = {}
    for raw in payload.get("taste_signals", []):
        values = {key: raw.get(key) for key in ("dimension", "value", "direction", "strength", "confidence", "source", "evidence")}
        values["confirmed_at"] = _parse_date(raw.get("confirmed_at"))
        values["created_at"] = _parse_date(raw.get("created_at")) or datetime.now(timezone.utc).replace(tzinfo=None)
        signal = TasteSignal(**values); db.add(signal); db.flush()
        if raw.get("id") is not None:
            signal_ids[raw["id"]] = signal.id
    catalogue_ids = {}
    allowed_catalogue_fields = {column.name for column in CatalogueItem.__table__.columns} - {"id", "created_at", "is_demo"}
    for raw in payload.get("catalogue_items", []):
        provider, provider_id = raw.get("source_provider", "local"), raw.get("provider_id")
        existing = db.query(CatalogueItem).filter_by(source_provider=provider, provider_id=provider_id).first() if provider_id else None
        values = {key: value for key, value in raw.items() if key in allowed_catalogue_fields}
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            item = existing
        else:
            item = CatalogueItem(**values); db.add(item)
        db.flush()
        if raw.get("id") is not None:
            catalogue_ids[raw["id"]] = item.id
    for raw in payload.get("feedback_events", []):
        catalogue_id = catalogue_ids.get(raw.get("catalogue_item_id"))
        if catalogue_id is None:
            continue
        values = {key: raw.get(key) for key in ("action", "reason", "context", "rating", "undone", "library_item_created", "previous_library_state_json")}
        values["catalogue_item_id"] = catalogue_id
        values["library_item_id"] = media_ids.get(raw.get("library_item_id"))
        values["taste_signal_id"] = signal_ids.get(raw.get("taste_signal_id"))
        values["created_at"] = _parse_date(raw.get("created_at")) or datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(RecommendationFeedback(**values))
    db.commit()


def db_size():
    db_file = DATA_DIR / "manu_ai.db"
    return db_file.stat().st_size if db_file.exists() else 0
