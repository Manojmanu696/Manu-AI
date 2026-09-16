"""Read-only public web search/fetch providers for Manu AI."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from html import unescape
from html.parser import HTMLParser
import ipaddress, json, re, socket
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from ..config import BRAVE_API_KEY, SERPER_API_KEY, WEB_REQUEST_TIMEOUT_SECONDS, WEB_SEARCH_PROVIDER

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/146 Safari/537.36 ManuAI/1.0"


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    provider: str = ""

    def to_dict(self):
        return asdict(self)


class WebSearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, limit: int = 8) -> list[SearchResult]: ...


def _safe(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
            return False
        if p.hostname.lower() in {"localhost", "localhost.localdomain"}:
            return False
        for addr in socket.getaddrinfo(p.hostname, None, type=socket.SOCK_STREAM):
            ip = ipaddress.ip_address(addr[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True
    except (OSError, ValueError):
        return False


def _http(url: str, method="GET", data: bytes | None = None, headers: dict[str, str] | None = None) -> str:
    h = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/json",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    h.update(headers or {})
    with urlopen(Request(url, data=data, method=method, headers=h), timeout=WEB_REQUEST_TIMEOUT_SECONDS) as response:
        return response.read(2_000_000).decode(response.headers.get_content_charset() or "utf-8", errors="replace")


class DuckParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.url = ""
        self.title = []
        self.snippet = []
        self.in_title = False
        self.in_snippet = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        c = a.get("class", "") or ""
        if tag == "a" and "result__a" in c:
            raw = a.get("href", "") or ""
            p = urlparse(raw)
            self.url = unquote(parse_qs(p.query).get("uddg", [raw])[0])
            self.title = []
            self.snippet = []
            self.in_title = True
        elif "result__snippet" in c:
            self.in_snippet = True

    def handle_data(self, d):
        if self.in_title:
            self.title.append(d)
        if self.in_snippet:
            self.snippet.append(d)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_title:
            title = " ".join(self.title).strip()
            if title and _safe(self.url):
                self.results.append(SearchResult(
                    unescape(title), self.url,
                    unescape(" ".join(self.snippet).strip()), "duckduckgo"
                ))
            self.in_title = False
        if self.in_snippet and tag in {"div", "span"}:
            self.in_snippet = False


class BingParser(HTMLParser):
    """Small parser for Bing's public HTML result page.

    Bing is used as a no-key fallback because some hosted environments/IPs
    receive an empty/403 response from DuckDuckGo's HTML endpoint.
    """
    def __init__(self):
        super().__init__()
        self.results: list[SearchResult] = []
        self.in_result = False
        self.in_title = False
        self.in_snippet = False
        self.current_url = ""
        self.title: list[str] = []
        self.snippet: list[str] = []
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "") or ""
        if tag == "li" and "b_algo" in cls:
            self.in_result = True
            self.depth = 1
            self.current_url = ""
            self.title = []
            self.snippet = []
        elif self.in_result and tag == "li":
            self.depth += 1
        if self.in_result and tag == "a" and not self.current_url:
            href = a.get("href", "") or ""
            if href.startswith(("http://", "https://")):
                self.current_url = href
        if self.in_result and tag == "h2":
            self.in_title = True
        if self.in_result and tag == "p":
            self.in_snippet = True

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if self.in_snippet:
            self.snippet.append(data)

    def handle_endtag(self, tag):
        if tag == "h2":
            self.in_title = False
        if tag == "p":
            self.in_snippet = False
        if tag == "li" and self.in_result:
            self.depth -= 1
            if self.depth <= 0:
                title = unescape(" ".join(self.title).strip())
                snippet = unescape(" ".join(self.snippet).strip())
                if title and _safe(self.current_url):
                    self.results.append(SearchResult(title, self.current_url, snippet, "bing"))
                self.in_result = False
                if len(self.results) >= 20:
                    return


class BingSearch(WebSearchProvider):
    def search(self, query, limit=8):
        url = "https://www.bing.com/search?" + urlencode({"q": query[:500], "cc": "in", "setlang": "en"})
        html = _http(url)
        parser = BingParser()
        parser.feed(html)
        return parser.results[:limit]


class DuckDuckGoSearch(WebSearchProvider):
    def search(self, query, limit=8):
        q = quote_plus(query[:500])
        fails = []
        for url, method, data in [
            ("https://html.duckduckgo.com/html/", "POST", f"q={q}&kl=in-en&kp=-1".encode()),
            (f"https://html.duckduckgo.com/html/?q={q}", "GET", None),
            (f"https://lite.duckduckgo.com/lite/?q={q}", "GET", None),
        ]:
            try:
                html = _http(
                    url, method, data,
                    {"Content-Type": "application/x-www-form-urlencoded"} if method == "POST" else None,
                )
                p = DuckParser()
                p.feed(html)
                if p.results:
                    return p.results[:limit]
                fails.append(f"{url}: empty")
            except Exception as e:
                fails.append(f"{url}: {type(e).__name__}")

        # DuckDuckGo can reject requests from some cloud/ISP IP ranges.
        # Automatically fail over to Bing so the app still has real public-web
        # search without requiring a paid API key.
        try:
            bing = BingSearch().search(query, limit)
            if bing:
                return bing
            fails.append("bing: empty")
        except Exception as e:
            fails.append(f"bing: {type(e).__name__}")
        raise RuntimeError("Public web search unavailable: " + "; ".join(fails))


class BraveSearch(WebSearchProvider):
    def search(self, query, limit=8):
        if not BRAVE_API_KEY:
            raise RuntimeError("BRAVE_API_KEY is not configured")
        raw = _http(
            "https://api.search.brave.com/res/v1/web/search?" + urlencode({"q": query[:500], "count": limit}),
            headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY},
        )
        data = json.loads(raw)
        out = []
        for r in (data.get("web", {}).get("results") or [])[:limit]:
            u = r.get("url", "")
            t = r.get("title", "")
            if t and _safe(u):
                out.append(SearchResult(t, u, r.get("description", "") or "", "brave"))
        return out


class SerperSearch(WebSearchProvider):
    def search(self, query, limit=8):
        if not SERPER_API_KEY:
            raise RuntimeError("SERPER_API_KEY is not configured")
        raw = _http(
            "https://google.serper.dev/search",
            "POST",
            json.dumps({"q": query[:500], "gl": "in", "hl": "en", "num": limit}).encode(),
            {"Content-Type": "application/json", "X-API-KEY": SERPER_API_KEY},
        )
        data = json.loads(raw)
        out = []
        for r in (data.get("organic") or [])[:limit]:
            u = r.get("link", "")
            t = r.get("title", "")
            if t and _safe(u):
                out.append(SearchResult(t, u, r.get("snippet", "") or "", "google"))
        return out


def current_search_provider() -> WebSearchProvider:
    name = (WEB_SEARCH_PROVIDER or "auto").lower()
    if name in {"brave", "brave_search"}:
        return BraveSearch()
    if name in {"serper", "google"}:
        return SerperSearch()
    if name in {"bing", "bing_html"}:
        return BingSearch()
    if name in {"duckduckgo_html", "public_html"}:
        return DuckDuckGoSearch()
    if BRAVE_API_KEY:
        return BraveSearch()
    if SERPER_API_KEY:
        return SerperSearch()
    return DuckDuckGoSearch()


class WebFetchTool:
    def fetch(self, url: str) -> dict[str, Any]:
        if not _safe(url):
            raise ValueError("Only public http(s) URLs may be fetched.")
        with urlopen(
            Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,text/plain"}),
            timeout=WEB_REQUEST_TIMEOUT_SECONDS,
        ) as response:
            ct = response.headers.get_content_type()
            text = response.read(800_000).decode(response.headers.get_content_charset() or "utf-8", errors="replace")
        title = ""
        if ct in {"text/html", "application/xhtml+xml"}:
            m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
            title = unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()) if m else ""
            text = re.sub(r"<script[^>]*>.*?</script>|<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
            text = unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))).strip()
        return {"url": url, "title": title[:300], "content_type": ct, "text": text[:30000]}


class ReadOnlyBrowserTool:
    name = "read_only_browser"
    supports_automation = False

    def __init__(self, fetcher=None):
        self.fetcher = fetcher or WebFetchTool()

    def open_and_read(self, url):
        return self.fetcher.fetch(url)

    def status(self):
        return {"mode": "read-only HTTP browser", "supports_automation": False, "destructive_actions": "not available"}


def tool_definitions():
    return [
        {"type": "function", "function": {"name": "web_search", "description": "Search the public web for current factual discovery information.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
        {"type": "function", "function": {"name": "web_fetch", "description": "Read a public web page returned by search. Read-only.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    ]


def execute_tool(name, arguments):
    if name == "web_search":
        return {"results": [r.to_dict() for r in current_search_provider().search(str(arguments.get("query", ""))[:500])]}
    if name == "web_fetch":
        return WebFetchTool().fetch(str(arguments.get("url", "")))
    return {"error": f"Unknown or blocked tool: {name}"}
