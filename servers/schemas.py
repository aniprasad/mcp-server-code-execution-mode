"""
Shared Pydantic schemas for MCP server outputs.

These schemas serve dual purposes:
1. Runtime validation of tool outputs
2. Auto-generated documentation for LLMs to understand output structures

Usage in tools:
    from schemas import MatchInfo, WeatherInfo
    
    # Return validated data:
    return MatchInfo(home="Arsenal", away="Chelsea", ...).model_dump()
    
    # Get schema for documentation:
    MatchInfo.model_json_schema()
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Weather Schemas
# =============================================================================

class WeatherInfo(BaseModel):
    """Current weather conditions for a city."""
    
    city: str = Field(description="City name")
    country: str = Field(description="Country code (e.g., 'US', 'UK')")
    temp: float = Field(description="Temperature in requested units")
    feels_like: float = Field(description="Feels-like temperature")
    conditions: str = Field(description="Weather description (e.g., 'cloudy', 'sunny', 'rainy')")
    humidity: int = Field(description="Humidity percentage (0-100)")
    wind_speed: float = Field(description="Wind speed in requested units")
    units: str = Field(description="Unit system: 'metric' (Celsius, m/s) or 'imperial' (Fahrenheit, mph)")


class ForecastDay(BaseModel):
    """Weather forecast for a single day."""
    
    date: str = Field(description="Date in YYYY-MM-DD format")
    temp_high: float = Field(description="High temperature for the day")
    temp_low: float = Field(description="Low temperature for the day")
    conditions: str = Field(description="Expected weather conditions")
    humidity: int = Field(description="Expected humidity percentage")
    precipitation_chance: Optional[int] = Field(None, description="Chance of precipitation (0-100)")


class ForecastInfo(BaseModel):
    """Multi-day weather forecast for a city."""
    
    city: str = Field(description="City name")
    country: str = Field(description="Country code")
    units: str = Field(description="Unit system used")
    days: List[ForecastDay] = Field(description="List of daily forecasts")


# =============================================================================
# Soccer/Football Schemas
# =============================================================================

class MatchInfo(BaseModel):
    """Information about a soccer/football match."""
    
    home: str = Field(description="Home team name")
    away: str = Field(description="Away team name")
    score: Optional[str] = Field(None, description="Current or final score like '2-1' (None if not started)")
    status: str = Field(description="Match status: SCHEDULED, LIVE, HALFTIME, FINISHED, POSTPONED")
    minute: Optional[int] = Field(None, description="Current minute of play (only for live matches)")
    competition: str = Field(description="League or tournament name")
    venue: str = Field(description="City where the match is played")
    datetime: Optional[str] = Field(None, description="Match date/time in ISO format (for scheduled matches)")


class TeamStanding(BaseModel):
    """A team's position in league standings."""
    
    position: int = Field(description="League position (1 = first place)")
    team: str = Field(description="Team name")
    played: int = Field(description="Games played")
    won: int = Field(description="Games won")
    drawn: int = Field(description="Games drawn")
    lost: int = Field(description="Games lost")
    goals_for: int = Field(description="Goals scored")
    goals_against: int = Field(description="Goals conceded")
    goal_difference: int = Field(description="Goal difference (for - against)")
    points: int = Field(description="Total points")


class StandingsInfo(BaseModel):
    """League standings/table for a competition."""
    
    competition: str = Field(description="Competition name")
    competition_code: str = Field(description="Competition code (e.g., 'PL', 'CL')")
    season: str = Field(description="Current season (e.g., '2025-2026')")
    standings: List[TeamStanding] = Field(description="List of team standings ordered by position")


class CompetitionInfo(BaseModel):
    """Information about a soccer competition."""
    
    code: str = Field(description="Competition code (e.g., 'PL', 'CL')")
    name: str = Field(description="Full competition name")
    country: Optional[str] = Field(None, description="Country (for domestic leagues)")


# =============================================================================
# Helper Functions
# =============================================================================

def schema_to_description(model: type[BaseModel]) -> str:
    """
    Convert a Pydantic model to a human-readable description for tool documentation.
    
    Example:
        >>> print(schema_to_description(MatchInfo))
        Information about a soccer/football match.
        
        Fields:
          - home (str): Home team name
          - away (str): Away team name
          ...
    """
    schema = model.model_json_schema()
    lines = [model.__doc__ or model.__name__, ""]
    lines.append("Fields:")
    
    for name, prop in schema.get("properties", {}).items():
        type_str = prop.get("type", "any")
        # Handle optional fields
        if "anyOf" in prop:
            types = [t.get("type", "null") for t in prop["anyOf"]]
            type_str = " | ".join(t for t in types if t != "null")
            if "null" in types:
                type_str += " (optional)"
        desc = prop.get("description", "")
        lines.append(f"  - {name} ({type_str}): {desc}")
    
    return "\n".join(lines)


def get_all_schemas() -> dict:
    """
    Return all available output schemas for discovery.
    
    Returns:
        Dict mapping schema names to their JSON schemas.
    """
    models = [
        WeatherInfo,
        ForecastInfo,
        ForecastDay,
        MatchInfo,
        TeamStanding,
        StandingsInfo,
        CompetitionInfo,
    ]
    return {
        model.__name__: {
            "description": model.__doc__,
            "schema": model.model_json_schema(),
        }
        for model in models
    }
