"""Stale-while-revalidate homepage ingestion and deterministic personal ranking."""
from __future__ import annotations

import json
import hashlib
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..config import TMDB_API_KEY
from ..models import CatalogueItem, DiscoverySectionCache, MediaItem, Memory, RecommendationFeedback, TasteSignal
from .providers import AniListProvider, TMDBProvider, TVMazeProvider
from .embeddings import embedding_status, embedding_work_pending, prepare_local_embeddings, semantic_similarities

log = logging.getLogger(__name__)
PROVIDERS = {"tmdb": TMDBProvider(), "anilist": AniListProvider(), "tvmaze": TVMazeProvider()}
_LOCK = threading.Lock()
_RUNNING = False
_TTL_HOURS = {
    "trending_movies": 4, "trending_tv": 4, "popular_movies": 8, "popular_tv": 8,
    "now_playing": 8, "upcoming_movies": 24, "recent_releases": 12,
    "top_rated_movies": 24, "top_rated_tv": 24, "hidden_gems": 24,
    "psychological_thrillers": 24, "mind_games": 24, "intelligent_stories": 24,
    "short_movies": 24, "short_completed_series": 24, "popular_anime": 12,
    "seasonal_anime": 24, "tvmaze_catalogue": 24,
}
_PROVIDER_SECTIONS = {"tmdb": set(_TTL_HOURS) - {"popular_anime", "seasonal_anime", "tvmaze_catalogue"},
                      "anilist": {"popular_anime", "seasonal_anime"}, "tvmaze": {"tvmaze_catalogue"}}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _stale_sections(db: Session) -> set[str]:
    now = _now()
    records = {x.section_key: x for x in db.query(DiscoverySectionCache).all()}
    return {key for key in _TTL_HOURS if key not in records or records[key].expires_at <= now}


def _upsert_item(db: Session, row: dict) -> CatalogueItem:
    provider, provider_id = row.get("source_provider", "local"), row.get("provider_id")
    item = db.query(CatalogueItem).filter_by(source_provider=provider, provider_id=provider_id).first() if provider_id else None
    values = {k: v for k, v in row.items() if k in CatalogueItem.__table__.columns and k not in {"id", "created_at", "is_demo", "section", "source"}}
    values.update({"source_retrieved_at": _now(), "is_demo": False})
    if not item:
        item = CatalogueItem(**values)
        db.add(item)
        db.flush()
    else:
        for key, value in values.items():
            setattr(item, key, value)
    return item


def _refresh_provider(provider_name: str) -> tuple[str, dict[str, list[dict]], dict[str, str]]:
    provider = PROVIDERS[provider_name]
    try:
        sections = provider.fetch_sections()
        return provider_name, sections, getattr(provider, "errors", {})
    except Exception as exc:
        log.warning("Discovery provider %s failed: %s", provider_name, exc)
        return provider_name, {}, {section: str(exc)[:500] for section in _PROVIDER_SECTIONS[provider_name]}


def _refresh_worker(force: bool = False) -> None:
    global _RUNNING
    db = SessionLocal()
    try:
        stale = set(_TTL_HOURS) if force else _stale_sections(db)
        required = {name for name, sections in _PROVIDER_SECTIONS.items() if sections & stale}
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="manu-provider") as executor:
            futures = [executor.submit(_refresh_provider, name) for name in sorted(required)]
            results = [future.result() for future in futures]
        now = _now()
        fetched_any: set[str] = set()
        refreshed_sections: set[str] = set()
        errors: dict[str, dict[str, str]] = {}
        for name, sections, section_errors in results:
            if sections:
                fetched_any.add(name)
            if section_errors:
                errors[name] = section_errors
            for section, rows in sections.items():
                if section not in stale and not force:
                    continue
                if section in section_errors:
                    continue
                try:
                    objects = [_upsert_item(db, row) for row in rows]
                    cached = db.get(DiscoverySectionCache, section)
                    ids = [x.id for x in objects]
                    if cached:
                        cached.provider = name
                        cached.catalogue_ids_json = json.dumps(ids)
                        cached.fetched_at = now
                        cached.expires_at = now + timedelta(hours=_TTL_HOURS[section])
                        cached.last_error = ""
                    else:
                        db.add(DiscoverySectionCache(section_key=section, provider=name, catalogue_ids_json=json.dumps(ids), fetched_at=now, expires_at=now + timedelta(hours=_TTL_HOURS[section])))
                    refreshed_sections.add(section)
                except Exception:
                    log.exception("Could not persist discovery section %s", section)
                    db.rollback()
        # Record attempted-but-unavailable sections too; otherwise a missing
        # key or provider outage would trigger a new worker on every page poll.
        for key in stale - refreshed_sections:
            provider = next((name for name, names in _PROVIDER_SECTIONS.items() if key in names), "")
            message = errors.get(provider, {}).get(key, "TMDB_API_KEY is not configured" if provider == "tmdb" and not TMDB_API_KEY else "Provider did not return this section")
            cached = db.get(DiscoverySectionCache, key)
            if cached:
                cached.last_error = message
                cached.expires_at = now + timedelta(minutes=20)
            else:
                db.add(DiscoverySectionCache(section_key=key, provider=provider, catalogue_ids_json="[]", fetched_at=now,
                                             expires_at=now + timedelta(minutes=20), last_error=message))
        db.commit()
        prepare_local_embeddings(db)
    except Exception:
        db.rollback()
        log.exception("Homepage discovery refresh failed")
    finally:
        db.close()
        with _LOCK:
            _RUNNING = False


