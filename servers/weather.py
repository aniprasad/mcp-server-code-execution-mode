#!/usr/bin/env python3
"""
Free Weather MCP Server (No API Key Required!)

Uses Open-Meteo API - completely free, no registration needed.
https://open-meteo.com/

Usage in sandbox:
    weather = await mcp_weather_free.get_weather(city="Seattle")
    forecast = await mcp_weather_free.get_forecast(city="London", days=3)
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
    from schemas import WeatherInfo, ForecastInfo, ForecastDay, schema_to_description
except ImportError:
    from .schemas import WeatherInfo, ForecastInfo, ForecastDay, schema_to_description

SERVER_NAME = "weather"

logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")
logger = logging.getLogger(SERVER_NAME)

app = Server(SERVER_NAME)

# Weather code descriptions from Open-Meteo
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="get_weather",
            description=f"""Get current weather for a city.

Output Schema:
{schema_to_description(WeatherInfo)}""",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name (e.g., 'Seattle', 'London', 'Tokyo')",
                    },
                },
                "required": ["city"],
            },
        ),
        Tool(
            name="get_forecast",
            description=f"""Get weather forecast for a city.

Output Schema:
{schema_to_description(ForecastInfo)}

Each day in the 'days' list:
{schema_to_description(ForecastDay)}""",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days (1-7)",
                        "default": 3,
                    },
                },
                "required": ["city"],
            },
        ),
        Tool(
            name="get_coordinates",
            description="Get latitude/longitude for a city. Useful for debugging.",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name to geocode",
                    },
                },
                "required": ["city"],
            },
        ),
    ]


def _make_request(url: str) -> Dict[str, Any]:
    """Make HTTP GET request and return JSON."""
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


def _geocode(city: str) -> Dict[str, Any]:
    """Convert city name to coordinates using Open-Meteo Geocoding API."""
    encoded_city = urllib.parse.quote(city)
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1&language=en&format=json"
    
    data = _make_request(url)
    results = data.get("results", [])
    
    if not results:
        raise RuntimeError(f"City not found: {city}")
    
    return results[0]


async def get_coordinates(city: str) -> Dict[str, Any]:
    """Get coordinates for a city."""
    location = _geocode(city)
    return {
        "city": location.get("name", city),
        "country": location.get("country", ""),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "timezone": location.get("timezone", ""),
        "population": location.get("population"),
    }


async def get_weather(city: str) -> Dict[str, Any]:
    """Get current weather for a city."""
    # First, geocode the city
    location = _geocode(city)
    lat = location["latitude"]
    lon = location["longitude"]
    
    # Get current weather from Open-Meteo
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        f"weather_code,wind_speed_10m"
        f"&timezone=auto"
    )
    
    data = _make_request(url)
    current = data.get("current", {})
    
    weather_code = current.get("weather_code", 0)
    conditions = WEATHER_CODES.get(weather_code, f"Unknown ({weather_code})")
    
    return WeatherInfo(
        city=location.get("name", city),
        country=location.get("country", ""),
        temp=current.get("temperature_2m", 0),
        feels_like=current.get("apparent_temperature", 0),
        conditions=conditions,
        humidity=current.get("relative_humidity_2m", 0),
        wind_speed=current.get("wind_speed_10m", 0),
        units="metric",
    ).model_dump()


async def get_forecast(city: str, days: int = 3) -> Dict[str, Any]:
    """Get weather forecast for a city."""
    # Clamp days to valid range
    days = max(1, min(7, days))
    
    # Geocode the city
    location = _geocode(city)
    lat = location["latitude"]
    lon = location["longitude"]
    
    # Get forecast from Open-Meteo
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,weather_code,"
        f"precipitation_probability_max"
        f"&timezone=auto"
        f"&forecast_days={days}"
    )
    
    data = _make_request(url)
    daily = data.get("daily", {})
    
    dates = daily.get("time", [])
    temp_maxes = daily.get("temperature_2m_max", [])
    temp_mins = daily.get("temperature_2m_min", [])
    weather_codes = daily.get("weather_code", [])
    precip_chances = daily.get("precipitation_probability_max", [])
    
    forecast_days = []
    for i in range(min(days, len(dates))):
        weather_code = weather_codes[i] if i < len(weather_codes) else 0
        forecast_days.append(ForecastDay(
            date=dates[i],
            temp_high=temp_maxes[i] if i < len(temp_maxes) else 0,
            temp_low=temp_mins[i] if i < len(temp_mins) else 0,
            conditions=WEATHER_CODES.get(weather_code, "Unknown"),
            humidity=0,  # Open-Meteo doesn't provide daily humidity in free tier
            precipitation_chance=precip_chances[i] if i < len(precip_chances) else None,
        ))
    
    return ForecastInfo(
        city=location.get("name", city),
        country=location.get("country", ""),
        units="metric",
        days=forecast_days,
    ).model_dump()


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    logger.info(f"Tool called: {name} with args: {arguments}")
    
    try:
        if name == "get_weather":
            result = await get_weather(city=arguments.get("city", ""))
        elif name == "get_forecast":
            result = await get_forecast(
                city=arguments.get("city", ""),
                days=arguments.get("days", 3),
            )
        elif name == "get_coordinates":
            result = await get_coordinates(city=arguments.get("city", ""))
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main() -> None:
    logger.info(f"Starting {SERVER_NAME} MCP server (Open-Meteo)...")
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
