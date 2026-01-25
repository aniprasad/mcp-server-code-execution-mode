# MCP Servers

This directory contains standalone MCP servers that can be used with mcp-server-code-execution-mode.

## Quick Start

1. Copy `_template.py` to create a new server
2. Define output schemas in `schemas.py` (recommended)
3. Implement your tools
4. Add a config file to `~/MCPs/` or register via environment

## Structure

```
servers/
├── _template.py      # Copy this to start a new server
├── schemas.py        # Shared Pydantic models for output types
├── weather.py        # Example: weather API
├── soccer.py         # Example: live soccer matches
├── requirements.txt  # Dependencies
└── README.md
```

## Usage in Sandbox

```python
# Pass servers=["weather", "soccer"] to load them
weather = await mcp_weather.get_weather(city="Seattle")
matches = await mcp_soccer.get_live_matches()

# Match data has consistent structure:
for match in matches:
    # Get weather for each venue
    venue_weather = await mcp_weather.get_weather(city=match['venue'])
    print(f"{match['home']} vs {match['away']} - {venue_weather['conditions']}")
```

## Output Schemas

We use Pydantic models in `schemas.py` for:
- **Validation**: Ensure outputs match expected structure
- **Documentation**: LLMs can understand output fields from descriptions
- **Consistency**: Same field names across related tools

### Example Schema

```python
from pydantic import BaseModel, Field

class MatchInfo(BaseModel):
    """Information about a soccer match."""
    home: str = Field(description="Home team name")
    away: str = Field(description="Away team name")
    venue: str = Field(description="City where match is played")
    score: str | None = Field(description="Current score like '2-1'")
    status: str = Field(description="SCHEDULED, LIVE, HALFTIME, FINISHED")
```

### Using Schemas in Tools

```python
from schemas import MatchInfo

async def get_live_matches():
    # ... fetch data ...
    return [MatchInfo(**match).model_dump() for match in matches]
```

### Available Schemas

| Schema | Used By | Description |
|--------|---------|-------------|
| `WeatherInfo` | weather.get_weather | Current weather conditions |
| `ForecastInfo` | weather.get_forecast | Multi-day forecast |
| `MatchInfo` | soccer.get_live_matches, get_upcoming | Match information |
| `StandingsInfo` | soccer.get_standings | League table |
| `TeamStanding` | (part of StandingsInfo) | Team position in league |

## Configuration

Create `~/MCPs/my-servers.json`:

```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["C:/path/to/servers/weather.py"],
      "description": "Get weather for cities"
    }
  }
}
```

Or set environment variable:
```
MCP_SERVERS_CONFIG=C:/path/to/my-servers.json
```

After adding servers, regenerate the API documentation:
```bash
uv run python generate_api_docs.py
```
This updates `~/MCPs/mcp-tools.md` which the VS Code Copilot Agent uses.

## API Keys

| Server | API Key Required? | Notes |
|--------|-------------------|-------|
| weather | ❌ No | Uses [Open-Meteo](https://open-meteo.com/) - completely free, no registration |
| soccer | ❌ No (mock) | Returns mock data; set `FOOTBALL_API_KEY` for real data from [football-data.org](https://www.football-data.org/) |