def request_refresh(force: bool = False) -> bool:
    global _RUNNING
    with _LOCK:
        if _RUNNING:
            return False
        _RUNNING = True
    threading.Thread(target=_refresh_worker, args=(force,), name="manu-home-refresh", daemon=True).start()
    return True


def _fit_label(score: float) -> str:
    if score >= 74: return "Excellent fit"
    if score >= 63: return "Strong match"
    if score >= 52: return "Good fit"
    return "Explore"


def _tokens(text: str) -> set[str]:
    import re
    ignored = {"and", "the", "with", "for", "from", "that", "this", "have", "like", "movie", "show", "series"}
    return {x for x in re.findall(r"[a-z0-9]{3,}", (text or "").lower()) if x not in ignored}


def _completed_short_series(candidate: CatalogueItem) -> bool:
    status = (candidate.series_status or "").casefold()
    return (candidate.media_type in {"tv", "anime"}
            and status in {"ended", "canceled", "cancelled", "finished"}
            and candidate.episodes is not None and candidate.episodes <= 24)


def score_candidate(candidate: CatalogueItem, history: list[MediaItem], memories: list[Memory], signals: list[TasteSignal], events: list[RecommendationFeedback], feedback_genres: dict[str, int] | None = None, semantic_similarity: float = 0.0) -> tuple[float, list[str]]:
    """Two-stage ranking score. Scale is internal ordering only, never a probability."""
    score, reasons = 48.0, []
    genres = {x.strip().lower() for x in (candidate.genres or "").replace("|", ",").split(",") if x.strip()}
    positive: dict[str, set[str]] = {}
    negative: dict[str, set[str]] = {}
    for item in history:
        title_key = item.title.strip().casefold()
        liked = item.personal_rating >= 8 if item.personal_rating is not None else item.sentiment == "like"
        disliked = item.personal_rating <= 4 if item.personal_rating is not None else item.sentiment == "dislike"
        if liked:
            for genre in (x.strip().lower() for x in (item.genres or "").split(",") if x.strip()):
                positive.setdefault(genre, set()).add(title_key)
        if disliked:
            for genre in (x.strip().lower() for x in (item.genres or "").split(",") if x.strip()):
                negative.setdefault(genre, set()).add(title_key)
    hits = genres & positive.keys()
    avoids = {genre for genre, count in negative.items() if count >= 2} & genres
    if hits:
        score += min(20, sum(len(positive[g]) for g in hits) * 5)
        reasons.append("In genres you have rated highly: " + ", ".join(sorted(hits)[:2]))
    if avoids:
        score -= min(25, sum(len(negative[g]) for g in avoids) * 8)
        reasons.append("Includes genres you have rated poorly: " + ", ".join(sorted(avoids)[:2]))
    repeated_likes = [g for g in genres if (feedback_genres or {}).get(g, 0) >= 2]
    if repeated_likes:
        score += min(12, 3 * sum((feedback_genres or {})[g] for g in repeated_likes))
        reasons.append("Repeated positive feedback on " + ", ".join(sorted(repeated_likes)[:2]))
    candidate_text = " ".join((candidate.title, candidate.description, candidate.genres, candidate.tags, candidate.story_focus or "")).lower()
    history_terms = set()
    for item in history:
        if item.personal_rating is not None and item.personal_rating >= 8 or item.personal_rating is None and item.sentiment == "like":
            history_terms |= _tokens(" ".join((item.title, item.description, item.genres, item.tags)))
    semantic_hits = _tokens(candidate_text) & history_terms
    if semantic_hits:
        score += min(12, len(semantic_hits) * 1.4)
        if not reasons: reasons.append("Shares story themes with titles you rated highly")
    if semantic_similarity > 0.12:
        score += min(16, max(0.0, semantic_similarity) * 18)
        if semantic_similarity >= 0.36:
            reasons.append("Semantically similar to a title or preference you liked")
    preference_hits = []
    for signal in signals:
        if signal.source in {"explicit", "inferred"} and signal.value.lower() in candidate_text:
            magnitude = signal.strength * signal.confidence * (1.0 if signal.source == "explicit" else 0.55)
            if signal.direction == "negative": score -= 12 * magnitude
            else: score += 10 * magnitude
            if signal.direction != "negative": preference_hits.append(signal.value)
    explicit_text = " ".join(m.content.lower() for m in memories if m.source in {"user", "chatgpt_import"})
    compact_title = (candidate.media_type == "movie" and candidate.runtime_minutes is not None and candidate.runtime_minutes <= 120) or _completed_short_series(candidate)
    if any(x in explicit_text for x in ("short", "engaging", "non-filler")) and compact_title:
        score += 4
        if not reasons: reasons.append("Fits your preference for compact, engaging stories")
    feedback = [e for e in events if e.catalogue_item_id == candidate.id and not e.undone]
    actions = {e.action for e in feedback}
    score += sum({"love": 18, "like": 10, "not_interested": -40, "watchlist": 4}.get(e.action, 0) for e in feedback)
    if "not_interested" in actions:
        reasons.append("You previously marked this as not for you")
    votes = max(0, candidate.vote_count or 0)
    rating = candidate.public_rating or candidate.imdb_rating
    if rating:
        confidence = votes / (votes + 200) if votes else 0.25
        score += max(-3, min(5, (float(rating) - 6.0) * confidence * 1.7))
    if not reasons:
        reasons.append("Selected to broaden your discovery")
    if preference_hits:
        reasons.insert(0, "Matches a saved preference: " + ", ".join(preference_hits[:2]))
    return score, reasons[:3]


