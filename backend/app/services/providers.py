"""Provider adapters for public movie and television catalogues.

All provider I/O is server-side. Adapters return normalized, source-attributed
records and never receive a user's private memories or library.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from html import unescape
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..config import TMDB_API_KEY, WEB_REQUEST_TIMEOUT_SECONDS

log = logging.getLogger(__name__)
_NETWORK_LIMIT = threading.BoundedSemaphore(4)
_GENRES: dict[str, dict[int, str]] = {}


def request_json(url: str, *, method: str = "GET", payload: dict | None = None, headers: dict | None = None,
                 timeout_seconds: float | None = None, max_attempts: int = 3) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=data, method=method, headers={
        "Accept": "application/json", "Content-Type": "application/json",
        "User-Agent": "ManuAI/1.0 (local-first discovery)", **(headers or {}),
    })
    last_error: Exception | None = None
    attempts = max(1, min(max_attempts, 3))
    for attempt in range(attempts):
        try:
            with _NETWORK_LIMIT, urlopen(request, timeout=timeout_seconds or WEB_REQUEST_TIMEOUT_SECONDS) as response:
                raw = response.read(2_000_000)
                return json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            last_error = exc
            if exc.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
            retry_after = exc.headers.get("Retry-After", "")
            delay = min(float(retry_after) if retry_after.isdigit() else 0.6 * (2 ** attempt), 8.0)
            time.sleep(delay)
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise
            time.sleep(min(0.4 * (2 ** attempt), 4.0))
    raise RuntimeError("Provider request failed") from last_error


def _tmdb(path: str, params: dict | None = None) -> dict:
    if not TMDB_API_KEY:
        raise RuntimeError("TMDB_API_KEY is not configured")
    query = {"api_key": TMDB_API_KEY, "language": "en-US", **(params or {})}
    return request_json(f"https://api.themoviedb.org/3{path}?{urlencode(query)}")


def _tmdb_rows(kind: str, rows: list[dict], genres: dict[int, str], section: str) -> list[dict]:
    normalized = []
    for row in rows:
        provider_id = row.get("id")
        if not provider_id:
            continue
        media = "tv" if kind == "tv" else "movie"
        genre_ids = row.get("genre_ids") or []
        title = row.get("title") or row.get("name") or row.get("original_title") or row.get("original_name")
        release = row.get("release_date") or row.get("first_air_date") or ""
        normalized.append({
            "media_type": media, "title": title or "Untitled",
            "original_title": row.get("original_title") or row.get("original_name") or "",
            "description": row.get("overview") or "",
            "genres": ", ".join(genres[g] for g in genre_ids if g in genres),
            "genre_ids_json": json.dumps(genre_ids), "tags": "",
            "release_year": int(release[:4]) if release[:4].isdigit() else None,
            "image_url": f"https://image.tmdb.org/t/p/w500{row['poster_path']}" if row.get("poster_path") else "",
            "backdrop_url": f"https://image.tmdb.org/t/p/w1280{row['backdrop_path']}" if row.get("backdrop_path") else "",
            "external_id": f"tmdb:{media}:{provider_id}", "provider_id": str(provider_id),
            "source_provider": "tmdb", "external_url": f"https://www.themoviedb.org/{media}/{provider_id}",
            "source_url": f"https://www.themoviedb.org/{media}/{provider_id}",
            "imdb_rating": round(float(row.get("vote_average") or 0), 1) or None,
            "public_rating": round(float(row.get("vote_average") or 0), 1) or None,
            "vote_count": int(row.get("vote_count") or 0), "popularity": row.get("popularity"),
            "original_language": row.get("original_language") or "",
            "countries_json": json.dumps(row.get("origin_country") or []),
            "series_status": "", "section": section, "source": "TMDB",
        })
    return normalized


class TMDBProvider:
    name = "tmdb"

    def health(self) -> dict:
        if not TMDB_API_KEY:
            return {"status": "not_configured", "message": "Add TMDB_API_KEY to .env to enable movie and TV discovery."}
        try:
            _tmdb("/configuration")
            return {"status": "ok", "message": "TMDB is reachable."}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:240]}

    def fetch_sections(self) -> dict[str, list[dict]]:
        self.errors = {}
        if not TMDB_API_KEY:
            return {}
        movie_genres = {x["id"]: x["name"] for x in _tmdb("/genre/movie/list").get("genres", [])}
        tv_genres = {x["id"]: x["name"] for x in _tmdb("/genre/tv/list").get("genres", [])}
        _GENRES["movie"], _GENRES["tv"] = movie_genres, tv_genres
        specs: dict[str, tuple[str, str, dict]] = {
            "trending_movies": ("/trending/movie/week", "movie", {}),
            "trending_tv": ("/trending/tv/week", "tv", {}),
            "popular_movies": ("/movie/popular", "movie", {"region": "IN"}),
            "popular_tv": ("/tv/popular", "tv", {}),
            "now_playing": ("/movie/now_playing", "movie", {"region": "IN"}),
            "upcoming_movies": ("/movie/upcoming", "movie", {"region": "IN"}),
            "top_rated_movies": ("/movie/top_rated", "movie", {}),
            "top_rated_tv": ("/tv/top_rated", "tv", {}),
            "recent_releases": ("/discover/movie", "movie", {"region": "IN", "primary_release_date.gte": (date.today() - timedelta(days=60)).isoformat(),
                                                                 "primary_release_date.lte": date.today().isoformat(), "sort_by": "primary_release_date.desc",
                                                                 "vote_count.gte": 10}),
            "hidden_gems": ("/discover/movie", "movie", {"sort_by": "vote_average.desc", "vote_count.gte": 25, "vote_count.lte": 1000, "vote_average.gte": 7.0}),
            "psychological_thrillers": ("/discover/movie", "movie", {"with_genres": "53,9648", "sort_by": "vote_average.desc", "vote_count.gte": 80}),
            "mind_games": ("/discover/movie", "movie", {"with_genres": "878,9648", "sort_by": "popularity.desc", "vote_count.gte": 30}),
            "intelligent_stories": ("/discover/movie", "movie", {"with_genres": "9648,80", "sort_by": "vote_average.desc", "vote_count.gte": 60}),
            "short_movies": ("/discover/movie", "movie", {"with_runtime.lte": 115, "sort_by": "popularity.desc", "vote_count.gte": 30}),
            "short_completed_series": ("/discover/tv", "tv", {"with_status": 4, "with_runtime.lte": 45, "sort_by": "vote_average.desc", "vote_count.gte": 50}),
        }
        def fetch_one(name, spec):
            path, kind, params = spec
            try:
                payload = _tmdb(path, {"page": 1, **params})
                return name, _tmdb_rows(kind, (payload.get("results") or [])[:24], movie_genres if kind == "movie" else tv_genres, name), ""
            except Exception as exc:
                log.exception("TMDB section fetch failed: %s", name)
                return name, [], str(exc)[:240]
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="tmdb-section") as executor:
            fetched = list(executor.map(lambda pair: fetch_one(*pair), specs.items()))
        self.errors = {name: error for name, _, error in fetched if error}
        sections = {name: rows for name, rows, _ in fetched}
        return sections

    def details(self, item: dict) -> dict:
        kind, provider_id = item.get("media_type"), item.get("provider_id")
        if kind not in {"movie", "tv"} or not str(provider_id or "").isdigit():
            return item
        paths = {"detail": (f"/{kind}/{provider_id}", {"append_to_response": "videos,credits"}),
                 "watch": (f"/{kind}/{provider_id}/watch/providers", {}), "similar": (f"/{kind}/{provider_id}/similar", {"page": 1})}
        results = {}
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="tmdb-detail") as executor:
            futures = {key: executor.submit(_tmdb, path, params) for key, (path, params) in paths.items()}
            results["detail"] = futures["detail"].result()
            for key in ("watch", "similar"):
                try: results[key] = futures[key].result()
                except Exception as exc:
                    log.info("TMDB optional %s detail unavailable for %s: %s", key, provider_id, exc)
                    results[key] = None
        detail = results["detail"]
        regions = (results["watch"] or {}).get("results", {}).get("IN", {})
        video = next((v for v in detail.get("videos", {}).get("results", []) if v.get("site") == "YouTube" and v.get("type") == "Trailer"), None)
        providers = []
        for group in ("flatrate", "free", "ads", "rent", "buy"):
            for provider in regions.get(group, []) or []:
                providers.append({"name": provider.get("provider_name"), "type": group, "logo": f"https://image.tmdb.org/t/p/w92{provider['logo_path']}" if provider.get("logo_path") else ""})
        credits = detail.get("credits", {})
        directors = [x.get("name") for x in credits.get("crew", []) if x.get("job") == "Director"]
        genre_map = {g.get("id"): g.get("name", "") for g in detail.get("genres", [])}
        _GENRES.setdefault(kind, {}).update(genre_map)
        similar_rows = (results["similar"] or {}).get("results", [])[:16] if results["similar"] else []
        similar_items = _tmdb_rows(kind, similar_rows, _GENRES[kind], "similar")
        item.update({
            "genres": ", ".join(g.get("name", "") for g in detail.get("genres", [])),
            "runtime": f"{detail.get('runtime')} min" if detail.get("runtime") else (f"{detail['episode_run_time'][0]} min/episode" if detail.get("episode_run_time") else ""),
            "runtime_minutes": detail.get("runtime") or (detail.get("episode_run_time") or [None])[0],
            "seasons": detail.get("number_of_seasons"), "episodes": detail.get("number_of_episodes"),
            "series_status": detail.get("status") or "", "trailer_url": f"https://www.youtube.com/watch?v={video['key']}" if video else "",
            "countries_json": json.dumps([x.get("iso_3166_1") for x in detail.get("production_countries", []) if x.get("iso_3166_1")]),
            "watch_url": regions.get("link") or item.get("watch_url") or f"https://www.themoviedb.org/{kind}/{provider_id}/watch",
            "credits_json": json.dumps({"cast": [x.get("name") for x in credits.get("cast", [])[:10]], "directors": directors[:3], "creators": [x.get("name") for x in detail.get("created_by", [])]}),
            "backdrop_url": f"https://image.tmdb.org/t/p/w1280{detail['backdrop_path']}" if detail.get("backdrop_path") else item.get("backdrop_url", ""),
            "source_retrieved_at": date.today().isoformat(), "source_url": f"https://www.themoviedb.org/{kind}/{provider_id}",
            "similar_items": similar_items if results["similar"] is not None else None,
        })
        if results["watch"] is not None:
            item["watch_providers_json"] = json.dumps(providers)
            item["ott_india"] = ", ".join(dict.fromkeys(p["name"] for p in providers if p.get("name")))
        return item


class AniListProvider:
    name = "anilist"
    endpoint = "https://graphql.anilist.co"

    def health(self) -> dict:
        try:
            request_json(self.endpoint, method="POST", payload={"query": "{ Page(page:1,perPage:1){ media(type:ANIME,isAdult:false){ id } } }"})
            return {"status": "ok", "message": "AniList is reachable."}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:240]}

    @staticmethod
    def _season() -> tuple[str, int]:
        month = date.today().month
        return ("WINTER" if month in (1, 2, 3) else "SPRING" if month in (4, 5, 6) else "SUMMER" if month in (7, 8, 9) else "FALL", date.today().year)

    def fetch_sections(self) -> dict[str, list[dict]]:
        season, year = self._season()
        query = """query($season:MediaSeason,$year:Int,$sort:[MediaSort]) {
          Page(page:1,perPage:24) { media(type:ANIME,isAdult:false,season:$season,seasonYear:$year,sort:$sort) {
            id title { romaji english } description(asHtml:false) genres format status averageScore episodes duration countryOfOrigin
            startDate { year } coverImage { large } bannerImage siteUrl popularity
          } }
        }"""
        def load(sort: str, seasonal: bool, label: str):
            variables = {"season": season if seasonal else None, "year": year if seasonal else None, "sort": [sort]}
            response = request_json(self.endpoint, method="POST", payload={"query": query, "variables": variables})
            data = response.get("data", {}).get("Page", {}).get("media", [])
            rows = []
            for row in data:
                title = (row.get("title") or {}).get("english") or (row.get("title") or {}).get("romaji")
                aid = str(row.get("id"))
                rows.append({
                    "media_type": "anime", "title": title or "Untitled", "original_title": (row.get("title") or {}).get("romaji") or "",
                    "description": row.get("description") or "", "genres": ", ".join(row.get("genres") or []),
                    "tags": ", ".join(row.get("genres") or []), "release_year": (row.get("startDate") or {}).get("year"),
                    "image_url": (row.get("coverImage") or {}).get("large") or "", "backdrop_url": row.get("bannerImage") or "",
                    "external_id": f"anilist:anime:{aid}", "source_provider": "anilist", "provider_id": aid,
                    "external_url": row.get("siteUrl") or f"https://anilist.co/anime/{aid}", "source_url": row.get("siteUrl") or f"https://anilist.co/anime/{aid}",
                    "public_rating": (row.get("averageScore") or 0) / 10 or None, "vote_count": 0, "popularity": row.get("popularity"),
                    "episodes": row.get("episodes"), "runtime": f"{row['duration']} min/episode" if row.get("duration") else "",
                    "runtime_minutes": row.get("duration"), "episode_duration": f"{row['duration']} min" if row.get("duration") else "",
                    "series_status": row.get("status") or "", "source": "AniList", "section": label,
                    "original_language": "ja", "countries_json": json.dumps([row.get("countryOfOrigin")] if row.get("countryOfOrigin") else []),
                    "source_retrieved_at": date.today().isoformat(),
                })
            return rows
        sections = {}
        self.errors = {}
        try: sections["popular_anime"] = load("TRENDING_DESC", False, "popular_anime")
        except Exception as exc:
            self.errors["popular_anime"] = str(exc)[:240]
            log.exception("AniList popular anime fetch failed")
        try: sections["seasonal_anime"] = load("POPULARITY_DESC", True, "seasonal_anime")
        except Exception as exc:
            self.errors["seasonal_anime"] = str(exc)[:240]
            log.exception("AniList seasonal anime fetch failed")
        return sections

    def search(self, query_text: str, limit: int = 24) -> list[dict]:
        query = """query($search:String,$perPage:Int) { Page(page:1,perPage:$perPage) { media(type:ANIME,isAdult:false,search:$search) {
          id title { romaji english } description(asHtml:false) genres status averageScore episodes duration countryOfOrigin
          startDate { year } coverImage { large } bannerImage siteUrl popularity
        } } }"""
        response = request_json(self.endpoint, method="POST", payload={"query": query, "variables": {"search": query_text, "perPage": min(limit, 30)}})
        output = []
        for row in response.get("data", {}).get("Page", {}).get("media", []):
            aid = str(row.get("id")); title_data = row.get("title") or {}
            title = title_data.get("english") or title_data.get("romaji") or "Untitled"
            output.append({"media_type": "anime", "title": title, "original_title": title_data.get("romaji") or "",
                "description": row.get("description") or "", "genres": ", ".join(row.get("genres") or []),
                "tags": ", ".join(row.get("genres") or []), "release_year": (row.get("startDate") or {}).get("year"),
                "image_url": (row.get("coverImage") or {}).get("large") or "", "backdrop_url": row.get("bannerImage") or "",
                "external_id": f"anilist:anime:{aid}", "provider_id": aid, "source_provider": "anilist",
                "external_url": row.get("siteUrl") or f"https://anilist.co/anime/{aid}", "source_url": row.get("siteUrl") or f"https://anilist.co/anime/{aid}",
                "public_rating": (row.get("averageScore") or 0) / 10 or None, "vote_count": 0, "episodes": row.get("episodes"),
                "runtime": f"{row['duration']} min/episode" if row.get("duration") else "", "runtime_minutes": row.get("duration"),
                "episode_duration": f"{row['duration']} min" if row.get("duration") else "",
                "series_status": row.get("status") or "", "original_language": "ja",
                "countries_json": json.dumps([row.get("countryOfOrigin")] if row.get("countryOfOrigin") else []),
                "source": "AniList", "section": "search"})
        return output


class TVMazeProvider:
    name = "tvmaze"
    base = "https://api.tvmaze.com"

    def health(self) -> dict:
        try:
            request_json(f"{self.base}/shows?page=0")
            return {"status": "ok", "message": "TVmaze is reachable. Free API responses are cached for at least 60 minutes."}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:240]}

    def fetch_sections(self) -> dict[str, list[dict]]:
        try:
            rows = request_json(f"{self.base}/shows?page=0")
            self.errors = {}
            output = []
            for row in rows[:80]:
                sid = str(row.get("id"))
                image = row.get("image") or {}
                premiered = row.get("premiered") or ""
                summary = unescape(re.sub(r"<[^>]+>", " ", row.get("summary") or ""))
                output.append({
                    "media_type": "tv", "title": row.get("name") or "Untitled", "original_title": "",
                    "description": re.sub(r"\s+", " ", summary).strip()[:4000],
                    "genres": ", ".join(row.get("genres") or []), "tags": "", "release_year": int(premiered[:4]) if premiered[:4].isdigit() else None,
                    "image_url": image.get("medium") or "", "backdrop_url": image.get("original") or "",
                    "external_id": f"tvmaze:tv:{sid}", "provider_id": sid, "source_provider": "tvmaze",
                    "external_url": row.get("url") or "", "source_url": row.get("url") or "", "public_rating": (row.get("rating") or {}).get("average"),
                    "vote_count": 0, "runtime": f"{row['runtime']} min" if row.get("runtime") else "",
                    "runtime_minutes": row.get("runtime"), "original_language": row.get("language") or "",
                    "series_status": row.get("status") or "", "countries_json": json.dumps([((row.get("network") or {}).get("country") or {}).get("code")] if ((row.get("network") or {}).get("country") or {}).get("code") else []),
                    "source": "TVmaze", "section": "tvmaze_catalogue",
                })
            return {"tvmaze_catalogue": output}
        except Exception as exc:
            self.errors = {"tvmaze_catalogue": str(exc)[:240]}
            log.exception("TVmaze catalogue fetch failed")
            return {}

    def search(self, query: str, limit: int = 24) -> list[dict]:
        results = request_json(f"{self.base}/search/shows?{urlencode({'q': query})}")
        output = []
        for result in results[:limit]:
            row = result.get("show") or {}; sid = str(row.get("id")); image = row.get("image") or {}
            premiered = row.get("premiered") or ""; summary = unescape(re.sub(r"<[^>]+>", " ", row.get("summary") or ""))
            output.append({"media_type": "tv", "title": row.get("name") or "Untitled", "description": re.sub(r"\s+", " ", summary).strip()[:4000],
                "genres": ", ".join(row.get("genres") or []), "tags": "", "release_year": int(premiered[:4]) if premiered[:4].isdigit() else None,
                "image_url": image.get("medium") or "", "backdrop_url": image.get("original") or "", "external_id": f"tvmaze:tv:{sid}",
                "provider_id": sid, "source_provider": "tvmaze", "external_url": row.get("url") or "", "source_url": row.get("url") or "",
                "public_rating": (row.get("rating") or {}).get("average"), "vote_count": 0, "runtime": f"{row['runtime']} min" if row.get("runtime") else "",
                "runtime_minutes": row.get("runtime"), "original_language": row.get("language") or "", "series_status": row.get("status") or "",
                "countries_json": json.dumps([((row.get("network") or {}).get("country") or {}).get("code")] if ((row.get("network") or {}).get("country") or {}).get("code") else []),
                "source": "TVmaze", "section": "search"})
        return output

    def details(self, item: dict) -> dict:
        provider_id = str(item.get("provider_id") or "")
        if not provider_id.isdigit():
            raise ValueError("Invalid TVmaze provider identifier")
        embedded = request_json(f"{self.base}/shows/{provider_id}?{urlencode([('embed[]', 'episodes'), ('embed[]', 'cast')])}")
        data = embedded.get("_embedded", {})
        episodes = data.get("episodes", [])
        cast = [entry.get("person", {}).get("name") for entry in data.get("cast", []) if entry.get("person", {}).get("name")]
        item.update({
            "genres": ", ".join(embedded.get("genres") or item.get("genres", "").split(", ")),
            "runtime": f"{embedded.get('runtime')} min" if embedded.get("runtime") else item.get("runtime", ""),
            "runtime_minutes": embedded.get("runtime") or item.get("runtime_minutes"),
            "seasons": len({episode.get("season") for episode in episodes if episode.get("season") is not None}) or item.get("seasons"),
            "episodes": len(episodes) or item.get("episodes"),
            "series_status": embedded.get("status") or item.get("series_status", ""),
            "credits_json": json.dumps({"cast": cast[:20], "directors": [], "creators": []}),
            "episode_details_json": json.dumps([{"season": ep.get("season"), "number": ep.get("number"), "name": ep.get("name"),
                                                  "airdate": ep.get("airdate"), "runtime": ep.get("runtime")}
                                                 for ep in episodes[:40]]),
            "schedule_json": json.dumps(embedded.get("schedule") or {}),
            "countries_json": json.dumps([((embedded.get("network") or embedded.get("webChannel") or {}).get("country") or {}).get("code")] if ((embedded.get("network") or embedded.get("webChannel") or {}).get("country") or {}).get("code") else []),
            "source_retrieved_at": date.today().isoformat(),
        })
        return item
