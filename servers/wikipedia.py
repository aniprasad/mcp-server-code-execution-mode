#!/usr/bin/env python3
"""
Wikipedia MCP Server

Uses Wikipedia REST API for article summaries and information.
https://en.wikipedia.org/api/rest_v1/

Usage in sandbox:
    result = await mcp_wikipedia.summary(title='Python (programming language)')
    result = await mcp_wikipedia.search(query='machine learning')
    result = await mcp_wikipedia.on_this_day(month=1, day=25)
"""

import asyncio
import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Handle both direct execution and import from parent
try:
    from schemas import (
        ArticleSummary, SearchResult, SearchResults,
        OnThisDayEvent, OnThisDayResponse, 
        TrendingArticle, TrendingResponse,
        schema_to_description
    )
except ImportError:
    from .schemas import (
        ArticleSummary, SearchResult, SearchResults,
        OnThisDayEvent, OnThisDayResponse,
        TrendingArticle, TrendingResponse,
        schema_to_description
    )

SERVER_NAME = "wikipedia"
WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1"

logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")
logger = logging.getLogger(SERVER_NAME)

app = Server(SERVER_NAME)


def _make_request(url: str) -> Dict[str, Any]:
    """Make HTTP GET request and return JSON."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "MCPSandbox/1.0 (Educational; https://github.com)",
                "Accept": "application/json",
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"Article not found")
        raise RuntimeError(f"HTTP error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


def _encode_title(title: str) -> str:
    """Encode article title for URL (spaces to underscores, then URL encode)."""
    return urllib.parse.quote(title.replace(" ", "_"), safe="")


@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="summary",
            description=f"""Get a summary of a Wikipedia article.

Returns: {{title, extract, description, url, thumbnail, coordinates}}

