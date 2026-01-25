#!/usr/bin/env python3
"""
Soccer/Football MCP Server

Provides live soccer match information using football-data.org API.

Setup:
    1. Get a free API key from https://www.football-data.org/
    2. Set environment variable: FOOTBALL_API_KEY=your_key
    
Usage in sandbox:
    matches = await mcp_soccer.get_live_matches()
    upcoming = await mcp_soccer.get_upcoming_matches(competition="PL", days=3)
"""

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Import schemas for validation and documentation
try:
    from schemas import MatchInfo, StandingsInfo, TeamStanding, CompetitionInfo, schema_to_description
    HAS_SCHEMAS = True
except ImportError:
    HAS_SCHEMAS = False

SERVER_NAME = "soccer"
API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
BASE_URL = "https://api.football-data.org/v4"

# Popular competition codes
COMPETITIONS = {
    "PL": "Premier League",
    "PD": "La Liga",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
    "CL": "Champions League",
    "EC": "European Championship",
    "WC": "World Cup",
}

logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")
logger = logging.getLogger(SERVER_NAME)

app = Server(SERVER_NAME)


# =============================================================================
# Tool Definitions (auto-generated from schemas when available)
# =============================================================================

def _get_live_matches_description() -> str:
    """Generate description with output schema if available."""
    base = "Get currently live soccer/football matches worldwide."
    if HAS_SCHEMAS:
        return f"{base}\n\nReturns list of MatchInfo objects.\n\n{schema_to_description(MatchInfo)}"
    return base

def _get_upcoming_matches_description() -> str:
    """Generate description with output schema if available."""
    base = "Get upcoming soccer matches in the next few days."
    if HAS_SCHEMAS:
        return f"{base}\n\nReturns list of MatchInfo objects.\n\n{schema_to_description(MatchInfo)}"
    return base

def _get_standings_description() -> str:
    """Generate description with output schema if available."""
    base = "Get current league standings/table for a competition."
    if HAS_SCHEMAS:
        return f"{base}\n\n{schema_to_description(StandingsInfo)}"
    return base


