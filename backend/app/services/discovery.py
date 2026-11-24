from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from ..config import TMDB_API_KEY, WEB_REQUEST_TIMEOUT_SECONDS
from ..models import CatalogueItem
from .evidence import FRESH_EXCLUSIONS, external_key, personal_media, same_work
from . import watch_listings, tvmaze
from .recommendations import feedback_by_title, meets_constraints, recommend_order, score_title, taste
from .internet import current_search_provider


def _terms(value: str | None) -> set[str]:
    return {x.strip().lower() for x in re.split(r"[,|;/]", value or "") if x.strip()}


def _tokens(value: str | None) -> set[str]:
    stop = {"the", "and", "with", "from", "that", "this", "your", "you", "best", "movies", "movie", "anime", "shows", "show"}
    return {x for x in re.findall(r"[a-z0-9]{3,}", (value or "").lower()) if x not in stop}


def score_catalogue_item(db: Session, candidate: CatalogueItem, evidence=None, feedback=None):
    evidence = taste(db) if evidence is None else evidence
    feedback = feedback_by_title(db) if feedback is None else feedback
    return score_title(candidate, evidence, feedback.get(candidate.id))


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


def _public_score(db: Session, item: dict, evidence=None):
    return score_title(item, taste(db) if evidence is None else evidence)


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
    evidence = taste(db)
    for row in candidates:
        try:
            tmdb_id = int(row["id"])
            detail = _tmdb_get(f"/{kind}/{tmdb_id}")
            title = detail.get("title") or detail.get("name") or row.get("title") or row.get("name") or "Untitled"
            genres = ", ".join(g.get("name", "") for g in detail.get("genres", []) if g.get("name"))
            classified_anime = kind == "tv" and detail.get("original_language") == "ja" and any(g.get("id") == 16 for g in detail.get("genres", []))
            if kind == "tv" and is_anime != classified_anime:
                continue
            languages = ", ".join(x.get("english_name", x.get("iso_639_1", "")) for x in detail.get("spoken_languages", []) if x.get("english_name") or x.get("iso_639_1"))
            runtime = detail.get("runtime")
            if runtime: runtime = f"{runtime} min"
            elif detail.get("episode_run_time"): runtime = f"{detail['episode_run_time'][0]} min/episode"
            provider_names, watch_url = _tmdb_providers(kind, tmdb_id)
            item = {
                "id": tmdb_id,
                "media_type": media_type,
                "title": title,
                "description": detail.get("overview") or row.get("overview") or "",
                "genres": genres,
                "tags": "public-web",
                "release_year": int((detail.get("release_date") or detail.get("first_air_date") or "0000")[:4]) or None,
                "image_url": f"https://image.tmdb.org/t/p/w500{detail.get('poster_path') or row.get('poster_path')}" if (detail.get("poster_path") or row.get("poster_path")) else "",
                "external_id": f"tmdb:{tmdb_id}",
                "external_url": f"https://www.themoviedb.org/{kind}/{tmdb_id}",
                "public_rating": round(float(detail.get("vote_average")), 1) if detail.get("vote_average") else None,
                "runtime": runtime or "",
                "ott_india": provider_names,
                "seasons": detail.get("number_of_seasons") if kind == "tv" else None,
                "episodes": detail.get("number_of_episodes") if kind == "tv" else None,
                "episode_duration": runtime or "",
                "languages": languages,
                "watch_url": watch_url or f"https://www.themoviedb.org/{kind}/{tmdb_id}/watch",
                "source_url": f"https://www.themoviedb.org/{kind}/{tmdb_id}",
                "source": "tmdb",
                "source_retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
            score, reasons = _public_score(db, item, evidence)
            output.append({"item": item, "score": score, "reasons": reasons, "source": "public_tmdb"})
        except Exception:
            continue
    return sorted(output, key=lambda x: x["score"], reverse=True)[:limit]


def discover(db: Session, media_type=None, limit=24, query=None, language=None, max_minutes=None):
    public_types = {"movie", "tv", "anime"}
    public_rows = _tmdb_discover(db, media_type, query, limit) if media_type in public_types else []
    q = db.query(CatalogueItem).filter_by(is_demo=False)
    if media_type:
        q = q.filter(CatalogueItem.media_type == media_type)
    catalogue = q.all()
    history = personal_media(db).all()
    feedback = feedback_by_title(db)
    hidden = [item for item in catalogue if feedback.get(item.id) in {"watched", "not_for_me"}]
    excluded = [item for item in history if item.status in FRESH_EXCLUSIONS or item.sentiment == "dislike" or item.personal_rating is not None] + hidden
    evidence = taste(db)
    tokens = _tokens(query)
    rows = []
    for item in catalogue:
        if tokens and not tokens & _tokens(" ".join([item.title, item.genres, item.tags, item.description])):
            continue
        score, reasons = score_catalogue_item(db, item, evidence, feedback)
        rows.append({"item": item, "score": score, "reasons": reasons, "source": "local_catalogue"})

    eligible = []
    budget = 6
    for row in sorted([*public_rows, *rows], key=lambda row: -row["score"]):
        item = row["item"]
        if any(same_work(item, prior["item"]) for prior in eligible):
            continue
        if not query and any(item is other or same_work(item, other) for other in excluded):
            continue
        if not meets_constraints(item, language, max_minutes):
            if not budget or (item["media_type"] if isinstance(item, dict) else item.media_type) not in public_types:
                continue
            budget -= 1
            title = dict(item) if isinstance(item, dict) else {
                column.name: getattr(item, column.name) for column in CatalogueItem.__table__.columns
            }
            if (key := external_key(title)) and key[0] == "tvmaze":
                try:
                    title.update({name: value for name, value in tvmaze.series_details(int(key[1])).items()
                                  if name in {"language", "episode_duration", "episodes"} and value})
                except OSError:
                    pass
            info = watch_listings.title_listings(title, "IN")
            title.update({name: value for name, value in info.items()
                          if name in {"audio_languages", "language", "episode_duration", "episodes", "runtime"} and value})
            if not meets_constraints(title, language, max_minutes):
                continue
            row = {**row, "item": title}
        eligible.append(row)
    return recommend_order(eligible, limit, diversify=not query)


def web_discover(query: str, limit: int = 8) -> list[dict]:
    results = current_search_provider().search(query, limit=limit)
    return [{"title": r.title, "url": r.url, "snippet": r.snippet, "provider": r.provider, "source": "web"} for r in results]
