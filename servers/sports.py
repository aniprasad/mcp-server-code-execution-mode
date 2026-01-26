#!/usr/bin/env python3
"""
Sports MCP Server

Provides live scores, schedules, and standings for multiple sports using ESPN's API.

Supported sports:
- NFL (American Football)
- NBA (Basketball)
- MLB (Baseball)
- NHL (Hockey)
- Soccer (Premier League, La Liga, MLS, etc.)
- F1 (Formula 1)

Usage in sandbox:
    games = await mcp_sports.scoreboard(sport="nba")
    standings = await mcp_sports.standings(sport="nfl")
    schedule = await mcp_sports.schedule(sport="mlb", team="yankees")
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Import schemas for validation
try:
    from schemas import GameInfo, StandingEntry, NewsArticle, SportInfo
    HAS_SCHEMAS = True
except ImportError:
    HAS_SCHEMAS = False

SERVER_NAME = "sports"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"

# Sport/League mapping for ESPN API
SPORTS = {
    # US Sports
    "nfl": {"sport": "football", "league": "nfl", "name": "NFL"},
    "nba": {"sport": "basketball", "league": "nba", "name": "NBA"},
    "wnba": {"sport": "basketball", "league": "wnba", "name": "WNBA"},
    "mlb": {"sport": "baseball", "league": "mlb", "name": "MLB"},
    "nhl": {"sport": "hockey", "league": "nhl", "name": "NHL"},
    "ncaaf": {"sport": "football", "league": "college-football", "name": "College Football"},
    "ncaab": {"sport": "basketball", "league": "mens-college-basketball", "name": "College Basketball"},
    "mls": {"sport": "soccer", "league": "usa.1", "name": "MLS"},
    
    # Soccer leagues
    "epl": {"sport": "soccer", "league": "eng.1", "name": "Premier League"},
    "laliga": {"sport": "soccer", "league": "esp.1", "name": "La Liga"},
    "bundesliga": {"sport": "soccer", "league": "ger.1", "name": "Bundesliga"},
    "seriea": {"sport": "soccer", "league": "ita.1", "name": "Serie A"},
    "ligue1": {"sport": "soccer", "league": "fra.1", "name": "Ligue 1"},
    "ucl": {"sport": "soccer", "league": "uefa.champions", "name": "Champions League"},
    
    # Motorsport
    "f1": {"sport": "racing", "league": "f1", "name": "Formula 1"},
}

logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")
logger = logging.getLogger(SERVER_NAME)

app = Server(SERVER_NAME)


# =============================================================================
# ESPN API Helpers
# =============================================================================

def _espn_request(endpoint: str) -> Dict[str, Any]:
    """Make HTTP request to ESPN API."""
    try:
        req = urllib.request.Request(
            endpoint,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"Not found: {endpoint}")
        raise ValueError(f"ESPN API error: {e.code}")
    except urllib.error.URLError as e:
        raise ValueError(f"Network error: {e.reason}")


def _get_espn_url(sport_key: str, endpoint: str) -> str:
    """Build ESPN API URL for a sport."""
    if sport_key not in SPORTS:
        raise ValueError(f"Unknown sport: {sport_key}. Available: {', '.join(SPORTS.keys())}")
    
    info = SPORTS[sport_key]
    return f"{ESPN_BASE}/{info['sport']}/{info['league']}/{endpoint}"


def _format_game(event: Dict[str, Any], sport_key: str) -> Dict[str, Any]:
    """Format ESPN event to standardized game format."""
    competition = event.get("competitions", [{}])[0]
    competitors = competition.get("competitors", [])
    
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
    
    home_team = home.get("team", {})
    away_team = away.get("team", {})
    
    status = event.get("status", {})
    status_type = status.get("type", {})
    
    # Determine game state
    state = status_type.get("state", "pre")  # pre, in, post
    if state == "in":
        game_status = "LIVE"
    elif state == "post":
        game_status = "FINAL"
    else:
        game_status = "SCHEDULED"
    
    # Build score string - score can be str, int, dict, or missing
    home_score_raw = home.get("score", "0")
    away_score_raw = away.get("score", "0")
    
    # Handle various score formats from ESPN API
    def parse_score(val):
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
        if isinstance(val, dict):
            return val.get("value", 0)
        return 0
    
    home_score = parse_score(home_score_raw)
    away_score = parse_score(away_score_raw)
    score = f"{away_score}-{home_score}" if state != "pre" else None
    
    # Get display clock/period
    display_clock = status.get("displayClock", "")
    period = status.get("period", 0)
    
    result = {
        "home_team": home_team.get("displayName", home_team.get("name", "TBD")),
        "away_team": away_team.get("displayName", away_team.get("name", "TBD")),
        "home_score": home_score,
        "away_score": away_score,
        "score": score,
        "status": game_status,
        "detail": status_type.get("shortDetail", ""),
        "start_time": event.get("date", ""),
        "venue": competition.get("venue", {}).get("fullName", ""),
        "broadcast": ", ".join(
            b.get("names", [""])[0] if b.get("names") else ""
            for b in competition.get("broadcasts", [])
        ) or None,
        "sport": SPORTS[sport_key]["name"],
    }
    
    # Add period/clock for live games
    if game_status == "LIVE":
        result["clock"] = display_clock
        result["period"] = period
    
    return result


def _format_standing(entry: Dict[str, Any], sport_key: str) -> Dict[str, Any]:
    """Format ESPN standings entry."""
    team = entry.get("team", {})
    stats = {s.get("name"): s.get("value") for s in entry.get("stats", [])}
    
    return {
        "rank": int(stats.get("playoffSeed", stats.get("rank", 0))),
        "team": team.get("displayName", team.get("name", "")),
        "wins": int(stats.get("wins", 0)),
        "losses": int(stats.get("losses", 0)),
        "ties": int(stats.get("ties", 0)) if "ties" in stats else None,
        "pct": float(stats.get("winPercent", stats.get("winPct", 0))),
        "points": int(stats.get("points", 0)) if "points" in stats else None,
        "games_back": stats.get("gamesBehind", stats.get("GB")),
        "streak": stats.get("streak"),
        "last_10": stats.get("Last10"),
    }


# =============================================================================
# Tool Definitions
# =============================================================================

@app.list_tools()
async def list_tools() -> List[Tool]:
    sport_list = ", ".join(SPORTS.keys())
    
    return [
        Tool(
            name="scoreboard",
            description="Get today's games/matches with live scores.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sport": {
                        "type": "string",
                        "description": f"Sport/league code. Options: {sport_list}",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date in YYYYMMDD format. Default: today",
                    },
                },
                "required": ["sport"],
            },
        ),
        Tool(
            name="standings",
            description="Get current standings/rankings for a league.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sport": {
                        "type": "string",
                        "description": f"Sport/league code. Options: {sport_list}",
                    },
                    "group": {
                        "type": "string",
                        "description": "Division/conference filter (e.g., 'east', 'west', 'afc', 'nfc')",
                    },
                },
                "required": ["sport"],
            },
        ),
        Tool(
            name="team_schedule",
            description="Get upcoming games for a specific team.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sport": {
                        "type": "string",
                        "description": f"Sport/league code. Options: {sport_list}",
                    },
                    "team": {
                        "type": "string",
                        "description": "Team name or city (e.g., 'lakers', 'yankees', 'manchester united')",
                    },
                },
                "required": ["sport", "team"],
            },
        ),
        Tool(
            name="list_sports",
            description="List all available sports and league codes.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="news",
            description="Get latest sports news headlines.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sport": {
                        "type": "string",
                        "description": f"Sport/league code. Options: {sport_list}",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max headlines to return (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["sport"],
            },
        ),
    ]


# =============================================================================
# Tool Implementations
# =============================================================================

async def get_scoreboard(sport: str, date: Optional[str] = None) -> Dict[str, Any]:
    """Get scoreboard for a sport on a given date."""
    sport = sport.lower()
    
    url = _get_espn_url(sport, "scoreboard")
    if date:
        url += f"?dates={date}"
    
    data = _espn_request(url)
    
    events = data.get("events", [])
    games = [_format_game(e, sport) for e in events]
    
    return {
        "sport": SPORTS[sport]["name"],
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "games_count": len(games),
        "games": games,
    }


async def get_standings(sport: str, group: Optional[str] = None) -> Dict[str, Any]:
    """Get standings for a sport."""
    sport = sport.lower()
    
    # ESPN standings endpoint
    info = SPORTS[sport]
    url = f"https://site.api.espn.com/apis/v2/sports/{info['sport']}/{info['league']}/standings"
    
    data = _espn_request(url)
    
    standings = []
    for child in data.get("children", []):
        division_name = child.get("name", "")
        
        # Filter by group if specified
        if group and group.lower() not in division_name.lower():
            continue
        
        for entry in child.get("standings", {}).get("entries", []):
            standing = _format_standing(entry, sport)
            standing["division"] = division_name
            standings.append(standing)
    
    # Sort by rank/wins
    standings.sort(key=lambda x: (-x.get("wins", 0), x.get("rank", 999)))
    
    return {
        "sport": SPORTS[sport]["name"],
        "group": group,
        "teams_count": len(standings),
        "standings": standings,
    }


async def get_team_schedule(sport: str, team: str) -> Dict[str, Any]:
    """Search for a team and get their schedule."""
    sport = sport.lower()
    
    # First, search for the team
    info = SPORTS[sport]
    search_url = f"https://site.api.espn.com/apis/site/v2/sports/{info['sport']}/{info['league']}/teams"
    
    data = _espn_request(search_url)
    
    # Find matching team
    teams = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
    
    matched_team = None
    team_lower = team.lower()
    for t in teams:
        team_info = t.get("team", {})
        if (team_lower in team_info.get("displayName", "").lower() or
            team_lower in team_info.get("name", "").lower() or
            team_lower in team_info.get("location", "").lower() or
            team_lower in team_info.get("abbreviation", "").lower()):
            matched_team = team_info
            break
    
    if not matched_team:
        return {
            "error": f"Team '{team}' not found in {SPORTS[sport]['name']}",
            "available_teams": [t.get("team", {}).get("displayName") for t in teams[:20]],
        }
    
    # Get team schedule
    team_id = matched_team.get("id")
    schedule_url = f"https://site.api.espn.com/apis/site/v2/sports/{info['sport']}/{info['league']}/teams/{team_id}/schedule"
    
    schedule_data = _espn_request(schedule_url)
    
    events = schedule_data.get("events", [])
    games = []
    for event in events:
        game = _format_game(event, sport)
        games.append(game)
    
    return {
        "team": matched_team.get("displayName"),
        "sport": SPORTS[sport]["name"],
        "games_count": len(games),
        "games": games[-10:],  # Last/next 10 games
    }


async def list_sports() -> Dict[str, Any]:
    """List all available sports."""
    categories = {
        "US Sports": ["nfl", "nba", "wnba", "mlb", "nhl", "ncaaf", "ncaab", "mls"],
        "Soccer": ["epl", "laliga", "bundesliga", "seriea", "ligue1", "ucl"],
        "Motorsport": ["f1"],
    }
    
    result = {}
    for category, sports in categories.items():
        result[category] = [
            {"code": s, "name": SPORTS[s]["name"]}
            for s in sports
        ]
    
    return {"sports": result}


async def get_news(sport: str, limit: int = 5) -> Dict[str, Any]:
    """Get sports news headlines."""
    sport = sport.lower()
    
    info = SPORTS[sport]
    url = f"https://site.api.espn.com/apis/site/v2/sports/{info['sport']}/{info['league']}/news"
    
    data = _espn_request(url)
    
    articles = []
    for article in data.get("articles", [])[:limit]:
        articles.append({
            "headline": article.get("headline", ""),
            "description": article.get("description", ""),
            "published": article.get("published", ""),
            "link": article.get("links", {}).get("web", {}).get("href", ""),
        })
    
    return {
        "sport": SPORTS[sport]["name"],
        "articles_count": len(articles),
        "articles": articles,
    }


# =============================================================================
# Tool Dispatcher
# =============================================================================

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    logger.info(f"Tool called: {name} with args: {arguments}")
    
    try:
        if name == "scoreboard":
            result = await get_scoreboard(
                sport=arguments["sport"],
                date=arguments.get("date"),
            )
        elif name == "standings":
            result = await get_standings(
                sport=arguments["sport"],
                group=arguments.get("group"),
            )
        elif name == "team_schedule":
            result = await get_team_schedule(
                sport=arguments["sport"],
                team=arguments["team"],
            )
        elif name == "list_sports":
            result = await list_sports()
        elif name == "news":
            result = await get_news(
                sport=arguments["sport"],
                limit=arguments.get("limit", 5),
            )
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