def recommendation_caveats(candidate: CatalogueItem, history: list[MediaItem], signals: list[TasteSignal]) -> list[str]:
    searchable = " ".join((candidate.title, candidate.description, candidate.genres, candidate.tags, candidate.story_focus or "")).lower()
    caveats = []
    for signal in signals:
        if signal.direction == "negative" and signal.source in {"explicit", "inferred"} and signal.value.lower() in searchable:
            caveats.append(f"May not fit the saved preference: {signal.value}.")
    negative_genres: dict[str, set[str]] = {}
    for entry in history:
        disliked = entry.personal_rating <= 4 if entry.personal_rating is not None else entry.sentiment == "dislike"
        if disliked:
            for genre in (x.strip().lower() for x in (entry.genres or "").split(",") if x.strip()):
                negative_genres.setdefault(genre, set()).add(entry.title.casefold())
    repeated = sorted(genre for genre, titles in negative_genres.items() if len(titles) >= 2 and genre in candidate.genres.lower())
    if repeated:
        caveats.append("Includes genres seen in multiple titles you rated poorly: " + ", ".join(repeated[:2]) + ".")
    return caveats or ["No clear mismatch is present in the available catalogue details."]


def _ranking_context(db: Session) -> dict:
    history = db.query(MediaItem).all()
    memories = db.query(Memory).all()
    signals = db.query(TasteSignal).all()
    events = db.query(RecommendationFeedback).filter_by(undone=False).all()
    positive_ids = {e.catalogue_item_id for e in events if e.action in {"love", "like"}}
    feedback_genres: dict[str, int] = {}
    if positive_ids:
        for liked_item in db.query(CatalogueItem).filter(CatalogueItem.id.in_(positive_ids)).all():
            for genre in (g.strip().lower() for g in (liked_item.genres or "").split(",") if g.strip()):
                feedback_genres[genre] = feedback_genres.get(genre, 0) + 1
    seen_ids = {i.external_id for i in history if i.external_id}
    seen_titles = {i.title.strip().casefold() for i in history}
    excluded_actions = {"already_watched", "started", "completed", "dropped", "not_interested"}
    exclude_provider_ids = {e.catalogue_item_id for e in events if e.action in excluded_actions and not e.undone}
    return {"history": history, "memories": memories, "signals": signals, "events": events,
            "feedback_genres": feedback_genres, "seen_ids": seen_ids, "seen_titles": seen_titles,
            "exclude_provider_ids": exclude_provider_ids}


