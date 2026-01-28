#!/usr/bin/env python3
"""
Open Library MCP Server

Uses Open Library API for book data.
https://openlibrary.org/developers/api

Usage in sandbox:
    books = await mcp_openlibrary.search_books(query="Clean Code")
    book = await mcp_openlibrary.get_book(isbn="9780132350884")
    author = await mcp_openlibrary.get_author(key="/authors/OL34184A")
"""

import asyncio
import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Handle both direct execution and import from parent
try:
    from schemas import OLBook, OLAuthor, OLSearchResult
except ImportError:
    from .schemas import OLBook, OLAuthor, OLSearchResult

SERVER_NAME = "openlibrary"
API_BASE = "https://openlibrary.org"

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
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError("Not found")
        raise RuntimeError(f"HTTP error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


def _get_cover_url(cover_id: Optional[int], size: str = "M") -> Optional[str]:
    """Build cover URL from cover ID."""
    if not cover_id:
        return None
    return f"https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg"


def _parse_search_result(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Parse search result document into OLBook schema."""
    return OLBook(
        key=doc.get("key", ""),
        title=doc.get("title", ""),
        authors=[a for a in doc.get("author_name", [])],
        first_publish_year=doc.get("first_publish_year"),
        isbn=doc.get("isbn", [])[:5] if doc.get("isbn") else [],  # Limit ISBNs
        subjects=doc.get("subject", [])[:10] if doc.get("subject") else [],  # Limit subjects
        cover_url=_get_cover_url(doc.get("cover_i")),
        edition_count=doc.get("edition_count", 0),
        language=doc.get("language", [])[:5] if doc.get("language") else [],
    ).model_dump()


@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="search_books",
            description="Search for books by title, author, or subject.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (title, author name, or subject)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (1-20)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_book",
            description="Get book details by ISBN or Open Library ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "isbn": {
                        "type": "string",
                        "description": "ISBN-10 or ISBN-13",
                    },
                    "olid": {
                        "type": "string",
                        "description": "Open Library work ID (e.g., 'OL45804W')",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_author",
            description="Get author details by Open Library author key.",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Author key (e.g., '/authors/OL34184A' or 'OL34184A')",
                    },
                },
                "required": ["key"],
            },
        ),
        Tool(
            name="search_authors",
            description="Search for authors by name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Author name to search",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (1-20)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_cover",
            description="Get book cover URL by ISBN or cover ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "isbn": {
                        "type": "string",
                        "description": "ISBN-10 or ISBN-13",
                    },
                    "cover_id": {
                        "type": "integer",
                        "description": "Open Library cover ID",
                    },
                    "size": {
                        "type": "string",
                        "description": "Size: S (small), M (medium), L (large)",
                        "default": "M",
                    },
                },
                "required": [],
            },
        ),
    ]


# =============================================================================
# Tool Implementations
# =============================================================================

async def search_books(query: str, limit: int = 10) -> Dict[str, Any]:
    """Search for books."""
    limit = max(1, min(20, limit))
    encoded_query = urllib.parse.quote(query.strip())
    url = f"{API_BASE}/search.json?q={encoded_query}&limit={limit}"

    data = _make_request(url)

    books = [_parse_search_result(doc) for doc in data.get("docs", [])]

    return OLSearchResult(
        query=query,
        total=data.get("numFound", 0),
        books=books,
    ).model_dump()


async def get_book(isbn: Optional[str] = None, olid: Optional[str] = None) -> Dict[str, Any]:
    """Get book by ISBN or Open Library ID."""
    if not isbn and not olid:
        raise ValueError("Either isbn or olid is required")

    if isbn:
        # Use ISBN API
        isbn = isbn.replace("-", "").strip()
        url = f"{API_BASE}/isbn/{isbn}.json"
        try:
            data = _make_request(url)
        except ValueError:
            raise ValueError(f"Book not found for ISBN: {isbn}")

        # Get work info for more details
        work_key = None
        if data.get("works"):
            work_key = data["works"][0].get("key", "")

        # Get authors
        authors = []
        for author_ref in data.get("authors", []):
            author_key = author_ref.get("key", "")
            if author_key:
                try:
                    author_data = _make_request(f"{API_BASE}{author_key}.json")
                    authors.append(author_data.get("name", ""))
                except Exception:
                    pass

        return OLBook(
            key=work_key or data.get("key", ""),
            title=data.get("title", ""),
            authors=authors,
            first_publish_year=data.get("publish_date"),
            isbn=[isbn],
            subjects=data.get("subjects", [])[:10] if data.get("subjects") else [],
            cover_url=_get_cover_url(data.get("covers", [None])[0] if data.get("covers") else None),
            edition_count=1,
            language=[],
            description=data.get("description", {}).get("value") if isinstance(data.get("description"), dict) else data.get("description"),
            publishers=data.get("publishers", []),
            publish_date=data.get("publish_date"),
            number_of_pages=data.get("number_of_pages"),
        ).model_dump()

    else:
        # Use work ID
        olid = olid.strip()
        if not olid.startswith("/works/"):
            olid = f"/works/{olid}"

        url = f"{API_BASE}{olid}.json"
        data = _make_request(url)

        # Get authors
        authors = []
        for author_ref in data.get("authors", []):
            author_obj = author_ref.get("author", {})
            author_key = author_obj.get("key", "") if isinstance(author_obj, dict) else ""
            if author_key:
                try:
                    author_data = _make_request(f"{API_BASE}{author_key}.json")
                    authors.append(author_data.get("name", ""))
                except Exception:
                    pass

        # Get cover
        cover_id = data.get("covers", [None])[0] if data.get("covers") else None

        return OLBook(
            key=data.get("key", ""),
            title=data.get("title", ""),
            authors=authors,
            first_publish_year=None,
            isbn=[],
            subjects=data.get("subjects", [])[:10] if data.get("subjects") else [],
            cover_url=_get_cover_url(cover_id),
            edition_count=0,
            language=[],
            description=data.get("description", {}).get("value") if isinstance(data.get("description"), dict) else data.get("description"),
        ).model_dump()


async def get_author(key: str) -> Dict[str, Any]:
    """Get author by key."""
    key = key.strip()
    if not key.startswith("/authors/"):
        key = f"/authors/{key}"

    url = f"{API_BASE}{key}.json"
    data = _make_request(url)

    # Get bio text
    bio = data.get("bio")
    if isinstance(bio, dict):
        bio = bio.get("value", "")
    elif not isinstance(bio, str):
        bio = None

    # Get work count
    work_count = None
    try:
        works_url = f"{API_BASE}{key}/works.json?limit=0"
        works_data = _make_request(works_url)
        work_count = works_data.get("size", 0)
    except Exception:
        pass

    return OLAuthor(
        key=data.get("key", ""),
        name=data.get("name", ""),
        birth_date=data.get("birth_date"),
        death_date=data.get("death_date"),
        bio=bio,
        works_count=work_count,
        photo_url=_get_cover_url(data.get("photos", [None])[0] if data.get("photos") else None),
    ).model_dump()


async def search_authors(query: str, limit: int = 5) -> Dict[str, Any]:
    """Search for authors."""
    limit = max(1, min(20, limit))
    encoded_query = urllib.parse.quote(query.strip())
    url = f"{API_BASE}/search/authors.json?q={encoded_query}&limit={limit}"

    data = _make_request(url)

    authors = []
    for doc in data.get("docs", []):
        authors.append(OLAuthor(
            key=f"/authors/{doc.get('key', '')}",
            name=doc.get("name", ""),
            birth_date=doc.get("birth_date"),
            death_date=doc.get("death_date"),
            bio=None,
            works_count=doc.get("work_count"),
            photo_url=None,
        ).model_dump())

    return {
        "query": query,
        "total": data.get("numFound", 0),
        "authors": authors,
    }


async def get_cover(isbn: Optional[str] = None, cover_id: Optional[int] = None, size: str = "M") -> Dict[str, Any]:
    """Get book cover URL."""
    size = size.upper()
    if size not in ["S", "M", "L"]:
        size = "M"

    if cover_id:
        return {
            "cover_url": f"https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg",
            "size": size,
        }
    elif isbn:
        isbn = isbn.replace("-", "").strip()
        return {
            "cover_url": f"https://covers.openlibrary.org/b/isbn/{isbn}-{size}.jpg",
            "size": size,
        }
    else:
        raise ValueError("Either isbn or cover_id is required")


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    logger.info(f"Tool called: {name} with args: {arguments}")

    try:
        if name == "search_books":
            result = await search_books(
                query=arguments.get("query", ""),
                limit=arguments.get("limit", 10),
            )
        elif name == "get_book":
            result = await get_book(
                isbn=arguments.get("isbn"),
                olid=arguments.get("olid"),
            )
        elif name == "get_author":
            result = await get_author(key=arguments.get("key", ""))
        elif name == "search_authors":
            result = await search_authors(
                query=arguments.get("query", ""),
                limit=arguments.get("limit", 5),
            )
        elif name == "get_cover":
            result = await get_cover(
                isbn=arguments.get("isbn"),
                cover_id=arguments.get("cover_id"),
                size=arguments.get("size", "M"),
            )
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main() -> None:
    logger.info(f"Starting {SERVER_NAME} MCP server (Open Library API)...")
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
