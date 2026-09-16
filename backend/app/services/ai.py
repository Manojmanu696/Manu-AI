"""Manu AI intelligence layer: local memory + Ollama + live read-only web tools."""
from __future__ import annotations
import json
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from ..models import MediaItem, Memory
from .recommendations import recommendations
from .internet import tool_definitions, execute_tool
from .ollama import chat as ollama_chat, OllamaUnavailable

class AIProvider(ABC):
    @abstractmethod
    def respond(self, message: str, context: dict) -> dict: ...

def retrieve_context(db: Session, query: str) -> dict:
    items = db.query(MediaItem).all()
    memories = db.query(Memory).order_by(Memory.created_at.desc()).limit(30).all()
    q = query.lower()
    relevant = [i for i in items if any(term in (i.title + " " + i.genres + " " + i.tags).lower() for term in q.split() if len(term) > 2)]
    return {"items": relevant[:20] or items[:20], "memories": memories}

def _context_text(context: dict) -> str:
    items = []
    for i in context["items"]:
        items.append({"title": i.title, "type": i.media_type, "rating": i.personal_rating, "status": i.status, "genres": i.genres, "tags": i.tags, "notes": i.notes})
    memories = [{"category": m.category, "content": m.content, "source": m.source, "confidence": m.confidence} for m in context["memories"]]
    return json.dumps({"library": items, "memory": memories}, ensure_ascii=False)

class LocalProvider(AIProvider):
    def __init__(self, db: Session): self.db = db

    def respond(self, message: str, context: dict) -> dict:
        recs = recommendations(self.db, limit=8)
        picks = [{"title": r["item"].title, "type": r["item"].media_type, "score": r["score"], "reason": r["reasons"][0]} for r in recs]
        facts = [f"{i.title} — rated {i.personal_rating}/10" for i in context["items"] if i.personal_rating]
        return {"answer": "Your local recommendation engine is ready. " + ("Top current fits: " + ", ".join(p["title"] for p in picks[:3]) if picks else "Add a few favorites and I’ll learn your taste."), "mode": "local", "facts": facts, "recommendations": picks, "assumptions": ["Scores are ranking signals, not probabilities."]}

class OllamaProvider(AIProvider):
    def __init__(self, db: Session): self.db = db

    def respond(self, message: str, context: dict) -> dict:
        system = """You are Manu AI, a personal discovery intelligence. Use the supplied private library and memory as the source of truth for personal taste. You may use the read-only web_search and web_fetch tools whenever current information, availability, new releases, ratings, or facts are needed. Do NOT say you cannot search merely because a query is outside the local library: search the public web. Never send private memory or library data to a web tool. Never claim a fact is current without web research. When recommending entertainment, optimize for the user's saved taste: short, engaging, non-filler, avoid mainly slow emotional drama. Give concise, useful explanations."""
        messages = [{"role":"system", "content": system + "\nPRIVATE LOCAL CONTEXT:\n" + _context_text(context)}, {"role":"user", "content": message}]
        tools = tool_definitions()
        used_web = False
        sources = []
        for _ in range(4):
            response = ollama_chat(messages, tools)
            msg = response.get("message", {})
            messages.append(msg)
            calls = msg.get("tool_calls") or []
            if not calls:
                answer = (msg.get("content") or "").strip()
                return {"answer": answer, "mode": "ollama+web" if used_web else "ollama", "model": response.get("_model"), "facts": [], "recommendations": [], "sources": sources, "assumptions": []}
            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try: args = json.loads(args)
                    except json.JSONDecodeError: args = {}
                result = execute_tool(name, args)
                if name in {"web_search", "web_fetch"}: used_web = True
                if name == "web_search": sources.extend(result.get("results", []))
                elif name == "web_fetch": sources.append({"title": result.get("title", ""), "url": result.get("url", ""), "snippet": result.get("text", "")[:300]})
                messages.append({"role":"tool", "content":json.dumps(result, ensure_ascii=False)})
        raise OllamaUnavailable("Ollama used too many tool rounds")

def current_provider(db: Session) -> AIProvider:
    try:
        from .ollama import available
        if available(): return OllamaProvider(db)
    except Exception:
        pass
    return LocalProvider(db)
