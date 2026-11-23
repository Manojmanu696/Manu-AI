from datetime import datetime, timezone
from uuid import uuid4

from ..models import LocalAIRecord


def add_record(db, kind, data):
    record = LocalAIRecord(
        id=str(uuid4()), kind=kind,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None), data=data,
    )
    db.add(record)
    return record


def serialize_record(record):
    return {
        "id": record.id, "kind": record.kind,
        "created_at": record.created_at.isoformat() + "Z", "data": record.data,
    }
