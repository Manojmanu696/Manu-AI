from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from ..config import TMDB_API_KEY, WEB_REQUEST_TIMEOUT_SECONDS
from ..models import CatalogueItem, MediaItem, Memory, RecommendationFeedback
from .internet import current_search_provider


def _terms(value: str | None) -> set[str]:
    return {x.strip().lower() for x in re.split(r"[,|;/]", value or "") if x.strip()}


def _tokens(value: str | None) -> set[str]:
    stop = {"the", "and", "with", "from", "that", "this", "your", "you", "best", "movies", "movie", "anime", "shows", "show"}
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
        if "filler" in candidate.tags.lower(): score -= 12
    for event in db.query(RecommendationFeedback).filter_by(catalogue_item_id=candidate.id).all():
        score += {"like": 7, "watchlist": 5, "watched": -4, "not_for_me": -18}.get(event.action, 0)
    if candidate.imdb_rating:
        score += min(8, max(0, candidate.imdb_rating - 7) * 2)
    if not reasons: reasons.append("A new candidate selected for exploration")
    return max(1, min(99, round(score))), reasons[:3]


def _tmdb_get(path: str, params: dict[str, str] | None = None) -> dict:
    if not TMDB_API_KEY:
        return {}
    query = dict(params or {})
    query["api_key"] = TMDB_API_KEY
    query.setdefault("language", "en-US")
    url = f"https://api.themoviedb.org/3{path}?{urlencode(query)}"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "ManuAI/1.0"})
    with urlopen(request, timeout=WEB_REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read(1_500_000).decode("utf-8"))


def _tmdb_providers(kind: str, item_id: int) -> tuple[str, str]:
    try:
        payload = _tmdb_get(f"/{kind}/{item_id}/watch/providers")
        region = payload.get("results", {}).get("IN", {})
        names: list[str] = []
        for group in ("flatrate", "free", "ads", "rent", "buy"):
            for provider in region.get(group, []) or []:
                name = provider.get("provider_name")
                if name and name not in names: names.append(name)
        return ", ".join(names[:8]), region.get("link", "")
    except Exception:
        return "", ""


def _public_score(db: Session, item: dict) -> tuple[int, list[str]]:
    liked_genres, _, disliked_genres, memory_text = _taste(db)
    genres = _terms(item.get("genres", ""))
    score = 55
    reasons: list[str] = []
    hits = genres & set(liked_genres)
    avoid = genres & set(disliked_genres)
    if hits:
        score += min(25, 6 * sum(liked_genres[g] for g in hits))
        reasons.append(f"Matches genres you repeatedly enjoy: {', '.join(sorted(hits)[:3])}")
    if avoid:
        score -= min(18, 6 * len(avoid))
    searchable = " ".join(str(item.get(k, "")) for k in ("title", "description", "genres", "tags")).lower()
    hits_memory = [t for t in _tokens(memory_text) if t in searchable]
    if hits_memory:
        score += min(16, 3 * len(hits_memory))
        reasons.append("Matches your saved taste profile")
    rating = item.get("imdb_rating") or item.get("public_rating")
    if rating: score += min(8, max(0, float(rating) - 7) * 2)
    if not reasons: reasons.append("Selected from current public catalog data")
    return max(1, min(99, round(score))), reasons[:3]


