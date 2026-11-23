"""Keyless series lookup. TVmaze data is attributed in the title's source link."""
from functools import lru_cache
from html import unescape
import json
import re
from time import time
from urllib.parse import urlencode
from urllib.request import urlopen


@lru_cache(maxsize=128)
def request(path, params, hour):
    with urlopen(f"https://api.tvmaze.com/{path}?{urlencode(params)}", timeout=6) as response:
        return json.loads(response.read(2_000_000))


def summary(show):
    premiered = show.get("premiered") or ""
    runtime = show.get("averageRuntime") or show.get("runtime")
    media_type = "anime" if show.get("type") == "Animation" and show.get("language") == "Japanese" else "tv"
    return {
        "id": show["id"], "source": "tvmaze", "media_type": media_type,
        "title": show["name"], "description": unescape(re.sub("<[^>]+>", "", show.get("summary") or "")),
        "genres": ", ".join(show.get("genres") or []), "release_label": premiered,
        "release_year": int(premiered[:4]) if premiered[:4].isdigit() else None,
        "runtime": f"{runtime} min per episode" if runtime else "",
        "episode_duration": f"{runtime} min" if runtime else "",
        "language": show.get("language"), "image_url": (show.get("image") or {}).get("original"),
        "public_rating": (show.get("rating") or {}).get("average"), "rating_source": "TVmaze",
        "source_url": show.get("url"), "external_id": f"tvmaze:{show['id']}",
    }


def search_series(query):
    return [summary(row["show"]) for row in request("search/shows", (("q", query),), int(time() // 3600))[:10]]


def series_details(item_id):
    show = request(f"shows/{item_id}", (("embed[]", "cast"), ("embed[]", "episodes"), ("embed[]", "crew")), int(time() // 3600))
    embedded = show.get("_embedded", {})
    episodes = embedded.get("episodes", [])
    return {
        **summary(show),
        "episodes": len(episodes) or None,
        "seasons": len({episode["season"] for episode in episodes}) or None,
        "cast": [{"name": actor["person"]["name"], "role": actor["character"]["name"]}
                 for actor in embedded.get("cast", [])[:12]],
        "crew": [{"name": person["person"]["name"], "role": person["type"]}
                 for person in embedded.get("crew", [])[:10]],
    }
