import respx
from httpx import Response

from mia.tools.search import build_search_tools


@respx.mock
async def test_web_search_uses_duckduckgo_without_searxng() -> None:
    route = respx.get("https://html.duckduckgo.com/html/").mock(
        return_value=Response(
            200,
            text="""
            <html>
              <body>
                <a class="result__a" href="https://example.com/a">Example Result</a>
                <a class="result__snippet">Useful snippet for the result.</a>
              </body>
            </html>
            """,
        )
    )
    tool = build_search_tools(searxng_base_url="")[0]

    result = await tool.ainvoke({"query": "mia agent"})

    assert route.called
    assert "Example Result - https://example.com/a" in result
    assert "Useful snippet for the result." in result


@respx.mock
async def test_web_search_prefers_configured_searxng() -> None:
    route = respx.get("https://search.local/search").mock(
        return_value=Response(
            200,
            json={
                "results": [
                    {
                        "title": "SearX Result",
                        "url": "https://example.com/searx",
                        "content": "SearX snippet",
                    }
                ]
            },
        )
    )
    tool = build_search_tools(searxng_base_url="https://search.local")[0]

    result = await tool.ainvoke({"query": "mia agent"})

    assert route.called
    assert "SearX Result - https://example.com/searx" in result
    assert "SearX snippet" in result
