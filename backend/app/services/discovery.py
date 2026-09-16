from __future__ import annotations
import re
from collections import Counter
from sqlalchemy.orm import Session
from ..models import CatalogueItem, MediaItem, Memory, RecommendationFeedback
from .internet import current_search_provider


def _terms(value: str | None) -> set[str]:
    return {x.strip().lower() for x in re.split(r"[,|;/]", value or "") if x.strip()}


def _tokens(value: str | None) -> set[str]:
    stop = {"the", "and", "with", "from", "that", "this", "your", "you"}
    return {x for x in re.findall(r"[a-z0-9]{3,}", (value or "").lower()) if x not in stop}


def _taste(db: Session):
    history = db.query(MediaItem).all()
    memories = db.query(Memory).all()
    liked = [x for x in history if (x.personal_rating or 0) >= 8 or x.sentiment == "like" or x.status == "completed"]
    disliked = [x for x in history if (x.personal_rating or 0) <= 5 or x.sentiment == "dislike" or x.status == "dropped"]
    liked_genres = Counter(g for x in liked for g in _terms(x.genres))
    liked_tags = Counter(t for x in liked for t in _terms(x.tags))
    disliked_genres = Counter(g for x in disliked for g in _terms(x.genres))
    memory_text = " ".join(m.content.lower() for m in memories)
    return liked_genres, liked_tags, disliked_genres, memory_text


def score_catalogue_item(db: Session, candidate: CatalogueItem) -> tuple[int, list[str]]:
    liked_genres, liked_tags, disliked_genres, memory_text = _taste(db)
    score = 50
    reasons: list[str] = []
    genres, tags = _terms(candidate.genres), _terms(candidate.tags)
    genre_hits, tag_hits, avoid_hits = genres & set(liked_genres), tags & set(liked_tags), genres & set(disliked_genres)
    if genre_hits:
        score += min(24, 6 * sum(liked_genres[g] for g in genre_hits))
        reasons.append(f"Matches genres you repeatedly enjoy: {', '.join(sorted(genre_hits)[:3])}")
    if tag_hits:
        score += min(14, 4 * sum(liked_tags[t] for t in tag_hits))
        reasons.append("Shares themes you have liked before")
    if avoid_hits:
        score -= min(18, 6 * len(avoid_hits))
        reasons.append(f"Overlaps with genres you have disliked: {', '.join(sorted(avoid_hits)[:2])}")
    searchable = " ".join([candidate.title, candidate.description, candidate.genres, candidate.tags, candidate.story_focus, candidate.gameplay_style]).lower()
    memory_hits = [t for t in _tokens(memory_text) if t in searchable]
    if memory_hits:
        score += min(18, 3 * len(memory_hits))
        reasons.append("Matches your saved taste profile")
    if any(k in memory_text for k in ("short", "non-filler", "fast paced", "fast-paced", "engaging")):
        runtime = f"{candidate.runtime} {candidate.episode_duration} {candidate.reading_length}".lower()
        if any(k in runtime for k in ("90 min", "100 min", "110 min", "120 min", "20 min", "25 min", "30 min")):
            score += 6
            reasons.append("Fits your preference for shorter, engaging content")
        if "filler" in candidate.tags.lower():
            score -= 12
    for event in db.query(RecommendationFeedback).filter_by(catalogue_item_id=candidate.id).all():
        score += {"like": 7, "watchlist": 5, "watched": -4, "not_for_me": -18}.get(event.action, 0)
    if candidate.imdb_rating:
        score += min(8, max(0, candidate.imdb_rating - 7) * 2)
    if not reasons:
        reasons.append("A new candidate selected for exploration")
    return max(1, min(99, round(score))), reasons[:3]


def discover(db: Session, media_type: str | None = None, limit: int = 24, query: str | None = None) -> list[dict]:
    q = db.query(CatalogueItem)
    if media_type: q = q.filter(CatalogueItem.media_type == media_type)
    rows = q.all()
    owned = {x.title.strip().lower() for x in db.query(MediaItem).all()}
    if query:
        tokens = _tokens(query)
        rows = [x for x in rows if not tokens or tokens & _tokens(" ".join([x.title, x.genres, x.tags, x.description]))]
    rows = [x for x in rows if x.title.strip().lower() not in owned]
    ranked = []
    for item in rows:
        score, reasons = score_catalogue_item(db, item)
        ranked.append({"item": item, "score": score, "reasons": reasons, "source": "local_catalogue"})
    return sorted(ranked, key=lambda x: x["score"], reverse=True)[:limit]


def web_discover(query: str, limit: int = 8) -> list[dict]:
    results = current_search_provider().search(query, limit=limit)
    return [{"title": r.title, "url": r.url, "snippet": r.snippet, "provider": r.provider, "source": "web"} for r in results]
