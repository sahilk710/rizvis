"""
Web tools — search, fetch pages, global news & finance briefings, monitors.

Data-fetching helpers (fetch_news_items, search_duckduckgo) are module-level
so the dashboard backend can reuse them without going through MCP.
"""

import httpx
import xml.etree.ElementTree as ET
import asyncio
import re

# ── RSS Feed Sources ──────────────────────────────────────────────────────

WORLD_NEWS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.cnbc.com/id/100727362/device/rss/rss.html",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
]

FINANCE_FEEDS = [
    "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
]

# Map a substring of the feed URL to a friendly display name.
SOURCE_NAMES: list[tuple[str, str]] = [
    ("feeds.bbci.co.uk", "BBC"),
    ("bbc.co.uk", "BBC"),
    ("nytimes.com", "NYT"),
    ("cnbc.com", "CNBC"),
    ("aljazeera.com", "AL JAZEERA"),
    ("marketwatch.com", "MARKETWATCH"),
]


def _source_name(url: str) -> str:
    for key, name in SOURCE_NAMES:
        if key in url:
            return name
    return "NEWS"


async def _fetch_and_parse_feed(client: httpx.AsyncClient, url: str) -> list[dict]:
    """Fetch a single RSS feed and return parsed items."""
    try:
        response = await client.get(
            url, headers={"User-Agent": "Jarvis-AI/1.0"}, timeout=5.0
        )
        if response.status_code != 200:
            return []

        root = ET.fromstring(response.content)
        source_name = _source_name(url)

        items = []
        for item in root.findall(".//item")[:5]:
            title = item.findtext("title")
            description = item.findtext("description")
            link = item.findtext("link")
            pub_date = item.findtext("pubDate")

            if description:
                description = re.sub(r"<[^<]+?>", "", description).strip()

            items.append({
                "source": source_name,
                "title": title,
                "summary": (description[:200] + "...") if description else "",
                "link": link,
                "published": pub_date,
            })
        return items
    except Exception:
        return []


async def fetch_news_items(feeds: list[str], limit: int = 12) -> list[dict]:
    """
    Fetch & aggregate items across feeds. Returns a flat list of dicts —
    used by both MCP tools and the dashboard backend.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
        tasks = [_fetch_and_parse_feed(client, url) for url in feeds]
        results = await asyncio.gather(*tasks)
        all_articles = [item for sublist in results for item in sublist]
    return all_articles[:limit]


def _format_news_brief(articles: list[dict], heading: str) -> str:
    report = [f"### {heading}\n"]
    for entry in articles:
        report.append(f"**[{entry['source']}]** {entry['title']}")
        report.append(f"{entry['summary']}")
        report.append(f"Link: {entry['link']}\n")
    return "\n".join(report)


async def search_duckduckgo(query: str, limit: int = 5) -> list[dict]:
    """Run a DuckDuckGo HTML search and return [{title, snippet}, ...]."""
    url = "https://html.duckduckgo.com/html/"
    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
        response = await client.post(
            url,
            data={"q": query},
            headers={"User-Agent": "Jarvis-AI/1.0"},
        )
        response.raise_for_status()
        text = response.text

    snippets = re.findall(r'class="result__snippet">(.*?)</a>', text, re.DOTALL)
    titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', text, re.DOTALL)

    results = []
    for title, snippet in zip(titles[:limit], snippets[:limit]):
        results.append({
            "title": re.sub(r"<[^>]+>", "", title).strip(),
            "snippet": re.sub(r"<[^>]+>", "", snippet).strip(),
        })
    return results


# ── Tool Registration ─────────────────────────────────────────────────────

def register(mcp):

    @mcp.tool()
    async def get_world_news() -> str:
        """
        Fetches the latest global headlines from major news outlets (BBC, NYT, CNBC, Al Jazeera).
        Use this when the user asks 'What's going on in the world?', 'Brief me', or requests recent events.
        """
        articles = await fetch_news_items(WORLD_NEWS_FEEDS, limit=12)
        if not articles:
            return "The global news grid is unresponsive right now, sir. I can't pull headlines."
        return _format_news_brief(articles, "GLOBAL NEWS BRIEFING (LIVE)")

    @mcp.tool()
    async def get_finance_news() -> str:
        """
        Fetches the latest finance and market headlines from major financial outlets.
        Use this when the user asks about markets, finance news, or economic developments.
        """
        articles = await fetch_news_items(FINANCE_FEEDS, limit=12)
        if not articles:
            return "The financial feeds are unresponsive right now, sir."
        return _format_news_brief(articles, "FINANCE BRIEFING (LIVE)")

    @mcp.tool()
    async def search_web(query: str) -> str:
        """
        Search the web for a given query using DuckDuckGo.
        Returns a summary of the top results.
        """
        try:
            results = await search_duckduckgo(query, limit=5)
            if not results:
                return f"No results found for: {query}"
            lines = [f"### Search results for: {query}\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. **{r['title']}**\n   {r['snippet']}")
            return "\n\n".join(lines)
        except Exception as e:
            return f"Search failed: {str(e)}"

    @mcp.tool()
    async def fetch_url(url: str) -> str:
        """Fetch the raw text content of a URL. Returns the first 4000 characters."""
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text[:4000]

    @mcp.tool()
    async def open_world_monitor() -> str:
        """
        Opens the World Monitor dashboard (worldmonitor.app) in the system's web browser.
        Use this after delivering a world news briefing to give the user a visual overview.
        """
        import webbrowser
        try:
            webbrowser.open("https://worldmonitor.app/")
            return "Displaying the World Monitor on your primary screen now, sir."
        except Exception as e:
            return f"Unable to initialize the visual monitor: {str(e)}"

    @mcp.tool()
    async def open_finance_monitor() -> str:
        """
        Opens the Finance World Monitor dashboard in the system's web browser.
        Use this after delivering a finance briefing to show market visualizations.
        """
        import webbrowser
        try:
            webbrowser.open("https://finance.worldmonitor.app/")
            return "Displaying the Finance Monitor on your primary screen now, sir."
        except Exception as e:
            return f"Unable to initialize the finance monitor: {str(e)}"
