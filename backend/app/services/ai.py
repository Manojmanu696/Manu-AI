"""Provider boundary. The offline provider protects privacy and keeps v1 usable."""
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from ..models import MediaItem, Memory
from .recommendations import recommendations
from ..config import OPENAI_API_KEY


class AIProvider(ABC):
    @abstractmethod
    def respond(self, message: str, context: dict) -> dict: ...


def retrieve_context(db: Session, query: str) -> dict:
    terms = {term.lower() for term in query.split() if len(term) > 2}
    items = db.query(MediaItem).all()
    relevant = [item for item in items if terms & set((item.title + " " + item.genres + " " + item.tags).lower().split())]
    return {"items": relevant[:10], "memories": db.query(Memory).all()[:12]}


class LocalProvider(AIProvider):
    def __init__(self, db: Session): self.db = db

    def respond(self, message: str, context: dict) -> dict:
        recs = recommendations(self.db, limit=5)
        facts = [f"{item.title} — rated {item.personal_rating}/10" for item in context["items"] if item.personal_rating]
        if not facts:
            facts = [f"Your library currently has {self.db.query(MediaItem).count()} items."]
        picks = [{"title": r["item"].title, "type": r["item"].media_type, "score": r["score"], "reason": r["reasons"][0]} for r in recs]
        answer = "I’m using your local library and saved preferences. "
        answer += "These are the strongest current fits: " + (", ".join(p["title"] for p in picks[:3]) if picks else "add a few items and I’ll learn your taste.")
        return {"answer": answer, "mode": "local", "facts": facts, "recommendations": picks, "assumptions": ["Recommendation scores are explainable ranking signals, not probabilities."]}


class OpenAIProvider(AIProvider):
    """Intentional placeholder boundary; install provider SDK and wire here when opted in."""
    def respond(self, message: str, context: dict) -> dict:
        raise NotImplementedError("OpenAI is configured as an optional future provider. Local AI remains active.")


def current_provider(db: Session) -> AIProvider:
    # An API key is never used silently; v1 stays local until an explicit cloud toggle exists.
    return LocalProvider(db)