def _tmdb_discover(db: Session, media_type: str, query: str | None, limit: int) -> list[dict]:
    if not TMDB_API_KEY or media_type not in {"movie", "tv", "anime"}:
        return []
    is_anime = media_type == "anime"
    kind = "tv" if media_type in {"tv", "anime"} else "movie"
    generic = not query or len(_tokens(query)) == 0
    try:
        if is_anime and generic:
            payload = _tmdb_get("/discover/tv", {"with_genres": "16", "with_original_language": "ja", "sort_by": "vote_average.desc", "vote_count.gte": "100"})
        elif generic:
            payload = _tmdb_get(f"/discover/{kind}", {"sort_by": "popularity.desc", "vote_count.gte": "100"})
        else:
            payload = _tmdb_get(f"/search/{kind}", {"query": query or ""})
        candidates = (payload.get("results") or [])[: max(limit * 2, 12)]
    except Exception:
        return []

    output: list[dict] = []
    for row in candidates:
        try:
            tmdb_id = int(row["id"])
            detail = _tmdb_get(f"/{kind}/{tmdb_id}")
            title = detail.get("title") or detail.get("name") or row.get("title") or row.get("name") or "Untitled"
            genres = ", ".join(g.get("name", "") for g in detail.get("genres", []) if g.get("name"))
            if is_anime and "Animation" not in genres: genres = f"Animation, {genres}" if genres else "Animation"
            languages = ", ".join(x.get("english_name", x.get("iso_639_1", "")) for x in detail.get("spoken_languages", []) if x.get("english_name") or x.get("iso_639_1"))
            runtime = detail.get("runtime")
            if runtime: runtime = f"{runtime} min"
            elif detail.get("episode_run_time"): runtime = f"{detail['episode_run_time'][0]} min/episode"
            provider_names, watch_url = _tmdb_providers(kind, tmdb_id)
            item = {
                "id": -tmdb_id,
                "media_type": media_type,
                "title": title,
                "description": detail.get("overview") or row.get("overview") or "",
                "genres": genres,
                "tags": "public-web",
                "release_year": int((detail.get("release_date") or detail.get("first_air_date") or "0000")[:4]) or None,
                "image_url": f"https://image.tmdb.org/t/p/w500{detail.get('poster_path') or row.get('poster_path')}" if (detail.get("poster_path") or row.get("poster_path")) else "",
                "external_id": f"tmdb:{tmdb_id}",
                "external_url": f"https://www.themoviedb.org/{kind}/{tmdb_id}",
                "imdb_rating": round(float(detail.get("vote_average")), 1) if detail.get("vote_average") else None,
                "public_rating": round(float(detail.get("vote_average")), 1) if detail.get("vote_average") else None,
                "runtime": runtime or "",
                "ott_india": provider_names or "Not available in India",
                "seasons": detail.get("number_of_seasons") if kind == "tv" else None,
                "episodes": detail.get("number_of_episodes") if kind == "tv" else None,
                "episode_duration": runtime or "",
                "languages": languages,
                "watch_url": watch_url or f"https://www.themoviedb.org/{kind}/{tmdb_id}/watch",
                "source_url": f"https://www.themoviedb.org/{kind}/{tmdb_id}",
                "source": "tmdb",
                "source_retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
            score, reasons = _public_score(db, item)
            output.append({"item": item, "score": score, "reasons": reasons, "source": "public_tmdb"})
        except Exception:
            continue
    return sorted(output, key=lambda x: x["score"], reverse=True)[:limit]


def discover(db: Session, media_type: str | None = None, limit: int = 24, query: str | None = None) -> list[dict]:
    public_types = {"movie", "tv", "anime"}
    public_rows = _tmdb_discover(db, media_type, query, limit) if media_type in public_types else []
    q = db.query(CatalogueItem)
    if media_type: q = q.filter(CatalogueItem.media_type == media_type)
    rows = q.all()
    owned = {x.title.strip().lower() for x in db.query(MediaItem).all()}
    if query:
        tokens = _tokens(query)
        rows = [x for x in rows if not tokens or tokens & _tokens(" ".join([x.title, x.genres, x.tags, x.description]))]
    rows = [x for x in rows if x.title.strip().lower() not in owned]
    ranked = list(public_rows)
    for item in rows:
        score, reasons = score_catalogue_item(db, item)
        ranked.append({"item": item, "score": score, "reasons": reasons, "source": "local_catalogue"})
    # Public results win when available; local candidates remain a fallback/context source.
    return sorted(ranked, key=lambda x: x["score"], reverse=True)[:limit]


def web_discover(query: str, limit: int = 8) -> list[dict]:
    results = current_search_provider().search(query, limit=limit)
    return [{"title": r.title, "url": r.url, "snippet": r.snippet, "provider": r.provider, "source": "web"} for r in results]