def rank_catalogue(db: Session, items: list[CatalogueItem], *, limit: int = 12, mode: str = "best_fit", mood: str = "", context: dict | None = None) -> list[dict]:
    context = context or _ranking_context(db)
    history = context["history"]
    memories = context["memories"]
    signals = context["signals"]
    events = context["events"]
    feedback_genres = context["feedback_genres"]
    seen_ids = context["seen_ids"]
    seen_titles = context["seen_titles"]
    exclude_provider_ids = context["exclude_provider_ids"]
    candidates = [i for i in items if i.id not in exclude_provider_ids and i.external_id not in seen_ids and i.title.strip().casefold() not in seen_titles]
    preferences = {
        "psychological": ("thriller", "mystery", "psychological", "crime"),
        "mystery": ("mystery", "crime", "thriller", "science fiction"),
        "fast_hook": ("thriller", "action", "adventure", "crime"),
        "hidden_gems": (), "short_movies": (), "short_series": (),
        "critically_acclaimed": (), "explore": (), "surprise": (), "best_fit": (),
    }
    target_mode = mode if mode in preferences else "best_fit"
    ranked = []
    for candidate in candidates:
        score, reasons = score_candidate(candidate, history, memories, signals, events, feedback_genres,
                                         context.get("semantic_similarities", {}).get(candidate.id, 0.0))
        lower = (candidate.genres + " " + candidate.tags + " " + candidate.description).lower()
        mode_terms = preferences[target_mode]
        if mode_terms and any(term in lower for term in mode_terms): score += 9
        if target_mode == "hidden_gems" and 25 <= (candidate.vote_count or 0) <= 1500: score += 5
        if target_mode == "short_movies" and candidate.media_type == "movie" and candidate.runtime_minutes and candidate.runtime_minutes <= 110: score += 10
        if target_mode == "short_series" and _completed_short_series(candidate): score += 10
        if target_mode == "critically_acclaimed" and candidate.public_rating and candidate.public_rating >= 7.5: score += 5
        if target_mode == "explore": score += max(0, 18 - min(candidate.vote_count or 0, 1800) / 100)
        if mood:
            mood_terms = _tokens(mood)
            overlap = _tokens(lower) & mood_terms
            score += min(8, 2 * len(overlap))
            if "two hours" in mood.lower() and candidate.media_type == "movie" and candidate.runtime_minutes and candidate.runtime_minutes <= 120: score += 10
            if "short series" in mood.lower() and candidate.media_type in {"tv", "anime"} and candidate.episodes and candidate.episodes <= 24: score += 10
            if ("english audio" in mood.lower() or "english originals" in mood.lower()) and candidate.original_language == "en": score += 5
        ranked.append((score, candidate, reasons))
    if target_mode == "surprise":
        today = _now().date().isoformat()
        ranked.sort(key=lambda x: hashlib.sha256(f"{today}:{x[1].id}".encode()).hexdigest())
    else:
        ranked.sort(key=lambda x: (-x[0], (x[1].title or "").casefold(), x[1].id))
    selected, genre_counts, franchises = [], {}, set()
    while ranked and len(selected) < limit:
        best_index, best_value = 0, float("-inf")
        for index, (score, candidate, _) in enumerate(ranked):
            genres = {g.strip().casefold() for g in (candidate.genres or "").split(",") if g.strip()}
            penalty = sum(max(0, genre_counts.get(g, 0) - 1) * 3 for g in genres)
            franchise = _tokens(candidate.title)
            duplicate_penalty = 8 if franchise & franchises else 0
            value = score - penalty - duplicate_penalty
            if value > best_value:
                best_index, best_value = index, value
        score, candidate, reasons = ranked.pop(best_index)
        genres = {g.strip().casefold() for g in (candidate.genres or "").split(",") if g.strip()}
        for genre in genres: genre_counts[genre] = genre_counts.get(genre, 0) + 1
        franchises |= _tokens(candidate.title)
        selected.append({"item": candidate, "score": round(score, 2), "fit": _fit_label(score), "reasons": reasons, "source": candidate.source_provider})
    return selected


