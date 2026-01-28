#!/usr/bin/env python3
"""
REST Countries MCP Server

Uses REST Countries API for country data.
https://restcountries.com/

Usage in sandbox:
    country = await mcp_countries.get_country(name="France")
    results = await mcp_countries.search_countries(name="united")
    european = await mcp_countries.by_region(region="Europe")
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
    from schemas import Country
except ImportError:
    from .schemas import Country

SERVER_NAME = "countries"
API_BASE = "https://restcountries.com/v3.1"

logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")
logger = logging.getLogger(SERVER_NAME)

app = Server(SERVER_NAME)

# Fields to request (reduces response size)
FIELDS = "name,capital,region,subregion,population,area,languages,currencies,flags,cca2,cca3"


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
            raise ValueError("Country not found")
        raise RuntimeError(f"HTTP error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


def _parse_country(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse API response into Country schema."""
    # Extract languages as list of names
    languages = list(data.get("languages", {}).values()) if data.get("languages") else []

    # Extract currencies as list of {code, name, symbol}
    currencies = []
    for code, info in data.get("currencies", {}).items():
        currencies.append({
            "code": code,
            "name": info.get("name", ""),
            "symbol": info.get("symbol", ""),
        })

    return Country(
        name=data.get("name", {}).get("common", ""),
        official_name=data.get("name", {}).get("official", ""),
        cca2=data.get("cca2", ""),
        cca3=data.get("cca3", ""),
        capital=data.get("capital", []),
        region=data.get("region", ""),
        subregion=data.get("subregion", ""),
        population=data.get("population", 0),
        area=data.get("area"),
        languages=languages,
        currencies=currencies,
        flag_emoji=data.get("flag", ""),
        flag_png=data.get("flags", {}).get("png", ""),
    ).model_dump()


@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="get_country",
            description="Get detailed information about a country by name or code.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Country name or 2/3-letter code (e.g., 'France', 'US', 'USA')",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="search_countries",
            description="Search for countries by partial name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Partial country name to search (e.g., 'united' matches United States, United Kingdom)",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="by_region",
            description="Get all countries in a region.",
            inputSchema={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "description": "Region name: Africa, Americas, Asia, Europe, Oceania",
                    },
                },
                "required": ["region"],
            },
        ),
        Tool(
            name="by_currency",
            description="Get countries using a specific currency.",
            inputSchema={
                "type": "object",
                "properties": {
                    "currency": {
                        "type": "string",
                        "description": "Currency code (e.g., 'USD', 'EUR', 'GBP')",
                    },
                },
                "required": ["currency"],
            },
        ),
        Tool(
            name="by_language",
            description="Get countries where a language is spoken.",
            inputSchema={
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "description": "Language name or code (e.g., 'spanish', 'french', 'ara')",
                    },
                },
                "required": ["language"],
            },
        ),
    ]


# =============================================================================
# Tool Implementations
# =============================================================================

async def get_country(name: str) -> Dict[str, Any]:
    """Get country by name or code."""
    name = name.strip()

    # Try as 2-letter code first
    if len(name) == 2:
        try:
            url = f"{API_BASE}/alpha/{name.upper()}?fields={FIELDS}"
            data = _make_request(url)
            return _parse_country(data)
        except ValueError:
            pass

    # Try as 3-letter code
    if len(name) == 3:
        try:
            url = f"{API_BASE}/alpha/{name.upper()}?fields={FIELDS}"
            data = _make_request(url)
            return _parse_country(data)
        except ValueError:
            pass

    # Try exact name match
    encoded_name = urllib.parse.quote(name)
    url = f"{API_BASE}/name/{encoded_name}?fullText=true&fields={FIELDS}"
    try:
        data = _make_request(url)
        if data:
            return _parse_country(data[0])
    except ValueError:
        pass

    # Try partial name match
    url = f"{API_BASE}/name/{encoded_name}?fields={FIELDS}"
    data = _make_request(url)
    if data:
        return _parse_country(data[0])

    raise ValueError(f"Country not found: {name}")


async def search_countries(name: str) -> List[Dict[str, Any]]:
    """Search countries by partial name."""
    encoded_name = urllib.parse.quote(name.strip())
    url = f"{API_BASE}/name/{encoded_name}?fields={FIELDS}"

    data = _make_request(url)
    return [_parse_country(c) for c in data]


async def by_region(region: str) -> List[Dict[str, Any]]:
    """Get all countries in a region."""
    encoded_region = urllib.parse.quote(region.strip())
    url = f"{API_BASE}/region/{encoded_region}?fields={FIELDS}"

    data = _make_request(url)
    return [_parse_country(c) for c in data]


async def by_currency(currency: str) -> List[Dict[str, Any]]:
    """Get countries using a specific currency."""
    encoded_currency = urllib.parse.quote(currency.strip().upper())
    url = f"{API_BASE}/currency/{encoded_currency}?fields={FIELDS}"

    data = _make_request(url)
    return [_parse_country(c) for c in data]


async def by_language(language: str) -> List[Dict[str, Any]]:
    """Get countries where a language is spoken."""
    encoded_language = urllib.parse.quote(language.strip().lower())
    url = f"{API_BASE}/lang/{encoded_language}?fields={FIELDS}"

    data = _make_request(url)
    return [_parse_country(c) for c in data]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    logger.info(f"Tool called: {name} with args: {arguments}")

    try:
        if name == "get_country":
            result = await get_country(name=arguments.get("name", ""))
        elif name == "search_countries":
            result = await search_countries(name=arguments.get("name", ""))
        elif name == "by_region":
            result = await by_region(region=arguments.get("region", ""))
        elif name == "by_currency":
            result = await by_currency(currency=arguments.get("currency", ""))
        elif name == "by_language":
            result = await by_language(language=arguments.get("language", ""))
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main() -> None:
    logger.info(f"Starting {SERVER_NAME} MCP server (REST Countries API)...")
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
