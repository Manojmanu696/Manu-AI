"""Read title metadata and regional offers published in JustWatch's title pages."""
from functools import lru_cache
from html.parser import HTMLParser
import json
import re
from time import time
from unicodedata import normalize
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def slug(value):
    ascii_name = normalize("NFKD", value.replace("×", "x")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.casefold()).strip("-")


# The catalogue uses these short or English titles for entries with a different URL.
ALIASES = {
    ("tv", "marvel-s-agents-of-s-h-i-e-l-d", 2013): ("marvels-agents-of-s-h-i-e-l-d",),
    ("tv", "money-heist", 2017): ("paperhouse",),
    ("anime", "code-geass", 2006): ("code-geass-lelouch-of-the-rebellion",),
    ("anime", "kaiji-ultimate-survivor", 2007): ("kaiji",),
    ("anime", "parasyte-the-maxim", 2014): ("parasyte",),
}
# Exact AniList identities with India availability documented by Crunchyroll's
# winter 2025 and fall 2026 lineups. These links open the corresponding episodes.
CRUNCHYROLL_INDIA = {
    "anilist:anime:170166": "https://www.crunchyroll.com/watch/GK9UG2Z72/so-time-begins-to-flow-again",
    "anilist:anime:205909": "https://www.crunchyroll.com/watch/GE00384155HIIN/an-unwanted-repayment",
}
RELEASE_YEARS = {("movie", "the-invisible-guest", 2016): "2017"}
ACCESS = {"ProvideService": "Subscription", "LeaseOut": "Rent", "Sell": "Buy"}


def public_url(value, host=None):
    if not isinstance(value, str):
        return None
    url = urlparse(value)
    if url.scheme == "https" and url.hostname and (host is None or url.hostname == host):
        return value
    return None


class TitlePage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_schema = False
        self.schema = []
        self.logos = {}
        self.no_offers = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if tag == "script":
            self.in_schema = attrs.get("type") == "application/ld+json"
        if "buybox-no-offers" in classes:
            self.no_offers = True
        if tag == "img" and "provider-icon" in classes:
            logo = public_url(attrs.get("src"), "images.justwatch.com")
            if logo and attrs.get("alt"):
                self.logos.setdefault(attrs["alt"], logo)

    def handle_data(self, value):
        if self.in_schema:
            self.schema.append(value)

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_schema = False


def parse_title(html, name, year, media_type, region):
    page = TitlePage()
    page.feed(html)
    try:
        graph = json.loads("".join(page.schema)).get("@graph", [])
    except (ValueError, AttributeError):
        return {}
    expected = "Movie" if media_type == "movie" else "TVSeries"
    record = next((node for node in graph if node.get("@type") == expected), {})
    title_slug = slug(name)
    accepted = (title_slug, *ALIASES.get((media_type, title_slug, year), ()))
    accepted_years = (str(year), RELEASE_YEARS.get((media_type, title_slug, year)))
    if slug(record.get("name") or "") not in accepted or (record.get("dateCreated") or "")[:4] not in accepted_years:
        return {}
    watch_url = public_url(record.get("@id"), "www.justwatch.com")
    if not watch_url or not urlparse(watch_url).path.startswith(f"/{region.lower()}/"):
        return {}
    image_id = (record.get("image") or {}).get("@id")
    poster = next((node.get("contentUrl") for node in graph if node.get("@id") == image_id), None)
    providers = {}
    audio_languages = set()
    for action in record.get("potentialAction") or []:
        offer = action.get("expectsAcceptanceOf") or {}
        if (offer.get("eligibleRegion") or {}).get("name") != region:
            continue
        for prop in offer.get("additionalProperty") or []:
            if prop.get("name") == "audioLanguage" and isinstance(prop.get("value"), list):
                audio_languages.update(str(code).lower() for code in prop["value"])
        provider = (offer.get("offeredBy") or {}).get("name")
        access = ACCESS.get((offer.get("businessFunction") or "").split("#")[-1], "Streaming")
        if access == "Subscription" and offer.get("price") == 0:
            access = "With ads" if provider and "with ads" in provider.casefold() else "Free"
        if provider:
            providers.setdefault((provider, access), {
                "name": provider, "access": access, "logo_url": page.logos.get(provider),
                "url": public_url((action.get("target") or {}).get("urlTemplate")),
            })

    seasons = record.get("containsSeason") or []
    season_count = record.get("numberOfSeasons")
    episodes = sum(season.get("numberOfEpisodes") or 0 for season in seasons if season.get("seasonNumber", 0) > 0)
    minutes = 0
    if duration := re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:\d+S)?", record.get("duration") or ""):
        minutes = int(duration[1] or 0) * 60 + int(duration[2] or 0)
    elif runtime := re.search(r'>Runtime</h3>(?:<!--[\s\S]*?-->|<[^>]+>|\s)*(?:(\d+)h\s*)?(\d+)min', html):
        minutes = int(runtime[1] or 0) * 60 + int(runtime[2])
    return {
        "image_url": public_url(poster, "images.justwatch.com"), "genres": ", ".join(record.get("genre") or []),
        "description": record.get("description"), "runtime": f"{minutes} min" if minutes and expected == "Movie" else None,
        "episode_duration": f"{minutes} min" if minutes and expected == "TVSeries" else None,
        "seasons": season_count, "episodes": episodes or None,
        "audio_languages": sorted(audio_languages), "providers": list(providers.values()), "watch_url": watch_url,
        "provider_data_available": bool(providers) or page.no_offers or (record.get("offers") or {}).get("offerCount") == 0,
    }


@lru_cache(maxsize=512)
def read_title(name, year, media_type, region, hour):
    key = slug(name)
    kind = "movie" if media_type == "movie" else "tv-show"
    for candidate in dict.fromkeys((key, *ALIASES.get((media_type, key, year), ()), f"{key}-{year}")):
        url = f"https://www.justwatch.com/{region.lower()}/{kind}/{candidate}"
        try:
            with urlopen(Request(url, headers={"User-Agent": "ManuAI/1.0 (personal media catalogue)"}), timeout=5) as response:
                if not public_url(response.geturl(), "www.justwatch.com"):
                    return {}
                html = response.read(2_500_000).decode("utf-8")
        except HTTPError as exc:
            if exc.code == 404:
                continue
            raise
        if result := parse_title(html, name, year, media_type, region):
            return result
    return {}


def title_listings(title, region):
    if not title.get("release_year") or not slug(title["title"]):
        return {}
    try:
        listings = read_title(title["title"], title["release_year"], title["media_type"], region, int(time() // 3600))
    except (OSError, ValueError, TypeError, AttributeError):
        listings = {}
    if region == "IN" and title["media_type"] == "anime" and not listings.get("providers"):
        url = CRUNCHYROLL_INDIA.get(title.get("external_id"))
        if url:
            return {**listings, "providers": [{"name": "Crunchyroll", "access": "Streaming", "url": url}],
                    "watch_url": url, "provider_source": "Crunchyroll", "provider_data_available": True,
                    "audio_languages": ["en"]}
    return listings
