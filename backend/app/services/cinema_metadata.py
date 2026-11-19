import json
from functools import lru_cache
from pathlib import Path
import re
import time
from urllib.parse import urlencode

from ..config import TMDB_API_KEY
from .discovery import _tmdb_get

DEMO_DETAILS = json.loads(Path(__file__).resolve().parents[1].joinpath("cinema_demo_metadata.json").read_text(encoding="utf-8"))
SCREEN_TYPES = ("movie", "tv", "anime")


def demo_details(item):
    if not item.is_demo:
        return {}
    return DEMO_DETAILS.get(f"{item.media_type}|{item.release_year}|{item.title}", {})


def identity(item):
    return item.media_type, item.release_year, item.title.strip().casefold()


def tmdb_image(path, size):
    return f"https://image.tmdb.org/t/p/{size}{path}" if path else ""


def tmdb_kind(media_type):
    return "movie" if media_type == "movie" else "tv"


def tmdb_summary(row, media_type):
    kind = tmdb_kind(media_type)
    item_id = row["id"]
    release = row.get("release_date") or row.get("first_air_date") or ""
    return {
        "id": item_id,
        "media_type": media_type,
        "title": row.get("title") or row.get("name") or "",
        "description": row.get("overview") or "",
        "release_year": int(release[:4]) if release[:4].isdigit() else None,
        "release_label": release,
        "image_url": tmdb_image(row.get("poster_path"), "w500"),
        "backdrop_url": tmdb_image(row.get("backdrop_path"), "w1280"),
        "public_rating": round(row["vote_average"], 1) if row.get("vote_count") else None,
        "rating_source": "TMDB",
        "external_id": f"tmdb:{item_id}",
        "source_url": f"https://www.themoviedb.org/{kind}/{item_id}",
    }


@lru_cache(maxsize=256)
def tmdb_details(media_type, item_id, region, hour):
    kind = tmdb_kind(media_type)
    row = _tmdb_get(f"/{kind}/{item_id}", {"append_to_response": "credits,videos,watch/providers,recommendations"})
    if not row:
        return {}
    item = tmdb_summary(row, media_type)
    credits = row.get("credits", {})
    videos = [video for video in row.get("videos", {}).get("results", [])
              if video.get("site") == "YouTube" and video.get("type") == "Trailer"
              and re.fullmatch(r"[\w-]{11}", video.get("key", ""))]
    trailer = next((video for video in videos if video.get("official")), videos[0] if videos else None)
    provider_groups = row.get("watch/providers", {}).get("results", {}).get(region, {})
    providers = [
        {"name": provider["provider_name"], "access": access}
        for group, access in (("flatrate", "Subscription"), ("free", "Free"), ("ads", "With ads"), ("rent", "Rent"), ("buy", "Buy"))
        for provider in provider_groups.get(group, [])
    ]
    related = []
    for candidate in row.get("recommendations", {}).get("results", []):
        candidate_type = media_type
        if kind == "tv":
            candidate_type = "anime" if candidate.get("original_language") == "ja" and 16 in candidate.get("genre_ids", []) else "tv"
        related.append(tmdb_summary(candidate, candidate_type))
    item.update(
        genres=", ".join(genre["name"] for genre in row.get("genres", [])),
        runtime=f"{row['runtime']} min" if row.get("runtime") else "",
        seasons=row.get("number_of_seasons"),
        episodes=row.get("number_of_episodes"),
        language=", ".join(language["english_name"] for language in row.get("spoken_languages", []) if language.get("english_name")),
        trailer_url=f"https://www.youtube.com/watch?{urlencode({'v': trailer['key']})}" if trailer else "",
        cast=[{"name": actor["name"], "role": actor.get("character", "")} for actor in credits.get("cast", [])[:12]],
        crew=[{"name": person["name"], "role": person["job"]} for person in credits.get("crew", [])
              if person["job"] in {"Director", "Writer", "Screenplay", "Director of Photography", "Original Music Composer"}][:10]
             + [{"name": person["name"], "role": "Creator"} for person in row.get("created_by", [])],
        providers=providers,
        watch_url=provider_groups.get("link", ""),
        region=region,
        provider_data_available="results" in row.get("watch/providers", {}),
        related=related[:8],
    )
    return item


def fetch_tmdb_details(media_type, item_id, region):
    return tmdb_details(media_type, item_id, region, int(time.time() // 3600)) if TMDB_API_KEY else {}


@lru_cache(maxsize=128)
def tmdb_search(query, media_type, hour):
    genres = {}
    for kind in (["movie", "tv"] if not media_type else [tmdb_kind(media_type)]):
        genres[kind] = {genre["id"]: genre["name"] for genre in _tmdb_get(f"/genre/{kind}/list").get("genres", [])}
    rows = _tmdb_get("/search/multi", {"query": query, "include_adult": "false"}).get("results", [])
    results = []
    for row in rows:
        kind = row.get("media_type")
        if kind not in genres:
            continue
        row_genres = row.get("genre_ids", [])
        target = "anime" if kind == "tv" and row.get("original_language") == "ja" and 16 in row_genres else kind
        if media_type and target != media_type:
            continue
        summary = tmdb_summary(row, target)
        summary["genres"] = ", ".join(genres[kind][key] for key in row_genres if key in genres[kind])
        results.append(summary)
    return results


def search_tmdb(query, media_type):
    return tmdb_search(query, media_type, int(time.time() // 3600))
