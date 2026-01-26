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


class CoordinatesInfo(BaseModel):
    """Geographic coordinates for a city."""
    
    city: str = Field(description="City name")
    country: str = Field(description="Country code")
    latitude: float = Field(description="Latitude in decimal degrees")
    longitude: float = Field(description="Longitude in decimal degrees")
    timezone: str = Field(description="Timezone identifier (e.g., 'America/New_York')")
    population: Optional[int] = Field(None, description="City population if available")


# =============================================================================
# Sports Schemas (ESPN-based multi-sport)
# =============================================================================

class GameInfo(BaseModel):
    """Information about a sports game/match."""
    
    home_team: str = Field(description="Home team name")
    away_team: str = Field(description="Away team name")
    home_score: int = Field(description="Home team score")
    away_score: int = Field(description="Away team score")
    score: Optional[str] = Field(None, description="Score string like '24-17' (None if not started)")
    status: str = Field(description="Game status: SCHEDULED, LIVE, FINAL")
    detail: str = Field(description="Status detail (e.g., '4th Quarter', 'Final', '3:30 PM ET')")
    start_time: str = Field(description="Game start time in ISO format")
    venue: str = Field(description="Venue/stadium name")
    broadcast: Optional[str] = Field(None, description="TV broadcast info")
    sport: str = Field(description="Sport name (e.g., 'NBA', 'NFL')")
    clock: Optional[str] = Field(None, description="Game clock (for live games)")
    period: Optional[int] = Field(None, description="Current period/quarter (for live games)")


class StandingEntry(BaseModel):
    """A team's position in standings."""
    
    rank: int = Field(description="Position in standings")
    team: str = Field(description="Team name")
    wins: int = Field(description="Wins")
    losses: int = Field(description="Losses")
    ties: Optional[int] = Field(None, description="Ties (for sports that have them)")
    pct: float = Field(description="Win percentage")
    points: Optional[int] = Field(None, description="Points (for leagues using points)")
    games_back: Optional[str] = Field(None, description="Games behind leader")
    streak: Optional[str] = Field(None, description="Current streak (e.g., 'W3')")
    division: Optional[str] = Field(None, description="Division/conference name")


class NewsArticle(BaseModel):
    """Sports news article."""
    
    headline: str = Field(description="Article headline")
    description: str = Field(description="Short description")
    published: str = Field(description="Publication date/time")
    link: str = Field(description="URL to full article")


class SportInfo(BaseModel):
    """Sport/league information."""
    
    code: str = Field(description="Sport code to use in API calls (e.g., 'nba', 'epl')")
    name: str = Field(description="Full sport/league name (e.g., 'NBA', 'Premier League')")


# =============================================================================
# Stock Schemas (Yahoo Finance-based)
# =============================================================================

class StockQuote(BaseModel):
    """Real-time stock quote information."""
    
    symbol: str = Field(description="Stock ticker symbol (e.g., 'AAPL')")
    name: str = Field(description="Company name")
    price: float = Field(description="Current price")
    change: float = Field(description="Price change from previous close")
    change_percent: float = Field(description="Percentage change from previous close")
    currency: str = Field(description="Currency code (e.g., 'USD')")
    exchange: str = Field(description="Exchange name")
    market_state: str = Field(description="Market state: PRE, REGULAR, POST, CLOSED")
    volume: int = Field(description="Trading volume")
    volume_formatted: str = Field(description="Volume with K/M/B suffix")
    day_high: Optional[float] = Field(None, description="Day's high price")
    day_low: Optional[float] = Field(None, description="Day's low price")
    year_high: Optional[float] = Field(None, description="52-week high")
    year_low: Optional[float] = Field(None, description="52-week low")
    market_cap: Optional[float] = Field(None, description="Market capitalization")
    market_cap_formatted: Optional[str] = Field(None, description="Market cap with B/T suffix")


class HistoricalPrice(BaseModel):
    """Historical OHLCV price data point."""
    
    date: str = Field(description="Date/time of the data point")
    open: Optional[float] = Field(None, description="Opening price")
    high: Optional[float] = Field(None, description="High price")
    low: Optional[float] = Field(None, description="Low price")
    close: Optional[float] = Field(None, description="Closing price")
    volume: int = Field(description="Trading volume")