@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="get_live_matches",
            description=_get_live_matches_description(),
            inputSchema={
                "type": "object",
                "properties": {
                    "competition": {
                        "type": "string",
                        "description": f"Filter by competition code: {', '.join(COMPETITIONS.keys())}. Leave empty for all.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_upcoming_matches",
            description=_get_upcoming_matches_description(),
            inputSchema={
                "type": "object",
                "properties": {
                    "competition": {
                        "type": "string",
                        "description": f"Competition code: {', '.join(COMPETITIONS.keys())}. Leave empty for all.",
                    },
                    "days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 14,
                        "default": 3,
                        "description": "Number of days ahead to check (1-14)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_standings",
            description=_get_standings_description(),
            inputSchema={
                "type": "object",
                "properties": {
                    "competition": {
                        "type": "string",
                        "enum": list(COMPETITIONS.keys()),
                        "description": f"Competition code. Options: {', '.join(f'{k} ({v})' for k, v in COMPETITIONS.items())}",
                    },
                },
                "required": ["competition"],
            },
        ),
        Tool(
            name="list_competitions",
            description="List available competition codes and their names.",
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

def _make_request(endpoint: str) -> Dict[str, Any]:
    """Make HTTP request to football-data.org API."""
    url = f"{BASE_URL}{endpoint}"
    headers = {"X-Auth-Token": API_KEY} if API_KEY else {}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ValueError("Invalid API key. Set FOOTBALL_API_KEY environment variable.")
        elif e.code == 403:
            raise ValueError("API rate limit exceeded or subscription required")
        elif e.code == 404:
            raise ValueError("Competition not found")
        raise
    except urllib.error.URLError as e:
        raise ValueError(f"Network error: {e.reason}")


def _format_match(match: Dict[str, Any], include_datetime: bool = False) -> Dict[str, Any]:
    """Format a match object to match MatchInfo schema."""
    home = match.get("homeTeam", {})
    away = match.get("awayTeam", {})
    score = match.get("score", {})
    full_time = score.get("fullTime", {})
    
    home_score = full_time.get("home")
    away_score = full_time.get("away")
    score_str = f"{home_score}-{away_score}" if home_score is not None else None
    
    # Map API status to our schema status
    status_map = {
        "SCHEDULED": "SCHEDULED",
        "TIMED": "SCHEDULED",
        "IN_PLAY": "LIVE",
        "PAUSED": "HALFTIME",
        "FINISHED": "FINISHED",
        "SUSPENDED": "POSTPONED",
        "POSTPONED": "POSTPONED",
        "CANCELLED": "POSTPONED",
    }
    
    result = {
        "home": home.get("name", "Unknown"),
        "away": away.get("name", "Unknown"),
        "score": score_str,
        "status": status_map.get(match.get("status", ""), match.get("status", "SCHEDULED")),
        "minute": match.get("minute"),
        "competition": match.get("competition", {}).get("name", ""),
        "venue": home.get("venue", home.get("name", "Unknown").split()[0]),  # Use home city as venue fallback
    }
    
    if include_datetime:
        result["datetime"] = match.get("utcDate", "")
    
    return result


async def get_live_matches(competition: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get currently live matches. Returns list of MatchInfo objects."""
    
    if not API_KEY:
        # Mock data matching MatchInfo schema
        return [
            {
                "home": "Manchester United",
                "away": "Liverpool",
                "score": "1-2",
                "status": "LIVE",
                "minute": 67,
                "competition": "Premier League",
                "venue": "Manchester",
                "_note": "Mock data - set FOOTBALL_API_KEY for real data",
            },
            {
                "home": "Real Madrid",
                "away": "Barcelona",
                "score": "0-0",
                "status": "LIVE",
                "minute": 23,
                "competition": "La Liga",
                "venue": "Madrid",
            },
        ]
    
    endpoint = "/matches?status=LIVE"
    if competition:
        endpoint = f"/competitions/{competition}/matches?status=LIVE"
    
    data = _make_request(endpoint)
    matches = [_format_match(m) for m in data.get("matches", [])]
    
    # Validate with schema if available
    if HAS_SCHEMAS:
        return [MatchInfo(**m).model_dump() for m in matches]
    return matches


async def get_upcoming_matches(competition: Optional[str] = None, days: int = 3) -> List[Dict[str, Any]]:
    """Get upcoming matches in the next N days. Returns list of MatchInfo objects."""
    
    if not API_KEY:
        # Mock data matching MatchInfo schema
        return [
            {
                "home": "Arsenal",
                "away": "Chelsea",
                "score": None,
                "status": "SCHEDULED",
                "minute": None,
                "competition": "Premier League",
                "venue": "London",
                "datetime": "2026-01-25T15:00:00Z",
                "_note": "Mock data - set FOOTBALL_API_KEY for real data",
            },
            {
                "home": "Bayern Munich",
                "away": "Dortmund",
                "score": None,
                "status": "SCHEDULED",
                "minute": None,
                "competition": "Bundesliga",
                "venue": "Munich",
                "datetime": "2026-01-26T17:30:00Z",
            },
        ]
    
    today = datetime.utcnow().strftime("%Y-%m-%d")
    future = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")
    
    if competition:
        endpoint = f"/competitions/{competition}/matches?dateFrom={today}&dateTo={future}"
    else:
        endpoint = f"/matches?dateFrom={today}&dateTo={future}"
    
    data = _make_request(endpoint)
    matches = [_format_match(m, include_datetime=True) for m in data.get("matches", [])]
    
    # Validate with schema if available
    if HAS_SCHEMAS:
        return [MatchInfo(**m).model_dump() for m in matches]
    return matches


async def get_standings(competition: str) -> Dict[str, Any]:
    """Get league standings for a competition. Returns StandingsInfo object."""
    
    if not API_KEY:
        # Mock data matching StandingsInfo schema
        return {
            "competition": COMPETITIONS.get(competition, competition),
            "competition_code": competition,
            "season": "2025-2026",
            "standings": [
                {"position": 1, "team": "Liverpool", "played": 20, "won": 15, "drawn": 3, "lost": 2, "goals_for": 48, "goals_against": 18, "goal_difference": 30, "points": 48},
                {"position": 2, "team": "Arsenal", "played": 20, "won": 14, "drawn": 4, "lost": 2, "goals_for": 42, "goals_against": 15, "goal_difference": 27, "points": 46},
                {"position": 3, "team": "Manchester City", "played": 20, "won": 13, "drawn": 4, "lost": 3, "goals_for": 45, "goals_against": 22, "goal_difference": 23, "points": 43},
            ],
            "_note": "Mock data - set FOOTBALL_API_KEY for real data",
        }
    
    endpoint = f"/competitions/{competition}/standings"
    data = _make_request(endpoint)
    
    standings = []
    for table in data.get("standings", []):
        if table.get("type") == "TOTAL":
            for row in table.get("table", []):
                standings.append({
                    "position": row.get("position"),
                    "team": row.get("team", {}).get("name"),
                    "played": row.get("playedGames"),
                    "won": row.get("won"),
                    "drawn": row.get("draw"),
                    "lost": row.get("lost"),
                    "goals_for": row.get("goalsFor"),
                    "goals_against": row.get("goalsAgainst"),
                    "goal_difference": row.get("goalDifference"),
                    "points": row.get("points"),
                })
    
    result = {
        "competition": data.get("competition", {}).get("name", competition),
        "competition_code": competition,
        "season": f"{data.get('season', {}).get('startDate', '')[:4]}-{data.get('season', {}).get('endDate', '')[:4]}",
        "standings": standings,
    }
    
    # Validate with schema if available
    if HAS_SCHEMAS:
        return StandingsInfo(**result).model_dump()
    return result


async def list_competitions() -> Dict[str, Any]:
    """List available competition codes."""
    return {
        "competitions": [
            {"code": code, "name": name}
            for code, name in COMPETITIONS.items()
        ]
    }


# =============================================================================
# Tool Dispatcher
# =============================================================================

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    logger.info(f"Tool called: {name} with args: {arguments}")
    
    try:
        if name == "get_live_matches":
            result = await get_live_matches(
                competition=arguments.get("competition"),
            )
        elif name == "get_upcoming_matches":
            result = await get_upcoming_matches(
                competition=arguments.get("competition"),
                days=arguments.get("days", 3),
            )
        elif name == "get_standings":
            result = await get_standings(
                competition=arguments["competition"],
            )
        elif name == "list_competitions":
            result = await list_competitions()
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# =============================================================================
# Entry Point
# =============================================================================

async def main() -> None:
    logger.info(f"Starting {SERVER_NAME} MCP server...")
    if not API_KEY:
        logger.warning("FOOTBALL_API_KEY not set - using mock data")
    
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
