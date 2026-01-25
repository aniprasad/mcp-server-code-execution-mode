# MCP Servers API Reference

Load servers with `servers=['name']`, call via `await mcp_<server>.<tool>(...)`

## Sandbox Helpers

These functions are always available in the sandbox (no import needed).

### Charts

**render_chart(data, chart_type, x, y, *, title=None, series=None, hue=None, filename='chart.png', width=10, height=6)**
Render a chart from data using seaborn. Simple, declarative interface.
- **data**: List of dicts or pandas DataFrame
- **chart_type** (str): One of `'bar'`, `'line'`, or `'scatter'`
- **x** (str): Field name for X axis
- **y** (str): Field name for Y axis
- **title** (str, optional): Chart title
- **series** (str, optional): Field for grouping (creates colored bars/lines). Alias: `hue`
- **filename** (str): Output filename (default: 'chart.png')
- **width** (int): Chart width in inches (default: 10)
- **height** (int): Chart height in inches (default: 6)
- **Returns**: `file://` URL to the saved chart (auto-printed)

```python
# Example: Simple bar chart
data = [{'day': 'Mon', 'temp': 25}, {'day': 'Tue', 'temp': 28}]
url = render_chart(data, 'bar', x='day', y='temp', title='Daily Temps')

# Example: Multi-series line chart
data = [
    {'month': 'Jan', 'city': 'Seattle', 'temp': 8},
    {'month': 'Jan', 'city': 'Miami', 'temp': 24},
    {'month': 'Feb', 'city': 'Seattle', 'temp': 10},
    {'month': 'Feb', 'city': 'Miami', 'temp': 25},
]
render_chart(data, 'line', x='month', y='temp', series='city', title='Temps by City')
```

### Files

**save_image(filename, figure_or_bytes, *, format=None)**
Save an image to the execution folder. For charts, use `render_chart()` instead.
- **filename** (str): Output filename (e.g., 'output.png')
- **figure_or_bytes**: Figure, PIL Image, or bytes
- **Returns**: `file://` URL that opens in browser

**save_file(filename, content, *, subdir='data')**
Save text or bytes to the execution folder.
- **filename** (str): Output filename (e.g., 'results.csv')
- **content** (str|bytes): Content to save
- **subdir** (str): Subdirectory ('data', 'images', or '')
- **Returns**: `file://` URL that opens in browser

**list_execution_files()**
List all files saved in current execution folder.
- **Returns**: `{images: [...], data: [...], other: [...]}`

**execution_folder()**
Get Path to current execution folder.
- **Returns**: `Path('/projects/executions/<id>')`

### Memory (Persistent Data)

**save_memory(key, value, *, metadata=None)**
Save JSON-serializable data that persists across sessions.
- **key** (str): Identifier (e.g., 'project_context')
- **value**: Any JSON-serializable data
- **metadata** (dict, optional): Extra info like `{'tags': ['important']}`

**load_memory(key, *, default=None)**
Load previously saved data.
- **key** (str): The memory identifier
- **default**: Value if not found
- **Returns**: The stored value

**list_memories()**
List all saved memory keys with metadata.
- **Returns**: `[{key, metadata, created_at, updated_at}, ...]`

**update_memory(key, updater)**
Update memory using a function: `update_memory('tasks', lambda t: t + ['new'])`

**delete_memory(key)** / **memory_exists(key)** / **get_memory_info(key)**
Delete, check existence, or get full info for a memory entry.

### Tools (Persistent Code)

**save_tool(func)**
Save a function to `user_tools.py` for future sessions.
```python
def my_helper(x): return x * 2
save_tool(my_helper)  # Available in all future sessions
```

## weather
Get weather information for cities (current conditions and forecasts) Load: `servers=['weather']`

### get_weather(city)
Get current weather for a city.
- **city** (string, required): City name (e.g., 'Seattle', 'London', 'Tokyo')
- **Returns**: `{city, country, temp, feels_like, conditions, humidity, wind_speed, units}`

### get_forecast(city, days=3)
Get weather forecast for a city.
- **city** (string, required): City name
- **days** (integer, optional): Number of days (1-7)
- **Returns**: `{city, country, units, days}`

### get_coordinates(city)
Get latitude/longitude for a city. Useful for debugging.
- **city** (string, required): City name to geocode

## soccer
Get live soccer matches, upcoming games, and league standings Load: `servers=['soccer']`

### get_live_matches(competition=)
Get currently live soccer/football matches worldwide.
- **competition** (string, optional): Filter by competition code: PL, PD, BL1, SA, FL1, CL, EC, WC. Leave empty for all.
- **Returns**: `{home, away, score, status, minute, competition, venue, datetime}`

### get_upcoming_matches(competition=, days=3)
Get upcoming soccer matches in the next few days.
- **competition** (string, optional): Competition code: PL, PD, BL1, SA, FL1, CL, EC, WC. Leave empty for all.
- **days** (integer, optional): Number of days ahead to check (1-14)
- **Returns**: `{home, away, score, status, minute, competition, venue, datetime}`

### get_standings(competition)
Get current league standings/table for a competition.
- **competition** (string, required): Competition code. Options: PL (Premier League), PD (La Liga), BL1 (Bundesliga), SA (Serie A), FL1 (Ligue 1), CL (Champions League), EC (European Championship), WC (World Cup)
- **Returns**: `{competition, competition_code, season, standings}`

### list_competitions()
List available competition codes and their names.
