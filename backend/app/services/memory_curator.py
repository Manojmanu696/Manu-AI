"""Memory curation adapter used by the ChatGPT ↔ Manu AI bridge."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .memory_lab import analyze


def curate_memory(db: Session, text: str) -> dict:
    """Analyse pasted context and return reviewable memory proposals.

    The database argument is intentionally accepted for the API service contract,
    but curation itself does not write to the database. The UI must explicitly
    approve each proposal before it becomes a stored memory.
    """
    del db
    return analyze(text)
