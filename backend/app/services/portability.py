import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session
from ..models import MediaItem, Memory
from ..config import BACKUP_DIR, DATA_DIR

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
    return {
        "format": "manu-ai-portable-data", "version": PORTABLE_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "media_items": [serialize_media(item) for item in db.query(MediaItem).all()],
        "memories": [serialize_memory(memory) for memory in db.query(Memory).all()],
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
    for raw in payload.get("media_items", []):
        values = {key: raw.get(key) for key in ("media_type","title","description","genres","personal_rating","sentiment","status","notes","tags","runtime","release_year","external_id","external_url","image_url","ai_metadata","is_demo")}
        values["date_added"] = _parse_date(raw.get("date_added")) or datetime.now(timezone.utc).replace(tzinfo=None)
        values["date_completed"] = _parse_date(raw.get("date_completed"))
        db.add(MediaItem(**values))
    for raw in payload.get("memories", []):
        values = {key: raw.get(key) for key in ("category","content","source","confidence","is_demo")}
        values["created_at"] = _parse_date(raw.get("created_at")) or datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(Memory(**values))
    db.commit()


def db_size():
    db_file = DATA_DIR / "manu_ai.db"
    return db_file.stat().st_size if db_file.exists() else 0
