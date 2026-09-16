"""Deterministic, explainable local recommendation scoring.

Scores are ordering signals—not probabilities—and intentionally remain inspectable.
"""
from collections import Counter
from ..models import MediaItem, Memory


def _terms(value: str) -> set[str]:
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def score_candidate(candidate: MediaItem, history: list[MediaItem], memories: list[Memory]):
    score, reasons = 45, []
    liked = [i for i in history if (i.personal_rating or 0) >= 8 or i.sentiment == "like"]
    dropped = [i for i in history if i.status == "dropped" or i.sentiment == "dislike"]
    candidate_genres = _terms(candidate.genres)
    candidate_tags = _terms(candidate.tags)

    for item in liked:
        shared_genres = candidate_genres & _terms(item.genres)
        shared_tags = candidate_tags & _terms(item.tags)
        if shared_genres:
            score += min(16, 5 * len(shared_genres))
            reasons.append(f"Shares {', '.join(sorted(shared_genres))} with {item.title}")
            break
        if shared_tags:
            score += min(10, 4 * len(shared_tags))
            reasons.append(f"Connects with the themes you liked in {item.title}")
            break

    for item in dropped:
        overlap = candidate_genres & _terms(item.genres)
        if overlap:
            score -= 10
            reasons.append(f"Some overlap with genres you tend to avoid: {', '.join(sorted(overlap))}")
            break

    preferences = " ".join(m.content.lower() for m in memories)
    matching = [genre for genre in candidate_genres if genre in preferences]
    if matching:
        score += min(12, 4 * len(matching))
        reasons.append(f"Matches your saved preference for {', '.join(sorted(matching))}")
    if candidate.status == "want":
        score += 4
    if not reasons:
        reasons.append("A curated candidate ready for you to explore")
    return max(1, min(99, score)), reasons[:3]


def recommendations(db, media_type: str | None = None, limit: int = 12):
    all_items = db.query(MediaItem).all()
    candidates = [i for i in all_items if i.status in {"want", "on_hold"} and (not media_type or i.media_type == media_type)]
    memories = db.query(Memory).all()
    results = []
    for item in candidates:
        score, reasons = score_candidate(item, all_items, memories)
        results.append({"item": item, "score": score, "reasons": reasons})
    return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]

