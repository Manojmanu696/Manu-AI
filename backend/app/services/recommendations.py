"""Heuristic ranking with explainable narrative signals and a separate personal evidence layer."""
from collections import Counter
import re

from ..models import CatalogueItem, MediaItem, RecommendationFeedback
from .evidence import EXPLICIT_SOURCES, FRESH_EXCLUSIONS, field, personal_media, same_work, taste_memories

DIMENSIONS = {
    "Curiosity": {"investigation", "investigate", "investigates", "mystery", "mysterious", "riddle", "conspiracy", "secret", "secrets"},
    "Stakes": {"survive", "survival", "consequences", "war", "rescue", "escape", "stakes", "risk"},
    "Progression": {"mission", "journey", "tournament", "mastery", "training", "heist", "strategy", "strategic"},
    "Payoff potential": {"resolution", "payoff", "unravel", "revelation", "ending", "reveal"},
}


def terms(value):
    return {part.strip().casefold() for part in re.split(r"[,|;/]", value or "") if part.strip()}


def words(value):
    return set(re.findall(r"[^\W_]+", value.casefold()))


def taste(db):
    history = personal_media(db).all()
    liked = [row for row in history if (row.personal_rating or 0) >= 8 or row.sentiment == "like"]
    evidence = Counter(genre for row in liked for genre in terms(row.genres))
    tags = Counter(tag for row in liked for tag in terms(row.tags))
    memories = [row for row in taste_memories(db) if row.source in EXPLICIT_SOURCES]
    return evidence, tags, memories


def score_title(candidate, evidence, feedback=None):
    genres = terms(field(candidate, "genres"))
    tags = terms(field(candidate, "tags"))
    description = field(candidate, "description") or ""
    narrative = words(" ".join((description, " ".join(tags))))
    signals = [label for label, keywords in DIMENSIONS.items() if narrative & keywords]
    liked_genres, liked_tags, memories = evidence
    profile_words = set().union(*(words(row.content) for row in memories))
    score = 45 + 6 * len(signals)
    reasons = [f"The premise signals {', '.join(label.lower() for label in signals)}."] if signals else []
    genre_matches = genres & set(liked_genres)
    if genre_matches:
        score += min(8, 2 * sum(liked_genres[g] for g in genre_matches))
        reasons.append("Shares genres with titles you rated highly: " + ", ".join(sorted(genre_matches)[:3]))
    tag_match = tags & set(liked_tags)
    if tag_match:
        score += min(8, 3 * len(tag_match))
        reasons.append("Shares themes with titles you liked: " + ", ".join(sorted(tag_match)[:3]))
    if signals and any(narrative & keywords & profile_words for keywords in DIMENSIONS.values()):
        score += 5
        reasons.append("The premise overlaps with a saved storytelling preference.")
    if tags & {"filler", "repetitive", "slow start"}:
        score -= 8
    if feedback == "like":
        score += 8
        reasons.append("You explicitly liked this suggestion.")
    if not reasons:
        reasons.append("Exploration pick with limited personal evidence.")
    return max(1, min(99, score)), reasons[:3]


def runtime_minutes(value):
    if match := re.fullmatch(r"(\d+)\s*min(?:utes)?", (value or "").strip(), re.I):
        return int(match[1])
    return None


def meets_constraints(item, language=None, max_minutes=None):
    if language:
        aliases = {"english": "en", "hindi": "hi", "japanese": "ja", "malayalam": "ml", "korean": "ko"}
        available = set(item.get("audio_languages", [])) | terms(item.get("language")) | terms(item.get("languages")) if isinstance(item, dict) else set()
        requested = language.casefold().strip()
        if requested not in available and aliases.get(requested) not in available:
            return False
    if max_minutes is not None:
        if field(item, "media_type") != "movie":
            episodes = item.get("episodes") if isinstance(item, dict) else getattr(item, "episodes", None)
            duration = item.get("episode_duration") if isinstance(item, dict) else getattr(item, "episode_duration", None)
            episode_minutes = runtime_minutes(duration)
            total = episodes * episode_minutes if episodes and episode_minutes else None
        else:
            total = runtime_minutes(field(item, "runtime"))
        if total is None or total > max_minutes:
            return False
    return True


def feedback_by_title(db):
    latest = {}
    rows = db.query(RecommendationFeedback).order_by(RecommendationFeedback.created_at.desc(), RecommendationFeedback.id.desc())
    for row in rows:
        latest.setdefault(row.catalogue_item_id, row.action)
    return latest


def recommend_order(results, limit, diversify=False):
    ranked = sorted(results, key=lambda row: -row["score"])
    if not ranked:
        return []
    chosen = [ranked.pop(0)]
    seen_types = Counter([field(chosen[0]["item"], "media_type")])
    seen_genres = Counter(terms(field(chosen[0]["item"], "genres")))
    while ranked and len(chosen) < limit:
        candidate = max(ranked, key=lambda row: row["score"] - (
            min(10, 4 * seen_types[field(row["item"], "media_type")]) +
            min(8, sum(seen_genres[g] for g in terms(field(row["item"], "genres")))) if diversify else 0))
        ranked.remove(candidate)
        chosen.append(candidate)
        seen_types[field(candidate["item"], "media_type")] += 1
        seen_genres.update(terms(field(candidate["item"], "genres")))
    for index, result in enumerate(chosen):
        result.update(verdict="Best pick" if index == 0 else "Consider",
                      caveat="Execution, hook timing and payoff are unverified from catalogue metadata.")
    return chosen


def recommendations(db, media_type=None, limit=12, language=None, max_minutes=None):
    evidence = taste(db)
    history = personal_media(db).all()
    negatives = [row for row in history if row.status in FRESH_EXCLUSIONS or row.sentiment == "dislike"]
    feedback = feedback_by_title(db)
    hidden = [row for row in db.query(CatalogueItem).filter_by(is_demo=False)
              if feedback.get(row.id) in {"watched", "not_for_me"}]
    candidates = [row for row in history if row.status in {"want", "on_hold", "recommended", "unwatched"}
                  and row.sentiment != "dislike" and (not media_type or row.media_type == media_type)]
    results = []
    for item in candidates:
        if any(same_work(item, row) for row in negatives + hidden) or not meets_constraints(item, language, max_minutes):
            continue
        if any(same_work(item, row["item"]) for row in results):
            continue
        score, reasons = score_title(item, evidence)
        results.append({"item": item, "score": score, "reasons": reasons})
    return recommend_order(results, limit, diversify=True)
