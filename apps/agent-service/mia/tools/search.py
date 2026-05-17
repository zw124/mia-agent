from html import unescape
from html.parser import HTMLParser

import httpx
from langchain_core.tools import StructuredTool


class _DuckDuckGoHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._capture: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        class_name = attributes.get("class", "")
        if tag == "a" and "result__a" in class_name:
            self._current = {"title": "", "url": attributes.get("href", "") or "", "snippet": ""}
            self._capture = "title"
            self._buffer = []
        elif self._current is not None and tag in {"a", "div"} and "result__snippet" in class_name:
            self._capture = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._current is None or self._capture is None:
            return
        if self._capture == "title" and tag == "a":
            self._current["title"] = _clean_text(" ".join(self._buffer))
            self._capture = None
            self._buffer = []
        elif self._capture == "snippet" and tag in {"a", "div"}:
            self._current["snippet"] = _clean_text(" ".join(self._buffer))
            if self._current.get("title") and self._current.get("url"):
                self.results.append(self._current)
            self._current = None
            self._capture = None
            self._buffer = []


def _clean_text(value: str) -> str:
    return " ".join(unescape(value).split())


def _format_results(*, provider: str, query: str, results: list[dict[str, str]]) -> str:
    if not results:
        return f"No {provider} results for: {query}"
    return "\n".join(
        (
            f"{index + 1}. {item.get('title') or 'Untitled'} - {item.get('url', '')}\n"
            f"{item.get('snippet') or item.get('content') or ''}"
        ).strip()
        for index, item in enumerate(results[:5])
    )


def build_search_tools(*, searxng_base_url: str) -> list[StructuredTool]:
    async def searxng_search(query: str) -> str:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{searxng_base_url.rstrip('/')}/search",
                params={"q": query, "format": "json", "language": "en"},
            )
            response.raise_for_status()
            data = response.json()
        results = [
            {
                "title": str(item.get("title", "Untitled")),
                "url": str(item.get("url", "")),
                "content": str(item.get("content", "")),
            }
            for item in data.get("results", [])[:5]
        ]
        return _format_results(provider="SearXNG", query=query, results=results)

    async def duckduckgo_search(query: str) -> str:
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "mia-agent/0.1 (+https://local)"},
        ) as client:
            response = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
            )
            response.raise_for_status()
        parser = _DuckDuckGoHtmlParser()
        parser.feed(response.text)
        return _format_results(provider="DuckDuckGo", query=query, results=parser.results)

    async def web_search(query: str) -> str:
        query = query.strip()
        if not query:
            return "Missing search query."
        if searxng_base_url:
            return await searxng_search(query)
        return await duckduckgo_search(query)

    return [
        StructuredTool.from_function(
            coroutine=web_search,
            name="web_search",
            description=(
                "Search the web. Uses configured SearXNG when available, otherwise DuckDuckGo."
            ),
        )
    ]
