"""
Shared Pydantic schemas for MCP server outputs.

These schemas serve dual purposes:
1. Runtime validation of tool outputs
2. Auto-generated documentation for LLMs to understand output structures

Usage in tools:
    from schemas import WeatherInfo, StockQuote
    
    # Return validated data:
    return WeatherInfo(city="Seattle", temp=72.5, ...).model_dump()
    
    # Get schema for documentation:
    WeatherInfo.model_json_schema()
"""

from typing import List, Optional, Union

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
    last_10: Optional[str] = Field(None, description="Record in last 10 games")
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


class RankingEntry(BaseModel):
    """A team's position in a ranking poll (e.g., AP Top 25)."""
    
    rank: int = Field(description="Current ranking position")
    previous_rank: Optional[int] = Field(None, description="Previous week's ranking")
    team: str = Field(description="Team name")
    abbreviation: str = Field(description="Team abbreviation")
    points: Optional[float] = Field(None, description="Voting points received")
    first_place_votes: Optional[int] = Field(None, description="Number of first-place votes")
    trend: Optional[str] = Field(None, description="Movement trend: 'up', 'down', or '-'")
    record: Optional[str] = Field(None, description="Team's win-loss record (e.g., '12-1')")


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
    timestamp: Optional[str] = Field(None, description="ISO timestamp when quote was fetched")
    crypto_name: Optional[str] = Field(None, description="Crypto name (only present for crypto quotes)")


class HistoricalPrice(BaseModel):
    """Historical OHLCV price data point."""
    
    date: str = Field(description="Date/time of the data point")
    open: Optional[float] = Field(None, description="Opening price")
    high: Optional[float] = Field(None, description="High price")
    low: Optional[float] = Field(None, description="Low price")
    close: Optional[float] = Field(None, description="Closing price")
    volume: int = Field(description="Trading volume")


class MarketIndex(BaseModel):
    """A single market index quote."""
    
    symbol: str = Field(description="Index symbol (e.g., '^GSPC' for S&P 500)")
    name: str = Field(description="Index name (e.g., 'S&P 500')")
    price: float = Field(description="Current index value")
    change: float = Field(description="Change from previous close")
    change_percent: float = Field(description="Percentage change")


class MarketSummary(BaseModel):
    """Summary of major market indices."""
    
    timestamp: str = Field(description="ISO timestamp of the data")
    indices_count: int = Field(description="Number of indices returned")
    indices: List[MarketIndex] = Field(description="List of market index quotes")


class StockSearchResult(BaseModel):
    """A single stock search result."""
    
    symbol: str = Field(description="Stock ticker symbol")
    name: str = Field(description="Company/security name")
    type: str = Field(description="Security type (e.g., 'S' for stock, 'E' for ETF)")
    exchange: str = Field(description="Exchange code")


class StockHistory(BaseModel):
    """Historical price data for a stock."""
    
    symbol: str = Field(description="Stock ticker symbol")
    name: str = Field(description="Company name")
    currency: str = Field(description="Currency code")
    period: str = Field(description="Time period requested")
    interval: str = Field(description="Data interval (e.g., '1d', '1h')")
    prices_count: int = Field(description="Number of price points")
    prices: List[HistoricalPrice] = Field(description="List of OHLCV price points")


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
# Microsoft Forms Schemas
# =============================================================================

class FormQuestion(BaseModel):
    """A question in a Microsoft Form."""
    
    id: str = Field(description="Question ID - format: 'r' + 32 hex chars (e.g., 'r624132511dcd4fe080e7eee074e01fad')")
    title: str = Field(description="Question text")
    type: str = Field(description="Question type: 'choice', 'rating', or 'text'")
    required: bool = Field(description="Whether the question is required")
    choices: Optional[List[str]] = Field(None, description="Available choices (for choice questions only)")
    ratingScale: Optional[int] = Field(None, description="Max rating value, e.g., 5 means scale 1-5 (for rating questions only)")


class FormSummaryQuestion(BaseModel):
    """Aggregated summary statistics for a single question."""
    
    questionId: str = Field(description="Question ID - same format as FormQuestion.id, use to join with questions dict")
    type: str = Field(description="Question type: 'choice', 'rating', or 'text'")
    average: Optional[float] = Field(None, description="Average rating value (for rating questions only)")
    count: Optional[int] = Field(None, description="Number of responses to this question")
    distribution: Optional[dict] = Field(None, description="Response counts - for choice: {'Yes': 42, 'No': 8}, for rating: {'1': 5, '2': 10, '5': 85}")
    recentValues: Optional[List[str]] = Field(None, description="Sample text responses (for text questions only)")