# =============================================================================
# FX/Currency Schemas (Frankfurter API)
# =============================================================================

class ConversionResult(BaseModel):
    """Currency conversion result."""
    
    amount: float = Field(description="Original amount to convert")
    from_currency: str = Field(description="Source currency code (e.g., 'USD')")
    to_currency: str = Field(description="Target currency code (e.g., 'EUR')")
    result: float = Field(description="Converted amount")
    rate: float = Field(description="Exchange rate used")
    date: str = Field(description="Date of the exchange rate (YYYY-MM-DD)")


class ExchangeRates(BaseModel):
    """Exchange rates for a base currency."""
    
    base: str = Field(description="Base currency code")
    date: str = Field(description="Date of the rates (YYYY-MM-DD)")
    rates: dict = Field(description="Dictionary of currency codes to rates")


class RateHistoryEntry(BaseModel):
    """Single historical rate entry."""
    
    date: str = Field(description="Date (YYYY-MM-DD)")
    rate: float = Field(description="Exchange rate on this date")


class RateHistory(BaseModel):
    """Historical exchange rates over time."""
    
    base: str = Field(description="Base currency code")
    target: str = Field(description="Target currency code")
    start_date: str = Field(description="Start date (YYYY-MM-DD)")
    end_date: str = Field(description="End date (YYYY-MM-DD)")
    rates: List[RateHistoryEntry] = Field(description="List of daily rates")


# =============================================================================
# Wikipedia Schemas
# =============================================================================

class ArticleSummary(BaseModel):
    """Summary of a Wikipedia article."""
    
    title: str = Field(description="Article title")
    extract: str = Field(description="Plain-text summary (first paragraph)")
    description: str = Field(description="Short description of the topic")
    url: str = Field(description="URL to the full article")
    thumbnail: Optional[str] = Field(None, description="URL to article thumbnail image")
    coordinates: Optional[dict] = Field(None, description="Geographic coordinates if applicable (lat, lon)")


class SearchResult(BaseModel):
    """A single Wikipedia search result."""
    
    title: str = Field(description="Article title")
    description: str = Field(description="Short description or snippet")
    url: str = Field(description="URL to the article")


class SearchResults(BaseModel):
    """Wikipedia search results."""
    
    query: str = Field(description="Original search query")
    results: List[SearchResult] = Field(description="List of matching articles")


class OnThisDayEvent(BaseModel):
    """A historical event that happened on a specific date."""
    
    year: Optional[int] = Field(None, description="Year the event occurred")
    text: str = Field(description="Description of the event")
    pages: List[str] = Field(description="Related Wikipedia article titles")


class OnThisDayResponse(BaseModel):
    """Events that happened on a specific date in history."""
    
    date: str = Field(description="Date in MM-DD format")
    events: List[OnThisDayEvent] = Field(description="List of historical events")


class TrendingArticle(BaseModel):
    """A trending Wikipedia article."""
    
    rank: int = Field(description="Rank in trending list (1 = most views)")
    title: str = Field(description="Article title")
    views: int = Field(description="Number of page views")
    url: str = Field(description="URL to the article")


class TrendingResponse(BaseModel):
    """Most-read articles on Wikipedia."""
    
    date: str = Field(description="Date for the trending data (YYYY-MM-DD)")
    articles: List[TrendingArticle] = Field(description="List of trending articles")


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
        CoordinatesInfo,
        GameInfo,
        StandingEntry,
        NewsArticle,
        SportInfo,
        StockQuote,
        HistoricalPrice,
        ConversionResult,
        ExchangeRates,
        RateHistory,
        RateHistoryEntry,
        ArticleSummary,
        SearchResult,
        SearchResults,
        OnThisDayEvent,
        OnThisDayResponse,
        TrendingArticle,
        TrendingResponse,
    ]
    return {
        model.__name__: {
            "description": model.__doc__,
            "schema": model.model_json_schema(),
        }
        for model in models
    }
