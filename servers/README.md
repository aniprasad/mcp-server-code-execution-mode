# MCP Servers

This directory contains standalone MCP servers that can be used with mcp-server-code-execution-mode.

## Quick Start

1. Copy `_template.py` to create a new server
2. Define output schemas in `schemas.py` (recommended)
3. Implement your tools
4. Add a config file to `.mcp/` or register via environment

## Structure

```
servers/
├── _template.py      # Copy this to start a new server
├── schemas.py        # Shared Pydantic models for output types
├── weather.py        # Weather API (Open-Meteo, free)
├── sports.py         # Sports API (ESPN, free)
├── stocks.py         # Stock/crypto API (Yahoo Finance, free)
├── requirements.txt  # Dependencies
└── README.md
```

## Usage in Sandbox

```python
# Pass servers=["weather", "sports", "stocks"] to load them
weather = await mcp_weather.get_weather(city="Seattle")
games = await mcp_sports.scoreboard(sport="nba")
quote = await mcp_stocks.quote(symbol="AAPL")

# Combine data across servers:
for game in games["games"]:
    if game["status"] == "SCHEDULED":
        # Get weather for the venue city
        city = game["venue"].split(",")[0]  # Extract city from venue
        forecast = await mcp_weather.get_weather(city=city)
        print(f"{game['away_team']} @ {game['home_team']} - {forecast['conditions']}")
```

## Available Servers

### weather
- **API**: [Open-Meteo](https://open-meteo.com/)
- **Tools**: `get_weather(city)`, `get_forecast(city, days)`, `get_coordinates(city)`

### sports
- **API**: ESPN
- **Sports**: NFL, NBA, WNBA, MLB, NHL, College Football, College Basketball, MLS, Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Champions League, F1
- **Tools**: 
  - `scoreboard(sport, date)` - Today's games with live scores
  - `standings(sport, group)` - Current standings
  - `team_schedule(sport, team)` - Team's schedule
  - `news(sport, limit)` - Latest headlines
  - `list_sports()` - All available sport codes

### stocks
- **API**: [Yahoo Finance](https://finance.yahoo.com/) (free, no API key)
- **Markets**: US stocks, ETFs, indices, cryptocurrencies
- **Tools**:
  - `quote(symbol)` - Real-time stock price with change, volume, market cap
  - `history(symbol, period)` - Historical OHLCV data (1d, 5d, 1mo, 3mo, 6mo, 1y, etc.)
  - `search(query)` - Search for ticker symbols by company name
  - `market_summary()` - Major indices (S&P 500, Dow, NASDAQ, etc.)
  - `crypto(symbol)` - Cryptocurrency prices (bitcoin, ethereum, etc.)

## Output Schemas

We use Pydantic models in `schemas.py` for:
- **Validation**: Ensure outputs match expected structure
- **Documentation**: LLMs can understand output fields from descriptions
- **Consistency**: Same field names across related tools

### Example Schema

```python
from pydantic import BaseModel, Field

class GameInfo(BaseModel):
    """Information about a sports game."""
    home_team: str = Field(description="Home team name")
    away_team: str = Field(description="Away team name")
    score: str | None = Field(description="Score like '24-17'")
    status: str = Field(description="SCHEDULED, LIVE, FINAL")
    sport: str = Field(description="Sport name")
```

### Available Schemas

| Schema | Used By | Description |
|--------|---------|-------------|
| `WeatherInfo` | weather.get_weather | Current weather conditions |
| `ForecastInfo` | weather.get_forecast | Multi-day forecast |
| `GameInfo` | sports.scoreboard, team_schedule | Game/match information |
| `StandingEntry` | sports.standings | Team position in standings |
| `NewsArticle` | sports.news | News headline |
| `StockQuote` | stocks.quote, stocks.crypto | Real-time stock/crypto quote |
| `HistoricalPrice` | stocks.history | OHLCV price data point |

## Configuration

Create `.mcp/mcp-servers.json`:

```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["${workspaceFolder}/servers/weather.py"],
      "description": "Get weather for cities"
    },
    "sports": {
      "command": "python",
      "args": ["${workspaceFolder}/servers/sports.py"],
      "description": "Get live scores, standings, schedules for NFL, NBA, MLB, NHL, Soccer, F1"
    },
    "stocks": {
      "command": "python",
      "args": ["${workspaceFolder}/servers/stocks.py"],
      "description": "Get real-time stock quotes, historical prices, and crypto data"
    }
  }
}
```

After adding/modifying servers, regenerate the API documentation:
```bash
uv run python generate_api_docs.py
```

## APIs Used

| Server | API | Notes |
|--------|-----|-------|
| weather | [Open-Meteo](https://open-meteo.com/) | Free weather data |
| sports | ESPN | Live scores, standings, schedules |
| stocks | [Yahoo Finance](https://finance.yahoo.com/) | Free stock/crypto data, no API key required |
