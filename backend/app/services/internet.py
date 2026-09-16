"""Provider-neutral, read-only internet research tools for Manu AI."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from html import unescape
from html.parser import HTMLParser
import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

from ..config import WEB_REQUEST_TIMEOUT_SECONDS, WEB_SEARCH_PROVIDER

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/146 Safari/537.36 ManuAI/1.0"


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    provider: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class WebSearchProvider(ABC):
    @abstractmethod
    def search(self, query: str, limit: int = 5) -> list[SearchResult]: ...


class _DuckDuckGoParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results: list[SearchResult] = []
        self._url = ""
        self._title: list[str] = []
        self._snippet: list[str] = []
        self._in_result = False
        self._in_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "") or ""
        if tag == "a" and ("result__a" in classes or "result-link" in classes):
            raw_url = attrs_dict.get("href", "") or ""
            parsed = urlparse(raw_url)
            redirect = parse_qs(parsed.query).get("uddg", [""])[0]
            self._url = unquote(redirect or raw_url)
            self._title, self._snippet = [], []
            self._in_result = True
        elif self._in_result and ("result__snippet" in classes or "result-snippet" in classes):
            self._in_snippet = True

    def handle_data(self, data: str):
        if self._in_result:
            (self._snippet if self._in_snippet else self._title).append(data)

    def handle_endtag(self, tag: str):
        if tag == "a" and self._in_result:
            title = " ".join(self._title).strip()
            if title and _is_safe_public_url(self._url):
                self.results.append(SearchResult(title=unescape(title), url=self._url, snippet=unescape(" ".join(self._snippet).strip()), provider="duckduckgo"))
            self._in_result = False
            self._in_snippet = False
        elif self._in_snippet and tag in {"a", "div", "span"}:
            self._in_snippet = False


class _BingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results: list[SearchResult] = []
        self._url = ""
        self._title: list[str] = []
        self._snippet: list[str] = []
        self._in_title = False
        self._in_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        a = dict(attrs)
        classes = a.get("class", "") or ""
        if tag == "li" and "b_algo" in classes:
            self._url, self._title, self._snippet = "", [], []
        elif tag == "a" and not self._url and a.get("href", "").startswith(("http://", "https://")):
            self._url = a.get("href", "") or ""
            self._in_title = True
        elif "b_caption" in classes:
            self._in_snippet = True

    def handle_data(self, data: str):
        if self._in_title: self._title.append(data)
        if self._in_snippet: self._snippet.append(data)

    def handle_endtag(self, tag: str):
        if tag == "a" and self._in_title:
            self._in_title = False
        if tag in {"p", "div"} and self._in_snippet:
            self._in_snippet = False
        if tag == "li" and self._url:
            title = " ".join(self._title).strip()
            if title and _is_safe_public_url(self._url):
                self.results.append(SearchResult(title=unescape(title), url=self._url, snippet=unescape(" ".join(self._snippet).strip()), provider="bing"))
            self._url = ""


class DuckDuckGoHtmlSearchProvider(WebSearchProvider):
    """No-key public search with several read-only fallbacks."""
    endpoints = (
        "https://html.duckduckgo.com/html/",
        "https://lite.duckduckgo.com/lite/",
        "https://www.google.com/search",
    )

    def _request(self, url: str, method: str = "GET", data: bytes | None = None) -> str:
        headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-IN,en;q=0.9"}
        if method == "POST": headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = Request(url, data=data, method=method, headers=headers)
        with urlopen(request, timeout=WEB_REQUEST_TIMEOUT_SECONDS) as response:
            return response.read(1_000_000).decode(response.headers.get_content_charset() or "utf-8", errors="replace")

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        if not query.strip(): return []
        encoded = quote_plus(query[:500])
        failures: list[str] = []
        for endpoint, method in ((self.endpoints[0], "POST"), (self.endpoints[0] + "?q=" + encoded, "GET"), (self.endpoints[1] + "?q=" + encoded, "GET"), (self.endpoints[2] + "?q=" + encoded + "&hl=en&gl=in", "GET")):
            try:
                data = f"q={encoded}&kl=in-en&kp=-1".encode() if method == "POST" else None
                html = self._request(endpoint, method, data)
                parser = _DuckDuckGoParser() if "duckduckgo" in endpoint else _BingParser() if "bing" in endpoint else _GoogleParser()
                parser.feed(html)
                if parser.results: return parser.results[:limit]
                failures.append(f"{endpoint}: empty")
            except Exception as exc:
                failures.append(f"{endpoint}: {type(exc).__name__}")
        raise RuntimeError("All public search providers failed: " + "; ".join(failures))


class _GoogleParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.results=[]; self.url=""; self.title=[]; self.capture=False
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=="a" and a.get("href","").startswith("http") and not any(x in a.get("href","") for x in ("google.com/search", "google.com/url")):
            self.url=a.get("href",""); self.title=[]; self.capture=True
    def handle_data(self, data):
        if self.capture: self.title.append(data)
    def handle_endtag(self, tag):
        if tag=="a" and self.capture:
            title=" ".join(self.title).strip()
            if title and self.url and _is_safe_public_url(self.url): self.results.append(SearchResult(title=unescape(title), url=self.url, provider="google"))
            self.capture=False


class WebFetchTool:
    """Read-only public-page fetcher with basic SSRF protection and text extraction."""
    def fetch(self, url: str) -> dict[str, Any]:
        if not _is_safe_public_url(url): raise ValueError("Only public http(s) URLs may be fetched.")
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,text/plain"})
        with urlopen(request, timeout=WEB_REQUEST_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get_content_type(); raw = response.read(600_000)
            text = raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
        if content_type in {"text/html", "application/xhtml+xml"}:
            title = _first_match(r"<title[^>]*>(.*?)</title>", text)
            text = re.sub(r"<script[^>]*>.*?</script>|<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
            text = unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))).strip()
        else: title = ""
        return {"url": url, "title": title[:300], "content_type": content_type, "text": text[:30_000]}


class ReadOnlyBrowserTool:
    name = "read_only_browser"; supports_automation = False
    def __init__(self, fetcher: WebFetchTool | None = None): self.fetcher = fetcher or WebFetchTool()
    def open_and_read(self, url: str) -> dict[str, Any]: return self.fetcher.fetch(url)
    def status(self) -> dict[str, Any]: return {"mode": "read-only HTTP browser", "supports_automation": False, "destructive_actions": "not available"}


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.I | re.S)
    return unescape(re.sub(r"\s+", " ", match.group(1)).strip()) if match else ""


def _is_safe_public_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password: return False
        if parsed.hostname.lower() in {"localhost", "localhost.localdomain"}: return False
        for address in socket.getaddrinfo(parsed.hostname, None, type=socket.SOCK_STREAM):
            ip = ipaddress.ip_address(address[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved: return False
        return True
    except (OSError, ValueError): return False


def current_search_provider() -> WebSearchProvider:
    if WEB_SEARCH_PROVIDER in {"duckduckgo_html", "public_html"}: return DuckDuckGoHtmlSearchProvider()
    raise RuntimeError(f"Unsupported web search provider: {WEB_SEARCH_PROVIDER}")


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {"type": "function", "function": {"name": "web_search", "description": "Search the public web for current factual discovery information. Never use this for private data.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
        {"type": "function", "function": {"name": "web_fetch", "description": "Fetch and read a public web page returned by search. Read-only: it cannot log in, submit forms, purchase, or change accounts.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    ]


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "web_search":
        query = str(arguments.get("query", ""))[:500]
        return {"results": [result.to_dict() for result in current_search_provider().search(query)]}
    if name == "web_fetch": return WebFetchTool().fetch(str(arguments.get("url", "")))
    return {"error": f"Unknown or blocked tool: {name}"}
