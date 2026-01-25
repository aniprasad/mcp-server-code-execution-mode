# 8. Creating MCP Servers

This document guides you through building your own MCP servers that work with the bridge.

## 🎯 What You'll Build

An MCP server is a Python script that:
1. Exposes "tools" that the sandbox can call
2. Communicates over stdin/stdout using the MCP protocol
3. Runs on the **host** (has network access, file access, etc.)

---

## 🚀 Quick Start

### Step 1: Copy the Template

```bash
cp servers/_template.py servers/my_server.py
```

### Step 2: Customize

Edit `my_server.py`:

```python
#!/usr/bin/env python3
"""My Custom MCP Server"""

import asyncio
import json
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Change this to your server name
SERVER_NAME = "my-server"

app = Server(SERVER_NAME)


# Define your tools
@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="hello",
            description="Say hello to someone",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name to greet"
                    }
                },
                "required": ["name"]
            }
        )
    ]


# Implement your tools
async def hello(name: str) -> Dict[str, Any]:
    return {"message": f"Hello, {name}!"}


# Route tool calls to implementations
@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    if name == "hello":
        result = await hello(name=arguments.get("name", "World"))
        return [TextContent(type="text", text=json.dumps(result))]
    
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


# Entry point
async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
```

### Step 3: Register the Server

Create `~/MCPs/my-server.json`:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "python",
      "args": ["C:/path/to/my_server.py"],
      "description": "My custom MCP server"
    }
  }
}
```

### Step 4: Use It

```python
# In sandbox
greeting = await mcp_my_server.hello(name="Claude")
print(greeting)
# → {"message": "Hello, Claude!"}
```

---

## 📐 Server Structure

Every MCP server has these components:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          MCP SERVER STRUCTURE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  1. SERVER INITIALIZATION                                          │ │
│  │                                                                    │ │
│  │  from mcp.server import Server                                     │ │
│  │  app = Server("server-name")                                       │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  2. TOOL DEFINITIONS                                               │ │
│  │                                                                    │ │
│  │  @app.list_tools()                                                 │ │
│  │  async def list_tools() -> List[Tool]:                             │ │
│  │      return [Tool(name="...", description="...", inputSchema={})]  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  3. TOOL IMPLEMENTATIONS                                          │ │
│  │                                                                    │ │
│  │  async def my_tool(param1: str, param2: int) -> Dict:              │ │
│  │      # Your logic here                                             │ │
│  │      return {"result": "..."}                                      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  4. TOOL DISPATCHER                                                │ │
│  │                                                                    │ │
│  │  @app.call_tool()                                                  │ │
│  │  async def call_tool(name: str, arguments: Dict) -> List:          │ │
│  │      if name == "my_tool":                                         │ │
│  │          result = await my_tool(**arguments)                       │ │
│  │          return [TextContent(type="text", text=json.dumps(result))]│ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  5. ENTRY POINT                                                    │ │
│  │                                                                    │ │
│  │  async def main():                                                 │ │
│  │      async with stdio_server() as (read_stream, write_stream):     │ │
│  │          await app.run(read_stream, write_stream, ...)             │ │
│  │                                                                    │ │
│  │  if __name__ == "__main__":                                        │ │
│  │      asyncio.run(main())                                           │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tool Definitions

### Basic Tool

```python
Tool(
    name="get_data",
    description="Fetch data from the API",
    inputSchema={
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "The item ID"
            }
        },
        "required": ["id"]
    }
)
```

### Tool with Optional Parameters

```python
Tool(
    name="search",
    description="Search for items",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "limit": {
                "type": "integer",
                "description": "Max results",
                "default": 10
            },
            "sort": {
                "type": "string",
                "enum": ["relevance", "date", "popularity"],
                "default": "relevance"
            }
        },
        "required": ["query"]
    }
)
```

### Tool with Complex Input

```python
Tool(
    name="create_order",
    description="Create a new order",
    inputSchema={
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string"},
                        "quantity": {"type": "integer"}
                    },
                    "required": ["product_id", "quantity"]
                }
            }
        },
        "required": ["customer_id", "items"]
    }
)
```

---

## 📋 Using Pydantic Schemas

For better documentation and validation, use Pydantic:

### Define Schemas

```python
# schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List

class WeatherInfo(BaseModel):
    """Current weather conditions."""
    
    city: str = Field(description="City name")
    temp: float = Field(description="Temperature")
    conditions: str = Field(description="Weather conditions")
    humidity: int = Field(description="Humidity percentage")


def schema_to_description(model: type[BaseModel]) -> str:
    """Convert Pydantic model to human-readable description."""
    schema = model.model_json_schema()
    lines = [model.__doc__ or model.__name__, "", "Fields:"]
    
    for name, prop in schema.get("properties", {}).items():
        type_str = prop.get("type", "any")
        desc = prop.get("description", "")
        lines.append(f"  - {name} ({type_str}): {desc}")
    
    return "\n".join(lines)
```

### Use in Tool Definition

```python
from schemas import WeatherInfo, schema_to_description

@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="get_weather",
            # Auto-generate description from schema
            description=f"Get current weather.\n\n{schema_to_description(WeatherInfo)}",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            }
        )
    ]
```

### Validate Output

```python
async def get_weather(city: str) -> Dict[str, Any]:
    # Fetch from API...
    data = {"city": city, "temp": 72, "conditions": "sunny", "humidity": 45}
    
    # Validate with Pydantic
    validated = WeatherInfo(**data)
    return validated.model_dump()