The 'extract' field contains a plain-text summary (first paragraph).
Use 'thumbnail' URL to display article image if available.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Article title (e.g., 'Python (programming language)', 'Albert Einstein')",
                    },
                },
                "required": ["title"],
            },
        ),
        Tool(
            name="search",
            description=f"""Search Wikipedia for articles matching a query.

Returns: {{query, results: [{{title, description, url}}]}}

Returns up to 10 matching articles with titles and descriptions.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'machine learning', 'climate change')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (1-10)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="on_this_day",
            description=f"""Get historical events that happened on a specific date.

Returns: {{date, events: [{{year, text, pages}}]}}

Great for "on this day in history" content. Each event includes the year and description.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "month": {
                        "type": "integer",
                        "description": "Month (1-12)",
                    },
                    "day": {
                        "type": "integer",
                        "description": "Day of month (1-31)",
                    },
                    "type": {
                        "type": "string",
                        "description": "Event type: 'selected' (notable), 'births', 'deaths', 'events', 'holidays'",
                        "default": "selected",
                    },
                },
                "required": ["month", "day"],
            },
        ),
        Tool(
            name="random",
            description=f"""Get a random Wikipedia article summary.

Returns: {{title, extract, description, url, thumbnail}}

Great for discovering new topics or trivia.""",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="trending",
            description=f"""Get the most-read Wikipedia articles (yesterday's top articles).

Returns: {{date, articles: [{{rank, title, views, url}}]}}

Shows what people are searching for - often reflects current news and events.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of articles to return (1-50)",
                        "default": 10,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="featured",
            description=f"""Get today's featured article from Wikipedia.

Returns: {{title, extract, description, url, thumbnail}}

Wikipedia editors select one high-quality article to feature each day.""",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


# =============================================================================
# Tool Implementations
# =============================================================================

async def summary(title: str) -> Dict[str, Any]:
    """Get summary of a Wikipedia article."""
    encoded = _encode_title(title)
    url = f"{WIKIPEDIA_API}/page/summary/{encoded}"
    data = _make_request(url)
    
    # Extract thumbnail if present
    thumbnail = None
    if "thumbnail" in data:
        thumbnail = data["thumbnail"].get("source")
    
    # Extract coordinates if present
    coordinates = None
    if "coordinates" in data:
        coordinates = {
            "lat": data["coordinates"].get("lat"),
            "lon": data["coordinates"].get("lon"),
        }
    
    return ArticleSummary(
        title=data.get("title", title),
        extract=data.get("extract", ""),
        description=data.get("description", ""),
        url=data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        thumbnail=thumbnail,
        coordinates=coordinates,
    ).model_dump()


async def search(query: str, limit: int = 5) -> Dict[str, Any]:
    """Search Wikipedia for articles."""
    limit = max(1, min(10, limit))  # Clamp to 1-10
    encoded = urllib.parse.quote(query)
    url = f"{WIKIPEDIA_API}/page/related/{_encode_title(query)}"
    
    # Use the search endpoint instead
    search_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={encoded}&limit={limit}&format=json"
    
    try:
        req = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": "MCPSandbox/1.0 (Educational; https://github.com)",
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
    except Exception as e:
        raise RuntimeError(f"Search failed: {e}")
    
    # OpenSearch returns [query, [titles], [descriptions], [urls]]
    titles = data[1] if len(data) > 1 else []
    descriptions = data[2] if len(data) > 2 else []
    urls = data[3] if len(data) > 3 else []
    
    results = []
    for i, title in enumerate(titles):
        results.append(SearchResult(
            title=title,
            description=descriptions[i] if i < len(descriptions) else "",
            url=urls[i] if i < len(urls) else "",
        ))
    
    return SearchResults(
        query=query,
        results=results,
    ).model_dump()


async def on_this_day(month: int, day: int, event_type: str = "selected") -> Dict[str, Any]:
    """Get events that happened on this day in history."""
    # Validate inputs
    month = max(1, min(12, month))
    day = max(1, min(31, day))
    
    valid_types = ["selected", "births", "deaths", "events", "holidays"]
    if event_type not in valid_types:
        event_type = "selected"
    
    url = f"{WIKIPEDIA_API}/feed/onthisday/{event_type}/{month:02d}/{day:02d}"
    data = _make_request(url)
    
    events = []
    raw_events = data.get(event_type, data.get("selected", []))
    
    for item in raw_events[:20]:  # Limit to 20 events
        # Get related page titles
        pages = [p.get("title", "") for p in item.get("pages", [])[:3]]
        
        events.append(OnThisDayEvent(
            year=item.get("year"),
            text=item.get("text", ""),
            pages=pages,
        ))
    
    return OnThisDayResponse(
        date=f"{month:02d}-{day:02d}",
        events=events,
    ).model_dump()


async def random_article() -> Dict[str, Any]:
    """Get a random Wikipedia article."""
    url = f"{WIKIPEDIA_API}/page/random/summary"
    data = _make_request(url)
    
    thumbnail = None
    if "thumbnail" in data:
        thumbnail = data["thumbnail"].get("source")
    
    return ArticleSummary(
        title=data.get("title", ""),
        extract=data.get("extract", ""),
        description=data.get("description", ""),
        url=data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        thumbnail=thumbnail,
        coordinates=None,
    ).model_dump()


async def trending(limit: int = 10) -> Dict[str, Any]:
    """Get most-read articles from yesterday."""
    from datetime import timedelta
    
    # Use yesterday's date (today's stats aren't ready until late)
    yesterday = datetime.now() - timedelta(days=1)
    year = yesterday.year
    month = yesterday.month
    day = yesterday.day
    
    url = f"{WIKIPEDIA_API}/feed/featured/{year}/{month:02d}/{day:02d}"
    data = _make_request(url)
    
    limit = max(1, min(50, limit))
    articles = []
    
    most_read = data.get("mostread", {}).get("articles", [])
    for i, article in enumerate(most_read[:limit]):
        articles.append(TrendingArticle(
            rank=i + 1,
            title=article.get("title", ""),
            views=article.get("views", 0),
            url=article.get("content_urls", {}).get("desktop", {}).get("page", ""),
        ))
    
    return TrendingResponse(
        date=f"{year}-{month:02d}-{day:02d}",
        articles=articles,
    ).model_dump()


async def featured() -> Dict[str, Any]:
    """Get today's featured article."""
    now = datetime.now()
    year = now.year
    month = now.month
    day = now.day
    
    url = f"{WIKIPEDIA_API}/feed/featured/{year}/{month:02d}/{day:02d}"
    data = _make_request(url)
    
    tfa = data.get("tfa", {})
    
    thumbnail = None
    if "thumbnail" in tfa:
        thumbnail = tfa["thumbnail"].get("source")
    
    return ArticleSummary(
        title=tfa.get("title", ""),
        extract=tfa.get("extract", ""),
        description=tfa.get("description", ""),
        url=tfa.get("content_urls", {}).get("desktop", {}).get("page", ""),
        thumbnail=thumbnail,
        coordinates=None,
    ).model_dump()


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    logger.info(f"Tool called: {name} with args: {arguments}")
    
    try:
        if name == "summary":
            result = await summary(title=arguments.get("title", ""))
        elif name == "search":
            result = await search(
                query=arguments.get("query", ""),
                limit=arguments.get("limit", 5),
            )
        elif name == "on_this_day":
            result = await on_this_day(
                month=arguments.get("month", 1),
                day=arguments.get("day", 1),
                event_type=arguments.get("type", "selected"),
            )
        elif name == "random":
            result = await random_article()
        elif name == "trending":
            result = await trending(limit=arguments.get("limit", 10))
        elif name == "featured":
            result = await featured()
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main() -> None:
    logger.info(f"Starting {SERVER_NAME} MCP server (Wikipedia API)...")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
