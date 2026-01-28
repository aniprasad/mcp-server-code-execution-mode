#!/usr/bin/env python3
"""
Hacker News MCP Server

Uses Hacker News Firebase API and Algolia HN Search API.
https://github.com/HackerNews/API
https://hn.algolia.com/api

Usage in sandbox:
    stories = await mcp_hackernews.top_stories(limit=10)
    story = await mcp_hackernews.story(id=12345)
    user = await mcp_hackernews.user(username="pg")
    results = await mcp_hackernews.search(query="python", limit=10)
"""

import asyncio
import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Handle both direct execution and import from parent
try:
    from schemas import HNStory, HNUser, HNSearchResult, HNSearchHit
except ImportError:
    from .schemas import HNStory, HNUser, HNSearchResult, HNSearchHit

SERVER_NAME = "hackernews"
FIREBASE_API = "https://hacker-news.firebaseio.com/v0"
ALGOLIA_API = "https://hn.algolia.com/api/v1"

logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")
logger = logging.getLogger(SERVER_NAME)

app = Server(SERVER_NAME)


def _make_request(url: str) -> Any:
    """Make HTTP GET request and return JSON."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError("Not found")
        raise RuntimeError(f"HTTP error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


def _parse_story(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse story data into HNStory schema."""
    # Convert Unix timestamp to ISO format
    time_unix = data.get("time", 0)
    time_iso = datetime.fromtimestamp(time_unix, tz=timezone.utc).isoformat().replace("+00:00", "Z") if time_unix else None

    return HNStory(
        id=data.get("id", 0),
        title=data.get("title", ""),
        url=data.get("url"),
        score=data.get("score", 0),
        by=data.get("by", ""),
        time=time_iso,
        time_unix=time_unix,
        descendants=data.get("descendants", 0),
        type=data.get("type", "story"),
        text=data.get("text"),
    ).model_dump()


def _fetch_story(story_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single story by ID."""
    url = f"{FIREBASE_API}/item/{story_id}.json"
    data = _make_request(url)
    if data and data.get("type") in ("story", "job", "poll"):
        return _parse_story(data)
    return None


@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="top_stories",
            description="Get the current top stories on Hacker News.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of stories to return (1-30)",
                        "default": 10,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="new_stories",
            description="Get the newest stories on Hacker News.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of stories to return (1-30)",
                        "default": 10,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="best_stories",
            description="Get the best stories on Hacker News (highest voted recent stories).",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of stories to return (1-30)",
                        "default": 10,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="story",
            description="Get full details of a specific story by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer",
                        "description": "Story ID",
                    },
                },
                "required": ["id"],
            },
        ),
        Tool(
            name="user",
            description="Get a user's profile information.",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Username (case-sensitive)",
                    },
                },
                "required": ["username"],
            },
        ),
        Tool(
            name="search",
            description="Search Hacker News stories and comments (via Algolia).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results to return (1-50)",
                        "default": 10,
                    },
                    "search_type": {
                        "type": "string",
                        "description": "Type of search: 'story' (stories only), 'comment' (comments only), 'all' (both)",
                        "default": "story",
                    },
                },
                "required": ["query"],
            },
        ),
    ]


# =============================================================================
# Tool Implementations
# =============================================================================

async def top_stories(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top stories."""
    limit = max(1, min(30, limit))

    # Get story IDs
    url = f"{FIREBASE_API}/topstories.json"
    story_ids = _make_request(url)

    # Fetch each story (limited)
    stories = []
    for story_id in story_ids[:limit]:
        story = _fetch_story(story_id)
        if story:
            stories.append(story)

    return stories


async def new_stories(limit: int = 10) -> List[Dict[str, Any]]:
    """Get newest stories."""
    limit = max(1, min(30, limit))

    url = f"{FIREBASE_API}/newstories.json"
    story_ids = _make_request(url)

    stories = []
    for story_id in story_ids[:limit]:
        story = _fetch_story(story_id)
        if story:
            stories.append(story)

    return stories


async def best_stories(limit: int = 10) -> List[Dict[str, Any]]:
    """Get best stories."""
    limit = max(1, min(30, limit))

    url = f"{FIREBASE_API}/beststories.json"
    story_ids = _make_request(url)

    stories = []
    for story_id in story_ids[:limit]:
        story = _fetch_story(story_id)
        if story:
            stories.append(story)

    return stories


async def story(id: int) -> Dict[str, Any]:
    """Get a specific story by ID."""
    url = f"{FIREBASE_API}/item/{id}.json"
    data = _make_request(url)

    if not data:
        raise ValueError(f"Story not found: {id}")

    return _parse_story(data)


async def user(username: str) -> Dict[str, Any]:
    """Get user profile."""
    encoded_username = urllib.parse.quote(username.strip())
    url = f"{FIREBASE_API}/user/{encoded_username}.json"
    data = _make_request(url)

    if not data:
        raise ValueError(f"User not found: {username}")

    # Convert Unix timestamp to ISO format
    created_unix = data.get("created", 0)
    created_iso = datetime.fromtimestamp(created_unix, tz=timezone.utc).isoformat().replace("+00:00", "Z") if created_unix else None

    return HNUser(
        id=data.get("id", ""),
        karma=data.get("karma", 0),
        about=data.get("about"),
        created=created_iso,
        created_unix=created_unix,
        submitted_count=len(data.get("submitted", [])),
    ).model_dump()


async def search(query: str, limit: int = 10, search_type: str = "story") -> Dict[str, Any]:
    """Search HN via Algolia API."""
    limit = max(1, min(50, limit))
    encoded_query = urllib.parse.quote(query.strip())

    # Build URL based on search type
    tags = ""
    if search_type == "story":
        tags = "&tags=story"
    elif search_type == "comment":
        tags = "&tags=comment"
    # 'all' = no tags filter

    url = f"{ALGOLIA_API}/search?query={encoded_query}&hitsPerPage={limit}{tags}"
    data = _make_request(url)

    hits = []
    for hit in data.get("hits", []):
        hits.append(HNSearchHit(
            objectID=hit.get("objectID", ""),
            title=hit.get("title") or hit.get("story_title", ""),
            url=hit.get("url") or hit.get("story_url"),
            author=hit.get("author", ""),
            points=hit.get("points") or hit.get("story_points", 0),
            num_comments=hit.get("num_comments", 0),
            created_at=hit.get("created_at", ""),
            story_id=hit.get("story_id"),
            type=hit.get("_tags", [""])[0] if hit.get("_tags") else "story",
        ).model_dump())

    return HNSearchResult(
        query=query,
        total=data.get("nbHits", 0),
        hits=hits,
    ).model_dump()


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    logger.info(f"Tool called: {name} with args: {arguments}")

    try:
        if name == "top_stories":
            result = await top_stories(limit=arguments.get("limit", 10))
        elif name == "new_stories":
            result = await new_stories(limit=arguments.get("limit", 10))
        elif name == "best_stories":
            result = await best_stories(limit=arguments.get("limit", 10))
        elif name == "story":
            result = await story(id=arguments.get("id", 0))
        elif name == "user":
            result = await user(username=arguments.get("username", ""))
        elif name == "search":
            result = await search(
                query=arguments.get("query", ""),
                limit=arguments.get("limit", 10),
                search_type=arguments.get("search_type", "story"),
            )
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main() -> None:
    logger.info(f"Starting {SERVER_NAME} MCP server (Hacker News API)...")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