class FormResponse(BaseModel):
    """A single response to a Microsoft Form."""
    
    id: int = Field(description="Response ID - sequential integer, unique per form")
    submitDate: str = Field(description="Submission timestamp in ISO 8601 format with timezone (e.g., '2025-01-13T22:54:45.499Z')")
    responder: str = Field(description="'anonymous' if form has anonymous setting, otherwise responder's email")
    answers: dict = Field(description="Dict of question_id -> answer. Values: str (choice/text), int (rating 1-N), list[str] (multi-select)")


class FormSummaryResult(BaseModel):
    """Summary statistics for a Microsoft Form (from get_form_summary). Fast - no individual responses."""
    
    title: str = Field(description="Form title")
    responseCount: int = Field(description="Total number of responses")
    avgSubmitTimeSeconds: Optional[float] = Field(None, description="Average time to complete form in seconds")
    questions: dict = Field(description="Dict of question_id -> FormSummaryQuestion. Keys are 'r' + 32 hex chars")


class FormDataResult(BaseModel):
    """Complete form data including structure, summary, and individual responses."""
    
    title: str = Field(description="Form title")
    description: str = Field(description="Form description")
    responseCount: int = Field(description="Total number of responses")
    questions: dict = Field(description="Dict of question_id -> FormQuestion. Keys are 'r' + 32 hex chars")
    summary: dict = Field(description="Dict of question_id -> FormSummaryQuestion. Same keys as questions dict")
    responses: List[FormResponse] = Field(description="Individual responses, ordered by id (sequential). Use answers[question_id] to get values")


# =============================================================================
# Countries Schemas (REST Countries API)
# =============================================================================

class Country(BaseModel):
    """Information about a country."""

    name: str = Field(description="Common country name (e.g., 'France')")
    official_name: str = Field(description="Official country name (e.g., 'French Republic')")
    cca2: str = Field(description="ISO 3166-1 alpha-2 code (e.g., 'FR')")
    cca3: str = Field(description="ISO 3166-1 alpha-3 code (e.g., 'FRA')")
    capital: List[str] = Field(description="List of capital cities (some countries have multiple)")
    region: str = Field(description="Geographic region (e.g., 'Europe', 'Asia')")
    subregion: str = Field(description="Geographic subregion (e.g., 'Western Europe')")
    population: int = Field(description="Country population")
    area: Optional[float] = Field(None, description="Land area in square kilometers")
    languages: List[str] = Field(description="Official languages spoken")
    currencies: List[dict] = Field(description="List of currencies: [{code, name, symbol}]")
    flag_emoji: str = Field(description="Flag emoji character")
    flag_png: str = Field(description="URL to flag PNG image")


# =============================================================================
# Open Library Schemas
# =============================================================================

class OLBook(BaseModel):
    """Book information from Open Library."""

    key: str = Field(description="Open Library work key (e.g., '/works/OL45804W')")
    title: str = Field(description="Book title")
    authors: List[str] = Field(description="List of author names")
    first_publish_year: Optional[Union[int, str]] = Field(None, description="Year first published (int from search, string from edition)")
    isbn: List[str] = Field(description="List of ISBNs (10 and 13 digit)")
    subjects: List[str] = Field(description="Subject categories")
    cover_url: Optional[str] = Field(None, description="URL to book cover image")
    edition_count: int = Field(description="Number of editions")
    language: List[str] = Field(description="Languages available")
    description: Optional[str] = Field(None, description="Book description/synopsis")
    publishers: Optional[List[str]] = Field(None, description="Publishers")
    publish_date: Optional[str] = Field(None, description="Publication date")
    number_of_pages: Optional[int] = Field(None, description="Page count")


class OLAuthor(BaseModel):
    """Author information from Open Library."""

    key: str = Field(description="Open Library author key (e.g., '/authors/OL34184A')")
    name: str = Field(description="Author name")
    birth_date: Optional[str] = Field(None, description="Birth date")
    death_date: Optional[str] = Field(None, description="Death date (if applicable)")
    bio: Optional[str] = Field(None, description="Author biography")
    works_count: Optional[int] = Field(None, description="Number of works by author")
    photo_url: Optional[str] = Field(None, description="URL to author photo")


