"""Local Ollama sentence embeddings for private, content-based ranking."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from ..config import OLLAMA_EMBEDDING_MODEL, OLLAMA_URL
from ..models import CatalogueItem, MediaItem, TasteEmbedding, TasteSignal
from .providers import request_json

log = logging.getLogger(__name__)
_FAILURE_UNTIL = 0.0
_FAILURE_MESSAGE = ""


def _local_endpoint() -> str | None:
    parsed = urlparse(OLLAMA_URL)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return None
    return OLLAMA_URL


def _text(value: str) -> str:
    return " ".join((value or "").split())[:2600]


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _records(db: Session) -> list[tuple[str, str]]:
    records = []
    for item in db.query(CatalogueItem).all():
        text = _text(". ".join(filter(None, [item.title, item.description, item.genres, item.tags, item.story_focus])))
        if text:
            records.append((f"catalogue:{item.id}", text))
    for item in db.query(MediaItem).all():
        text = _text(". ".join(filter(None, [item.title, item.description, item.genres, item.tags])))
        if text:
            records.append((f"media:{item.id}", text))
    for signal in db.query(TasteSignal).filter_by(direction="positive").all():
        text = _text(f"{signal.dimension}: {signal.value}")
        if text:
            records.append((f"signal:{signal.id}", text))
    return records


def embedding_work_pending(db: Session) -> bool:
    if not OLLAMA_EMBEDDING_MODEL or _local_endpoint() is None or time.monotonic() < _FAILURE_UNTIL:
        return False
    records = _records(db)
    if not records:
        return False
    rows = db.query(TasteEmbedding.entity_key, TasteEmbedding.content_hash, TasteEmbedding.model_name).all()
    stored = {row.entity_key: (row.content_hash, row.model_name) for row in rows}
    return any(stored.get(key) != (_digest(value), OLLAMA_EMBEDDING_MODEL) for key, value in records)


def prepare_local_embeddings(db: Session) -> int:
    """Embed only locally stored text; remote Ollama hosts are explicitly rejected."""
    global _FAILURE_UNTIL, _FAILURE_MESSAGE
    endpoint = _local_endpoint()
    if not OLLAMA_EMBEDDING_MODEL or endpoint is None or time.monotonic() < _FAILURE_UNTIL:
        return 0
    records = _records(db)
    if not records:
        return 0
    stored_rows = db.query(TasteEmbedding).all()
    stored = {row.entity_key: row for row in stored_rows}
    pending = [(key, value, _digest(value)) for key, value in records
               if key not in stored or stored[key].content_hash != _digest(value) or stored[key].model_name != OLLAMA_EMBEDDING_MODEL]
    written = 0
    try:
        for start in range(0, len(pending), 32):
            batch = pending[start:start + 32]
            response = request_json(f"{endpoint}/api/embed", method="POST",
                                    payload={"model": OLLAMA_EMBEDDING_MODEL, "input": [value for _, value, _ in batch], "truncate": True},
                                    timeout_seconds=3, max_attempts=1)
            vectors = response.get("embeddings") or []
            if len(vectors) != len(batch):
                raise ValueError("Ollama returned an unexpected embedding count")
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            for (key, _, digest), vector in zip(batch, vectors):
                if not isinstance(vector, list) or len(vector) < 8 or any(not isinstance(x, (float, int)) or not math.isfinite(x) for x in vector):
                    raise ValueError("Ollama returned an invalid sentence embedding")
                row = stored.get(key)
                if row is None:
                    row = TasteEmbedding(entity_key=key, content_hash=digest, model_name=OLLAMA_EMBEDDING_MODEL,
                                         vector_json=json.dumps(vector), updated_at=now)
                    db.add(row)
                else:
                    row.content_hash = digest; row.model_name = OLLAMA_EMBEDDING_MODEL
                    row.vector_json = json.dumps(vector); row.updated_at = now
                stored[key] = row
                written += 1
            db.commit()
        _FAILURE_UNTIL = 0.0; _FAILURE_MESSAGE = ""
        return written
    except Exception as exc:
        db.rollback()
        _FAILURE_UNTIL = time.monotonic() + 600
        _FAILURE_MESSAGE = str(exc)[:240]
        log.info("Local semantic ranking unavailable; lexical matching remains active: %s", _FAILURE_MESSAGE)
        return written


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    norm_left = math.sqrt(sum(x * x for x in left))
    norm_right = math.sqrt(sum(x * x for x in right))
    if not norm_left or not norm_right:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (norm_left * norm_right)


def semantic_similarities(db: Session, candidates: list[CatalogueItem], history: list[MediaItem]) -> dict[int, float]:
    candidate_keys = [f"catalogue:{item.id}" for item in candidates]
    liked_keys = [f"media:{item.id}" for item in history
                  if item.personal_rating is not None and item.personal_rating >= 8
                  or item.personal_rating is None and item.sentiment == "like"]
    positive_signal_keys = [f"signal:{signal.id}" for signal in db.query(TasteSignal).filter_by(direction="positive").all()]
    keys = candidate_keys + liked_keys + positive_signal_keys
    if not keys:
        return {}
    rows = db.query(TasteEmbedding).filter(TasteEmbedding.entity_key.in_(keys), TasteEmbedding.model_name == OLLAMA_EMBEDDING_MODEL).all()
    vectors = {}
    for row in rows:
        try:
            vectors[row.entity_key] = json.loads(row.vector_json)
        except (ValueError, TypeError):
            continue
    references = [vectors[key] for key in liked_keys + positive_signal_keys if key in vectors]
    if not references:
        return {}
    output = {}
    for item in candidates:
        vector = vectors.get(f"catalogue:{item.id}")
        if vector:
            output[item.id] = max(-1.0, min(1.0, sum(_cosine(vector, ref) for ref in references) / len(references)))
    return output


def embedding_status(db: Session) -> dict:
    count = db.query(TasteEmbedding).filter_by(model_name=OLLAMA_EMBEDDING_MODEL).count() if OLLAMA_EMBEDDING_MODEL else 0
    if not OLLAMA_EMBEDDING_MODEL:
        status = "disabled"
    elif _local_endpoint() is None:
        status = "local_host_required"
    elif time.monotonic() < _FAILURE_UNTIL:
        status = "unavailable"
    elif count:
        status = "ready"
    else:
        status = "pending"
    return {"status": status, "model": OLLAMA_EMBEDDING_MODEL, "stored_vectors": count,
            "last_error": _FAILURE_MESSAGE if time.monotonic() < _FAILURE_UNTIL else ""}