def home_snapshot(db: Session, *, force_refresh: bool = False, mode: str = "best_fit", mood: str = "") -> dict:
    cache = {x.section_key: x for x in db.query(DiscoverySectionCache).all()}
    stale = _stale_sections(db)
    if force_refresh or stale or embedding_work_pending(db):
        request_refresh(force_refresh)
    all_ids = {int(item_id) for record in cache.values() for item_id in json.loads(record.catalogue_ids_json or "[]")}
    rows = db.query(CatalogueItem).filter(CatalogueItem.id.in_(all_ids)).all() if all_ids else []
    by_id = {x.id: x for x in rows}
    ranking_context = _ranking_context(db)
    ranking_context["semantic_similarities"] = semantic_similarities(db, rows, ranking_context["history"])
    sections = {}
    for key in _TTL_HOURS:
        record = cache.get(key)
        ids = json.loads(record.catalogue_ids_json or "[]") if record else []
        items = [by_id[i] for i in ids if i in by_id]
        ranked = rank_catalogue(db, items, limit=18, mode=mode, mood=mood, context=ranking_context)
        sections[key] = {"items": ranked, "provider": record.provider if record else next((n for n, names in _PROVIDER_SECTIONS.items() if key in names), ""),
                         "fetched_at": record.fetched_at.isoformat() if record else None,
                         "stale": bool(record and (record.expires_at <= _now() or record.last_error)), "error": record.last_error if record else ""}
    all_items = list({item.id: item for item in rows}.values())
    movies = [x for x in all_items if x.media_type == "movie"]
    shows = [x for x in all_items if x.media_type in {"tv", "anime"}]
    sections["personalized_movies"] = {"items": rank_catalogue(db, movies, limit=18, mode=mode, mood=mood, context=ranking_context),
                                       "provider": "personalized", "fetched_at": newest_cache(cache), "stale": bool(stale), "error": ""}
    sections["personalized_tv"] = {"items": rank_catalogue(db, shows, limit=18, mode=mode, mood=mood, context=ranking_context),
                                   "provider": "personalized", "fetched_at": newest_cache(cache), "stale": bool(stale), "error": ""}
    liked = db.query(MediaItem).filter((MediaItem.personal_rating >= 8) | ((MediaItem.personal_rating.is_(None)) & (MediaItem.sentiment == "like"))).order_by(MediaItem.date_added.desc()).first()
    if liked:
        similar = rank_catalogue(db, all_items, limit=18, mode=mode, mood=mood, context=ranking_context)
        liked_terms = _tokens(" ".join((liked.title, liked.genres, liked.tags, liked.description)))
        similar = [x for x in similar if liked_terms & _tokens(" ".join((x["item"].title, x["item"].genres, x["item"].description)))]
        for x in similar: x["reasons"] = [f"Shares themes with {liked.title}", *x["reasons"][:2]]
    else:
        similar = []
    sections["because_you_liked"] = {"items": similar[:18], "based_on": liked.title if liked else None,
                                     "provider": "personalized", "fetched_at": newest_cache(cache), "stale": bool(stale), "error": ""}
    in_progress = db.query(MediaItem).filter(MediaItem.status == "current", MediaItem.media_type.in_(["movie", "tv", "anime"])).order_by(MediaItem.date_added.desc()).limit(12).all()
    sections["continue_watching"] = {"items": [{"item": x, "fit": "In progress", "reasons": [], "is_local": True} for x in in_progress],
                                     "provider": "local", "fetched_at": newest_cache(cache), "stale": False, "error": ""}
    newest = max((x.fetched_at for x in cache.values()), default=None)
    with _LOCK: refreshing = _RUNNING
    provider_last = {name: [c for c in cache.values() if c.provider == name] for name in PROVIDERS}
    providers = {
        "tmdb": {"status": "configured" if TMDB_API_KEY else "not_configured",
                 "last_error": next((c.last_error for c in provider_last["tmdb"] if c.last_error), "")},
        "anilist": {"status": "available" if any(c.provider == "anilist" for c in cache.values()) else "pending",
                    "last_error": next((c.last_error for c in provider_last["anilist"] if c.last_error), "")},
        "tvmaze": {"status": "available" if any(c.provider == "tvmaze" for c in cache.values()) else "pending",
                   "last_error": next((c.last_error for c in provider_last["tvmaze"] if c.last_error), "")},
    }
    return {"sections": sections, "refreshing": refreshing, "last_updated": newest.isoformat() if newest else None,
            "stale": bool(stale) or any(section["stale"] for section in sections.values()), "providers": providers,
            "local_embeddings": embedding_status(db),
            "attribution": {"tmdb": "This product uses the TMDB API but is not endorsed or certified by TMDB.",
                            "tvmaze": "TV data provided by TVmaze. Licensed under CC BY-SA.",
                            "justwatch": "Streaming availability powered by JustWatch via TMDB."}}


def newest_cache(cache: dict) -> str | None:
    newest = max((x.fetched_at for x in cache.values()), default=None)
    return newest.isoformat() if newest else None