class OLSearchResult(BaseModel):
    """Open Library search results."""

    query: str = Field(description="Original search query")
    total: int = Field(description="Total number of results found")
    books: List[OLBook] = Field(description="List of matching books")


# =============================================================================
# Hacker News Schemas
# =============================================================================

class HNStory(BaseModel):
    """A Hacker News story/post."""

    id: int = Field(description="Story ID")
    title: str = Field(description="Story title")
    url: Optional[str] = Field(None, description="URL to external content (None for Ask HN, Show HN)")
    score: int = Field(description="Upvote score")
    by: str = Field(description="Username who submitted")
    time: Optional[str] = Field(None, description="Submission time (ISO 8601)")
    time_unix: int = Field(description="Submission time (Unix timestamp)")
    descendants: int = Field(description="Total comment count")
    type: str = Field(description="Item type: story, job, poll")
    text: Optional[str] = Field(None, description="HTML text content (for Ask HN, etc.)")


class HNUser(BaseModel):
    """A Hacker News user profile."""

    id: str = Field(description="Username")
    karma: int = Field(description="User's karma score")
    about: Optional[str] = Field(None, description="User's about text (HTML)")
    created: Optional[str] = Field(None, description="Account creation time (ISO 8601)")
    created_unix: int = Field(description="Account creation time (Unix timestamp)")
    submitted_count: int = Field(description="Number of submissions (stories + comments)")


class HNSearchHit(BaseModel):
    """A single search result from Algolia HN Search."""

    objectID: str = Field(description="Algolia object ID")
    title: str = Field(description="Story title")
    url: Optional[str] = Field(None, description="Story URL")
    author: str = Field(description="Author username")
    points: int = Field(description="Upvote points")
    num_comments: int = Field(description="Number of comments")
    created_at: str = Field(description="Creation time (ISO 8601)")
    story_id: Optional[int] = Field(None, description="Parent story ID (for comments)")
    type: str = Field(description="Type: story, comment")


class HNSearchResult(BaseModel):
    """Hacker News search results from Algolia."""

    query: str = Field(description="Original search query")
    total: int = Field(description="Total number of results")
    hits: List[HNSearchHit] = Field(description="List of search hits")


# =============================================================================
# Browser Schemas
# =============================================================================

class BrowserAction(BaseModel):
    """An interactive element on a web page."""
    
    type: str = Field(description="Action type: BUTTON, LINK, INPUT, etc.")
    selector: str = Field(description="Element index for use with execute_raw_action (e.g., '2', '15')")
    text: str = Field(description="Text/label of the element (from text or importantText)")
    confidence: float = Field(description="Confidence score (0-1) for the action relevance")


class BrowserScreenshot(BaseModel):
    """Base64-encoded screenshot data."""
    
    data: str = Field(description="Base64-encoded PNG image data")
    format: str = Field(default="png", description="Image format (always 'png')")
    encoding: str = Field(default="base64", description="Encoding type (always 'base64')")


class BrowserPageInfo(BaseModel):
    """Structured information about the current web page."""
    
    success: bool = Field(description="Whether the operation succeeded")
    url: str = Field(description="Current page URL")
    title: str = Field(description="Page title")
    actions: List[BrowserAction] = Field(description="List of interactive elements/actions available on the page")
    actions_count: int = Field(description="Number of actions found")
    screenshot: Optional[BrowserScreenshot] = Field(None, description="Screenshot if requested via include_screenshot=True")
    error: Optional[str] = Field(None, description="Error message if success=False")


class BrowserNavigateResult(BaseModel):
    """Result of a navigation operation."""
    
    success: bool = Field(description="Whether navigation succeeded")
    url: str = Field(description="URL after navigation")
    title: str = Field(description="Page title after navigation")
    error: Optional[str] = Field(None, description="Error message if success=False")


class BrowserActionResult(BaseModel):
    """Result of a browser action (click, type, scroll, etc.)."""
    
    success: bool = Field(description="Whether the action succeeded")
    error: Optional[str] = Field(None, description="Error message if success=False")


class BrowserScreenshotResult(BaseModel):
    """Result of a screenshot operation."""
    
    success: bool = Field(description="Whether screenshot succeeded")
    data: Optional[str] = Field(None, description="Base64-encoded PNG image data")
    format: str = Field(default="png", description="Image format")
    encoding: str = Field(default="base64", description="Data encoding")
    error: Optional[str] = Field(None, description="Error message if success=False")


