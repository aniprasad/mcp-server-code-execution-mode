# 1. Overview

## What Is This Project?

**MCP Server Code Execution Mode** is a bridge that lets AI models (like Claude) execute Python code safely in an isolated container while having access to external tools and services.

Think of it as a "sandboxed Python notebook" for AI agents.

## The Problem It Solves

### Traditional MCP: Token Explosion 💥

When you connect an AI to many MCP servers (tools), each tool's schema gets loaded into the AI's context:

```
Connect 10 MCP servers with 100 total tools
                    ↓
       30,000+ tokens of tool schemas
                    ↓
         Every single prompt includes all of them
                    ↓
              💰 Expensive! 🐌 Slow!
```

### This Solution: Discovery-First 🔍

Instead of loading all tool schemas upfront, we give the AI **one tool** (`run_python`) and let it discover tools on-demand:

```
AI gets 1 tool: run_python (~200 tokens)
                    ↓
    AI writes Python: "What servers exist?"
                    ↓
    AI writes Python: "What tools does 'weather' have?"
                    ↓
    AI calls only what it needs
                    ↓
         ✅ Cheap! ✅ Fast! ✅ Scalable!
```

## How It Works (Simple Version)

```
┌──────────────────────────────────────────────────────────────┐
│                         YOUR COMPUTER                         │
│                                                               │
│  ┌─────────────┐     JSON-RPC      ┌────────────────────┐    │
│  │   Claude    │◄─────────────────►│  This Bridge       │    │
│  │   (or any   │   "run_python"    │  (host process)    │    │
│  │   MCP       │                   │                    │    │
│  │   client)   │                   │  - Manages         │    │
│  └─────────────┘                   │    containers      │    │
│                                    │  - Connects to     │    │
│                                    │    MCP servers     │    │
│                                    │  - Routes RPC      │    │
│                                    └─────────┬──────────┘    │
│                                              │               │
│                                     stdin/stdout             │
│                                              │               │
│                                    ┌─────────▼──────────┐    │
│                                    │  Docker/Podman     │    │
│                                    │  Container         │    │
│                                    │                    │    │
│                                    │  🔒 No network     │    │
│                                    │  🔒 Read-only FS   │    │
│                                    │  🔒 No privileges  │    │
│                                    │                    │    │
│                                    │  Python runs here  │    │
│                                    │  safely isolated   │    │
│                                    └────────────────────┘    │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │ MCP Server  │  │ MCP Server  │  │ MCP Server  │           │
│  │  weather    │  │   sports    │  │   stocks    │           │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
│                (These have network access)                    │
└──────────────────────────────────────────────────────────────┘
```

## Key Benefits

| Feature | Benefit |
|---------|---------|
| **Token Efficient** | ~200 tokens vs 30,000+ for traditional MCP |
| **Secure** | Code runs in isolated container with no network/privileges |
| **Flexible** | AI writes Python code - can do loops, conditions, data processing |
| **Persistent** | Variables and functions persist across calls (like a notebook) |
| **Extensible** | Add new MCP servers without changing the bridge |

## What Can the AI Do?

Inside the sandbox, the AI can:

```python
# Discover what's available
servers = runtime.discovered_servers()
# → ['weather', 'sports', 'stocks']

# Search for tools
matches = await runtime.search_tool_docs("current temperature")
# → [{'server': 'weather', 'tool': 'get_weather', ...}]

# Call MCP tools
weather = await mcp_weather.get_weather(city="Seattle")
# → {'temp': 72, 'conditions': 'sunny', ...}

# Save data for later
save_memory("last_city", "Seattle")

# Load saved data
city = load_memory("last_city")
```

## Example Conversation

**User:** "What's the weather like at today's Premier League matches?"

**AI's thought process:**
1. I need weather data and sports data
2. Let me write Python to combine them

**AI writes:**
```python
# Get today's matches
matches = await mcp_sports.scoreboard(sport='epl')

# Get weather for each venue
for match in matches:
    weather = await mcp_weather.get_weather(city=match['venue'])
    print(f"{match['home']} vs {match['away']}")
    print(f"  Weather: {weather['temp']}°, {weather['conditions']}")
```

**Result:** The AI gets comprehensive data in a single execution, something that would require many individual tool calls with traditional MCP.

## Next Steps

→ [Core Concepts](02-core-concepts.md) - Learn the terminology
