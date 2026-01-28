# MCP Servers

This directory contains standalone MCP servers that can be used with mcp-server-code-execution-mode.

## Quick Start

1. Copy `_template.py` to create a new server
2. Define output schemas in `schemas.py` (recommended)
3. Implement your tools
4. Add a config file to `.mcp/` or register via environment

### Installation

Most servers work out of the box after `uv sync`. For browser automation:

```bash
# Install browser dependencies
uv pip install cesail playwright
uv run playwright install chromium
```

## Structure

```
servers/
├── _template.py      # Copy this to start a new server
├── schemas.py        # Shared Pydantic models for output types
├── weather.py        # Weather API (Open-Meteo, free)
├── sports.py         # Sports API (ESPN, free)
├── stocks.py         # Stock/crypto API (Yahoo Finance, free)
├── fx.py             # Currency exchange rates (frankfurter.dev, free)
├── wikipedia.py      # Wikipedia API (free)
├── msforms.py        # Microsoft Forms (requires auth)
├── browser.py        # Web automation (CeSail/Playwright)
├── requirements.txt  # Dependencies
└── README.md
```

## Usage in Sandbox

```python
# Pass servers=["weather", "sports", "stocks", "fx", "wikipedia", "msforms", "browser"] to load them
weather = await mcp_weather.get_weather(city="Seattle")
games = await mcp_sports.scoreboard(sport="nba")
quote = await mcp_stocks.quote(symbol="AAPL")
rates = await mcp_fx.rates(base="USD")
article = await mcp_wikipedia.random()

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

### msforms
- **API**: Microsoft Forms (private API, requires auth)
- **Auth**: Requires 3 env vars from browser DevTools (Network tab → any `formapi` request):
  - `MS_FORMS_TOKEN` - the `__requestverificationtoken` header value
  - `MS_FORMS_BEARER` - the `authorization` header value (without "Bearer " prefix)
  - `MS_FORMS_COOKIES` - the full `cookie` header value
- **Tools**:
  - `get_form_data(form_id, max_responses=100)` - Full form data: questions, aggregated stats, and individual responses
  - `get_form_summary(form_id)` - Aggregated stats only (faster)
  - `decode_form(form_id)` - Decode form ID to extract OrgId, OwnerId, TableId
- **Notes**: Owner ID auto-extracted from form_id. Auth tokens expire after ~1 hour.

### fx
- **API**: [Frankfurter](https://frankfurter.dev/) (free, no API key)
- **Currencies**: EUR, USD, GBP, JPY, and 30+ major currencies
- **Tools**:
  - `convert(amount, from_currency, to_currency)` - Convert between currencies
  - `rates(base)` - Get all exchange rates for a base currency
  - `history(from_currency, to_currency, days)` - Historical exchange rates

### wikipedia
- **API**: [Wikipedia REST API](https://en.wikipedia.org/api/rest_v1/) (free)
- **Tools**:
  - `summary(title)` - Get article summary by title
  - `search(query, limit)` - Search for articles
  - `on_this_day(month, day, type)` - Historical events on a date
  - `random()` - Get a random article
  - `trending(limit)` - Most viewed articles
  - `featured()` - Today's featured article

### browser
- **API**: [CeSail](https://github.com/anthropics/cesail) / [Playwright](https://playwright.dev/)
- **Requires**: `pip install cesail && playwright install chromium`
- **Tools**:
  - `navigate(url)` - Navigate to a URL
  - `back()` / `forward()` - Browser history navigation
  - `get_page_info(include_screenshot)` - Get current page URL, title, available actions
  - `click(selector)` - Click an element by CSS selector
  - `type_text(selector, text)` - Type text into an input field
  - `hover(selector)` - Hover over an element
  - `select_option(selector, value)` - Select dropdown option
  - `scroll(direction, amount)` - Scroll page ('down'/'up', 'viewport'/'half')
  - `screenshot(full_page)` - Capture screenshot as base64
  - `wait_for_selector(selector, timeout_ms, state)` - Wait for element
  - `wait(ms)` - Wait for milliseconds
  - `execute_raw_action(action_type, params)` - Execute raw CeSail action
  - `close_browser()` - Close the browser instance
- **Notes**: Runs in headless mode by default. Set `BROWSER_HEADLESS=false` for visible browser.

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
| `FxConversion` | fx.convert | Currency conversion result |
| `FxRates` | fx.rates | Exchange rates for a base currency |
| `WikipediaSummary` | wikipedia.summary, random | Article summary |
| `BrowserNavigateResult` | browser.navigate | Navigation result with URL/title |
| `BrowserScreenshotResult` | browser.screenshot | Screenshot with base64 data |
| `FormQuestion` | msforms.get_form_data | Question definition with choices/rating scale |
| `FormDataResult` | msforms.get_form_data | Complete form data with responses |
| `FormSummaryResult` | msforms.get_form_summary | Aggregated form statistics |

## Configuration

The `prepare.py` script auto-generates `.mcp/mcp-servers.json` from `servers/mcp-servers.json`.

To run the servers, they use the project's virtual environment:

```json
{
  "mcpServers": {
    "weather": {
      "command": ".venv/Scripts/python.exe",
      "args": ["servers/weather.py"],
      "description": "Get weather for cities"
    },
    "browser": {
      "command": ".venv/Scripts/python.exe",
      "args": ["servers/browser.py"],
      "description": "Web automation with CeSail/Playwright",
      "env": {
        "BROWSER_HEADLESS": "true"
      }
    }
  }
}
```

> **Note:** On macOS/Linux, change `.venv/Scripts/python.exe` to `.venv/bin/python`.

After adding/modifying servers, regenerate the API documentation:
```bash
uv run python prepare.py --force
```

## APIs Used

| Server | API | Notes |
|--------|-----|-------|
| weather | [Open-Meteo](https://open-meteo.com/) | Free weather data |
| sports | ESPN | Live scores, standings, schedules |
| stocks | [Yahoo Finance](https://finance.yahoo.com/) | Free stock/crypto data, no API key |
| fx | [Frankfurter](https://frankfurter.dev/) | Free currency exchange rates |
| wikipedia | [Wikipedia REST API](https://en.wikipedia.org/api/rest_v1/) | Free encyclopedia data |
| browser | [CeSail](https://github.com/anthropics/cesail) / Playwright | Web automation (requires install) |
| msforms | Microsoft Forms | Private API, requires auth tokens |