# =============================================================================
# Helper Functions
# =============================================================================

def schema_to_description(model: type[BaseModel]) -> str:
    """
    Convert a Pydantic model to a human-readable description for tool documentation.
    
    Example:
        >>> print(schema_to_description(WeatherInfo))
        Current weather conditions for a city.
        
        Fields:
          - city (str): City name
          - temp (float): Temperature in requested units
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


# =============================================================================
# Tool-to-Schema Mapping
# =============================================================================

# Maps "server.tool_name" -> Pydantic model for doc generation
# This enables the doc generator to extract output schemas without
# requiring Returns: lines in tool descriptions.

TOOL_OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    # Weather tools
    "weather.get_weather": WeatherInfo,
    "weather.get_forecast": ForecastInfo,
    "weather.get_coordinates": CoordinatesInfo,
    
    # Sports tools (tool names as registered in MCP)
    "sports.scoreboard": GameInfo,  # Returns list of GameInfo
    "sports.standings": StandingEntry,  # Returns list of StandingEntry
    "sports.team_schedule": GameInfo,  # Returns list of GameInfo
    "sports.list_sports": SportInfo,  # Returns list of SportInfo
    "sports.news": NewsArticle,  # Returns list of NewsArticle
    "sports.rankings": RankingEntry,  # Returns list of RankingEntry per poll
    
    # Stocks tools (tool names as registered in MCP)
    "stocks.quote": StockQuote,
    "stocks.history": StockHistory,
    "stocks.search": StockSearchResult,  # Returns list
    "stocks.market_summary": MarketSummary,
    "stocks.crypto": StockQuote,
    
    # FX tools
    "fx.convert": ConversionResult,
    "fx.rates": ExchangeRates,
    "fx.history": RateHistory,
    
    # Wikipedia tools
    "wikipedia.summary": ArticleSummary,
    "wikipedia.search": SearchResults,
    "wikipedia.on_this_day": OnThisDayResponse,
    "wikipedia.random": ArticleSummary,
    "wikipedia.trending": TrendingResponse,
    "wikipedia.featured": ArticleSummary,
    
    # Microsoft Forms tools
    "msforms.get_form_data": FormDataResult,
    "msforms.get_form_summary": FormSummaryResult,
    
    # Countries tools
    "countries.get_country": Country,
    "countries.search_countries": Country,  # Returns list
    "countries.by_region": Country,  # Returns list
    "countries.by_currency": Country,  # Returns list
    "countries.by_language": Country,  # Returns list

    # Open Library tools
    "openlibrary.search_books": OLSearchResult,
    "openlibrary.get_book": OLBook,
    "openlibrary.get_author": OLAuthor,
    "openlibrary.search_authors": OLAuthor,  # Returns dict with list
    # openlibrary.get_cover returns simple {cover_url, size} - no schema needed

    # Hacker News tools
    "hackernews.top_stories": HNStory,  # Returns list
    "hackernews.new_stories": HNStory,  # Returns list
    "hackernews.best_stories": HNStory,  # Returns list
    "hackernews.story": HNStory,
    "hackernews.user": HNUser,
    "hackernews.search": HNSearchResult,

    # Browser tools
    "browser.navigate": BrowserNavigateResult,
    "browser.back": BrowserNavigateResult,
    "browser.forward": BrowserNavigateResult,
    "browser.get_page_info": BrowserPageInfo,
    "browser.click": BrowserActionResult,
    "browser.type_text": BrowserActionResult,
    "browser.hover": BrowserActionResult,
    "browser.select_option": BrowserActionResult,
    "browser.scroll": BrowserActionResult,
    "browser.screenshot": BrowserScreenshotResult,
    "browser.wait_for_selector": BrowserActionResult,
    "browser.wait": BrowserActionResult,
    "browser.execute_raw_action": BrowserActionResult,
    "browser.close_browser": BrowserActionResult,
}


def get_tool_output_schema(server_name: str, tool_name: str) -> Optional[type[BaseModel]]:
    """
    Get the output schema model for a tool.
    
    Args:
        server_name: Server name (e.g., 'weather', 'stocks')
        tool_name: Tool name (e.g., 'get_weather', 'get_quote')
    
    Returns:
        The Pydantic model class, or None if not found.
    """
    key = f"{server_name}.{tool_name}"
    return TOOL_OUTPUT_SCHEMAS.get(key)
