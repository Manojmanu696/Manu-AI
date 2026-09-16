"""Provider-neutral, read-only internet research tools for Manu AI.

No personal library records are sent to these tools. They accept only a query or public URL.
"""
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

USER_AGENT = "ManuAI/0.2 (+local personal discovery research)"


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
        if tag == "a" and "result__a" in classes:
            raw_url = attrs_dict.get("href", "") or ""
            parsed = urlparse(raw_url)
            redirect = parse_qs(parsed.query).get("uddg", [""])[0]
            self._url = unquote(redirect or raw_url)
            self._title = []
            self._snippet = []
            self._in_result = True
        elif self._in_result and "result__snippet" in classes:
            self._in_snippet = True

    def handle_data(self, data: str):
        if self._in_result:
            (self._snippet if self._in_snippet else self._title).append(data)

    def handle_endtag(self, tag: str):
        if tag == "a" and self._in_result:
            title = " ".join(self._title).strip()
            if title and _is_safe_public_url(self._url):
                self.results.append(SearchResult(title=unescape(title), url=self._url, snippet=unescape(" ".join(self._snippet).strip()), provider="duckduckgo_html"))
            self._in_result = False
            self._in_snippet = False
        elif self._in_snippet and tag in {"a", "div", "span"}:
            self._in_snippet = False


class DuckDuckGoHtmlSearchProvider(WebSearchProvider):
    """A no-key, provider-swappable search adapter using DuckDuckGo's HTML endpoint."""
    endpoint = "https://html.duckduckgo.com/html/?q="

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        if not query.strip():
            return []
        request = Request(self.endpoint + quote_plus(query[:500]), headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
        with urlopen(request, timeout=WEB_REQUEST_TIMEOUT_SECONDS) as response:
            html = response.read(500_000).decode(response.headers.get_content_charset() or "utf-8", errors="replace")
        parser = _DuckDuckGoParser()
        parser.feed(html)
        return parser.results[:limit]


class WebFetchTool:
    """Read-only public-page fetcher with basic SSRF protection and text extraction."""
    def fetch(self, url: str) -> dict[str, Any]:
        if not _is_safe_public_url(url):
            raise ValueError("Only public http(s) URLs may be fetched.")
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,text/plain"})
        with urlopen(request, timeout=WEB_REQUEST_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get_content_type()
            raw = response.read(600_000)
            text = raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
        if content_type in {"text/html", "application/xhtml+xml"}:
            title = _first_match(r"<title[^>]*>(.*?)</title>", text)
            text = re.sub(r"<script[^>]*>.*?</script>|<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
            text = unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))).strip()
        else:
            title = ""
        return {"url": url, "title": title[:300], "content_type": content_type, "text": text[:30_000]}


class ReadOnlyBrowserTool:
    """Explicit browser boundary. It can read public pages but exposes no click/form/action API."""
    name = "read_only_browser"
    supports_automation = False

    def __init__(self, fetcher: WebFetchTool | None = None):
        self.fetcher = fetcher or WebFetchTool()

    def open_and_read(self, url: str) -> dict[str, Any]:
        return self.fetcher.fetch(url)

    def status(self) -> dict[str, Any]:
        return {"mode": "read-only HTTP browser", "supports_automation": self.supports_automation, "destructive_actions": "not available"}


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.I | re.S)
    return unescape(re.sub(r"\s+", " ", match.group(1)).strip()) if match else ""


def _is_safe_public_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return False
        if parsed.hostname.lower() in {"localhost", "localhost.localdomain"}:
            return False
        addresses = socket.getaddrinfo(parsed.hostname, None, type=socket.SOCK_STREAM)
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True
    except (OSError, ValueError):
        return False


def current_search_provider() -> WebSearchProvider:
    if WEB_SEARCH_PROVIDER == "duckduckgo_html":
        return DuckDuckGoHtmlSearchProvider()
    raise RuntimeError(f"Unsupported web search provider: {WEB_SEARCH_PROVIDER}")


def tool_definitions() -> list[dict[str, Any]]:
    """Ollama-compatible schemas for the only two tools the model may autonomously invoke."""
    return [
        {"type": "function", "function": {"name": "web_search", "description": "Search the public web for current factual discovery information. Never use this for private data.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
        {"type": "function", "function": {"name": "web_fetch", "description": "Fetch and read a public web page returned by search. Read-only: it cannot log in, submit forms, purchase, or change accounts.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    ]


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "web_search":
        query = str(arguments.get("query", ""))[:500]
        return {"results": [result.to_dict() for result in current_search_provider().search(query)]}
    if name == "web_fetch":
        return WebFetchTool().fetch(str(arguments.get("url", "")))
    return {"error": f"Unknown or blocked tool: {name}"}
