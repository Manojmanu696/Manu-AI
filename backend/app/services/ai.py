"""Manu AI intelligence layer: local memory + Ollama + live read-only web tools."""
from __future__ import annotations
import json
import re
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from .evidence import personal_media, taste_memories, now
from .discovery import discover
from .evidence import field, same_work
from .local_ai_records import add_record
from ..models import LocalAIRecord
from datetime import timedelta
from .recommendations import recommendations
from .internet import tool_definitions, execute_tool
from .ollama import chat as ollama_chat, OllamaUnavailable
from .rating_feedback import latest_feedback

def asks_for_recommendations(message):
    return bool(re.search(r"\b(recommend(?:ations?)?|what (?:should|can) i watch|suggest|top \d+)\b", message, re.I))


class AIProvider(ABC):
    @abstractmethod
    def respond(self, message: str, context: dict) -> dict: ...

def retrieve_context(db: Session, query: str) -> dict:
    items = personal_media(db).all()
    memories = taste_memories(db)[:30]
    q = query.lower()
    relevant = [i for i in items if any(term in (i.title + " " + i.genres + " " + i.tags).lower() for term in q.split() if len(term) > 2)]
    return {"items": relevant[:20] or items[:20], "memories": memories,
            "rating_feedback": list(latest_feedback(db).values())[:30]}

def _context_text(context: dict) -> str:
    items = []
    for i in context["items"]:
        items.append({"title": i.title, "type": i.media_type, "saved_rating_out_of_10": i.personal_rating, "status": i.status, "genres": i.genres, "tags": i.tags, "notes": i.notes})
    memories = [{"category": m.category, "content": m.content, "source": m.source} for m in context["memories"]]
    return json.dumps({"library": items, "memory": memories,
                       "rating_feedback": context["rating_feedback"]}, ensure_ascii=False)

class LocalProvider(AIProvider):
    def __init__(self, db: Session): self.db = db

    def respond(self, message: str, context: dict) -> dict:
        count = re.search(r"\b(\d{1,2})\s+(?:recommendations|titles|movies|shows|anime|picks)\b", message.casefold())
        limit = max(1, min(20, int(count[1]))) if count else 5
        kind = next((kind for expression, kind in ((r"\b(?:movies?|films?)\b", "movie"),
                        (r"\b(?:shows?|series)\b", "tv"), (r"\banime\b", "anime")) if re.search(expression, message.casefold())), None)
        language = "English" if re.search(r"\benglish\b", message, re.I) else None
        duration = re.search(r"\b(?:under|at most|max(?:imum)?)\s+(\d+)\s*(minutes?|hours?)\b", message, re.I)
        maximum = int(duration[1]) * (60 if duration[2].lower().startswith("hour") else 1) if duration else None
        recs = discover(self.db, kind, limit * 3, language=language, max_minutes=maximum)
        for candidate in recommendations(self.db, kind, limit, language, maximum):
            if len(recs) < limit and not any(same_work(candidate["item"], row["item"]) for row in recs):
                recs.append(candidate)
        recent = self.db.query(LocalAIRecord).filter_by(kind="recommendation_shown").filter(
            LocalAIRecord.created_at >= now() - timedelta(days=2)
        ).order_by(LocalAIRecord.created_at.desc()).limit(30).all()
        seen = [title for row in recent for title in row.data.get("titles", [])]
        recs.sort(key=lambda row: sum(same_work(row["item"], prior) for prior in seen))
        recs = recs[:limit]
        if recs and asks_for_recommendations(message):
            add_record(self.db, "recommendation_shown", {"titles": [
                {key: field(row["item"], key) for key in ("title", "media_type", "release_year", "external_id")}
                for row in recs
            ]})
        picks = [{"title": field(r["item"], "title"), "type": field(r["item"], "media_type"),
                  "score": r["score"], "reason": r["reasons"][0]} for r in recs]
        lines = [f"{index}. {pick['title']} · {pick['reason']}" for index, pick in enumerate(picks, 1)]
        if picks:
            lines.append(f"Best pick: {picks[0]['title']}.")
        facts = [f"{i.title} — saved rating {i.personal_rating}/10" for i in context["items"] if i.personal_rating]
        return {"answer": "\n".join(lines) or "No verified catalogue candidates match these filters.",
                "mode": "local", "facts": facts, "recommendations": picks,
                "assumptions": ["Personal fit is a heuristic ranking signal. Availability and language need a source."]}


class OllamaProvider(AIProvider):
    def __init__(self, db: Session): self.db = db

    def respond(self, message: str, context: dict) -> dict:
        if asks_for_recommendations(message):
            return LocalProvider(self.db).respond(message, context)
        system = """You are Manu AI, a personal discovery intelligence. Use the supplied private library and memory as the source of truth for personal taste. You may use the read-only web_search and web_fetch tools whenever current information, availability, new releases, ratings, or facts are needed. Do NOT say you cannot search merely because a query is outside the local library: search the public web. Never send private memory or library data to a web tool. Never claim a fact is current without web research. Latest explicit corrections and confirmed activity take precedence over imported claims and hypotheses. Unknown status means unknown. Treat completion as activity, never as enjoyment. Never reconstruct a rating from praise, older scales, or estimates, and never fabricate an exact score or claim a save. Prefer curiosity, meaningful stakes, progression and payoff across genres. Discuss metadata only when present in the supplied evidence or verified by a source. If Indian availability, dub, or personal history is missing, say unverified. Give concise explanations."""
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
