"""Explainable personal recommendation scoring over the private library."""
from collections import Counter
from ..models import MediaItem, Memory


def _terms(value: str | None) -> set[str]:
    return {part.strip().lower() for part in (value or "").replace("|", ",").split(",") if part.strip()}


def score_candidate(candidate: MediaItem, history: list[MediaItem], memories: list[Memory]):
    score, reasons = 45, []
    liked = [i for i in history if (i.personal_rating or 0) >= 8 or i.sentiment == "like" or i.status == "completed"]
    disliked = [i for i in history if (i.personal_rating or 0) <= 5 or i.sentiment == "dislike" or i.status == "dropped"]
    genres, tags = _terms(candidate.genres), _terms(candidate.tags)
    liked_genres = Counter(g for i in liked for g in _terms(i.genres))
    liked_tags = Counter(t for i in liked for t in _terms(i.tags))
    disliked_genres = Counter(g for i in disliked for g in _terms(i.genres))
    genre_hits, tag_hits, avoid_hits = genres & set(liked_genres), tags & set(liked_tags), genres & set(disliked_genres)
    if genre_hits:
        score += min(24, 6 * sum(liked_genres[g] for g in genre_hits)); reasons.append(f"Matches genres you repeatedly enjoy: {', '.join(sorted(genre_hits)[:3])}")
    if tag_hits:
        score += min(14, 4 * sum(liked_tags[t] for t in tag_hits)); reasons.append("Shares themes you have liked before")
    if avoid_hits:
        score -= min(18, 6 * len(avoid_hits)); reasons.append(f"Overlaps with genres you have disliked: {', '.join(sorted(avoid_hits)[:2])}")
    preference_text = " ".join(m.content.lower() for m in memories)
    searchable = " ".join([candidate.title, candidate.genres, candidate.tags, candidate.notes, candidate.description]).lower()
    preference_hits = [word for word in preference_text.replace(",", " ").split() if len(word) > 3 and word in searchable]
    if preference_hits:
        score += min(18, 3 * len(set(preference_hits))); reasons.append("Matches your saved taste profile")
    if any(k in preference_text for k in ("short", "non-filler", "fast paced", "fast-paced", "engaging")):
        runtime = candidate.runtime.lower()
        if runtime and any(k in runtime for k in ("90", "100", "110", "120", "20", "25", "30")):
            score += 6; reasons.append("Fits your preference for shorter, engaging content")
        if "filler" in candidate.tags.lower(): score -= 12
    if not reasons: reasons.append("A new candidate selected for exploration")
    return max(1, min(99, round(score))), reasons[:3]


def recommendations(db, media_type: str | None = None, limit: int = 12):
    all_items = db.query(MediaItem).all()
    candidates = [i for i in all_items if i.status in {"want", "on_hold"} and (not media_type or i.media_type == media_type)]
    memories = db.query(Memory).all()
    results = []
    for item in candidates:
        score, reasons = score_candidate(item, all_items, memories)
        results.append({"item": item, "score": score, "reasons": reasons})
    return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]