```

---

## 🌐 Making API Calls

MCP servers run on the host and can access the network:

```python
import urllib.request
import urllib.error
import urllib.parse
import json

def _make_api_request(url: str, headers: dict = None) -> dict:
    """Make HTTP GET request."""
    req = urllib.request.Request(url, headers=headers or {})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


async def get_weather(city: str) -> Dict[str, Any]:
    """Get weather from Open-Meteo API (free, no API key needed!)."""
    # First, geocode the city name to coordinates
    encoded_city = urllib.parse.quote(city)
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1"
    geo_data = _make_api_request(geo_url)
    
    if not geo_data.get("results"):
        raise RuntimeError(f"City not found: {city}")
    
    location = geo_data["results"][0]
    lat, lon = location["latitude"], location["longitude"]
    
    # Get weather data
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code"
    )
    data = _make_api_request(weather_url)
    
    return {
        "city": location["name"],
        "country": location["country"],
        "temp": data["current"]["temperature_2m"],
        "humidity": data["current"]["relative_humidity_2m"]
    }
```

> 💡 **Tip:** The included `servers/weather.py` uses [Open-Meteo](https://open-meteo.com/) which is completely free with no API key required!

---

## 🔧 Environment Variables

Configure your server with environment variables:

### In Server Code

```python
import os

API_KEY = os.environ.get("MY_API_KEY", "")
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

if not API_KEY:
    logger.warning("MY_API_KEY not set, using mock data")
```

### In Configuration

```json
{
  "mcpServers": {
    "my-server": {
      "command": "python",
      "args": ["my_server.py"],
      "env": {
        "MY_API_KEY": "your-secret-key",
        "DEBUG": "true"
      }
    }
  }
}
```

---

## 🧪 Testing Your Server

### Manual Testing

Run the server directly:

```bash
python my_server.py
```

Then send MCP requests via stdin:

```json
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"capabilities": {}}}
{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "hello", "arguments": {"name": "Test"}}}
```

### Automated Testing

```python
# test_my_server.py
import pytest
import asyncio
from my_server import hello, get_weather

@pytest.mark.asyncio
async def test_hello():
    result = await hello(name="World")
    assert result["message"] == "Hello, World!"

@pytest.mark.asyncio
async def test_get_weather_mock():
    # Test with mock data (no API key)
    result = await get_weather(city="Seattle")
    assert "city" in result
    assert "temp" in result
```

---

## 📝 Complete Example: Calculator Server

```python
#!/usr/bin/env python3
"""
Calculator MCP Server

Provides basic mathematical operations.
"""

import asyncio
import json
import logging
import math
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

SERVER_NAME = "calculator"
logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")
logger = logging.getLogger(SERVER_NAME)

app = Server(SERVER_NAME)


@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="add",
            description="Add two numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        ),
        Tool(
            name="multiply",
            description="Multiply two numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        ),
        Tool(
            name="sqrt",
            description="Calculate square root",
            inputSchema={
                "type": "object",
                "properties": {
                    "n": {"type": "number", "description": "Number to find square root of"}
                },
                "required": ["n"]
            }
        ),
        Tool(
            name="power",
            description="Calculate power (a^b)",
            inputSchema={
                "type": "object",
                "properties": {
                    "base": {"type": "number", "description": "Base number"},
                    "exponent": {"type": "number", "description": "Exponent"}
                },
                "required": ["base", "exponent"]
            }
        )
    ]


async def add(a: float, b: float) -> Dict[str, Any]:
    return {"result": a + b, "operation": f"{a} + {b}"}


async def multiply(a: float, b: float) -> Dict[str, Any]:
    return {"result": a * b, "operation": f"{a} × {b}"}


async def sqrt(n: float) -> Dict[str, Any]:
    if n < 0:
        raise ValueError("Cannot calculate square root of negative number")
    return {"result": math.sqrt(n), "operation": f"√{n}"}


async def power(base: float, exponent: float) -> Dict[str, Any]:
    return {"result": math.pow(base, exponent), "operation": f"{base}^{exponent}"}


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    logger.info(f"Tool called: {name} with {arguments}")
    
    try:
        if name == "add":
            result = await add(a=arguments["a"], b=arguments["b"])
        elif name == "multiply":
            result = await multiply(a=arguments["a"], b=arguments["b"])
        elif name == "sqrt":
            result = await sqrt(n=arguments["n"])
        elif name == "power":
            result = await power(base=arguments["base"], exponent=arguments["exponent"])
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        return [TextContent(type="text", text=json.dumps(result))]
    
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


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
```

**Usage in sandbox:**

```python
# In sandbox with servers=["calculator"]

result = await mcp_calculator.add(a=5, b=3)
print(result)
# → {"result": 8, "operation": "5 + 3"}

result = await mcp_calculator.sqrt(n=16)
print(result)
# → {"result": 4.0, "operation": "√16"}

result = await mcp_calculator.power(base=2, exponent=10)
print(result)
# → {"result": 1024.0, "operation": "2^10"}
```

---

## 📋 Checklist

Before deploying your server:

- [ ] Server name is unique and descriptive
- [ ] All tools have clear descriptions
- [ ] Input schemas define all required parameters
- [ ] Error handling is in place
- [ ] Logging helps with debugging
- [ ] Environment variables are documented
- [ ] Configuration file is created in `~/MCPs/`

---

## Next Steps

→ [Security Model](09-security-model.md) - Understand the security features
