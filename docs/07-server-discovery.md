# 7. Server Discovery

This document explains how the bridge finds and loads MCP servers from various configuration sources.

## 🎯 The Goal

When you call `run_python(code="...", servers=["weather", "soccer"])`, the bridge needs to:

1. Find the configuration for "weather" and "soccer"
2. Know how to start those servers
3. Connect to them

But where does it find this information?

---

## 📍 Configuration Sources

The bridge searches multiple locations for MCP server configurations. It checks these in order:

```python
CONFIG_SOURCES = [
    # User MCPs directory (recommended)
    ConfigSource(Path.home() / "MCPs", "directory"),
    # → ~/MCPs/*.json
    
    # Standard MCP config
    ConfigSource(Path.home() / ".config" / "mcp" / "servers", "directory"),
    # → ~/.config/mcp/servers/*.json
    
    # Local project
    ConfigSource(Path.cwd() / "mcp-servers", "directory"),
    # → ./mcp-servers/*.json
    
    # VS Code workspace
    ConfigSource(Path.cwd() / ".vscode" / "mcp.json", "file"),
    # → ./.vscode/mcp.json
    
    # Claude CLI config
    ConfigSource(Path.home() / ".claude.json", "file"),
    # → ~/.claude.json
    
    # Cursor config
    ConfigSource(Path.home() / ".cursor" / "mcp.json", "file"),
    # → ~/.cursor/mcp.json
    
    # OpenCode config
    ConfigSource(Path.home() / ".opencode.json", "file"),
    # → ~/.opencode.json
    
    # Windsurf config
    ConfigSource(Path.home() / ".codeium" / "windsurf" / "mcp_config.json", "file"),
    # → ~/.codeium/windsurf/mcp_config.json
]

# Platform-specific paths are also added:
# macOS: ~/Library/Application Support/...
# Linux: ~/.config/...
```

---

## 📄 Configuration Format

### Single File Format

Config files use this JSON structure:

```json
{
  "mcpServers": {
    "server-name": {
      "command": "python",
      "args": ["path/to/server.py"],
      "env": {
        "API_KEY": "xxx"
      },
      "cwd": "/path/to/working/directory",
      "description": "What this server does"
    }
  }
}
```

### Directory Format

For directories like `~/MCPs/`, the bridge reads all `.json` files:

```
~/MCPs/
├── weather.json       # Contains weather server config
├── soccer.json        # Contains soccer server config
└── mcp-servers.json   # Can contain multiple servers
```

---

## 🔍 Discovery Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        DISCOVERY FLOW                                     │
└──────────────────────────────────────────────────────────────────────────┘

   discover_servers()
          │
          ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │  For each CONFIG_SOURCE:                                         │
   │                                                                   │
   │  ┌─────────────────────────────────────────────────────────────┐ │
   │  │  If source is a DIRECTORY:                                  │ │
   │  │    - List all *.json files                                  │ │
   │  │    - Read each file                                         │ │
   │  │    - Extract mcpServers entries                             │ │
   │  │                                                             │ │
   │  │  If source is a FILE:                                       │ │
   │  │    - Read the file                                          │ │
   │  │    - Extract mcpServers entries                             │ │
   │  └─────────────────────────────────────────────────────────────┘ │
   │                                                                   │
   │  For each server found:                                          │
   │    - Create MCPServerInfo object                                 │
   │    - Store in self.servers[name]                                 │
   │    - Skip if already found (first wins)                          │
   └──────────────────────────────────────────────────────────────────┘
          │
          ▼
   Result: self.servers = {
       "weather": MCPServerInfo(
           name="weather",
           command="python",
           args=["C:/path/to/weather.py"],
           description="Get weather information"
       ),
       "soccer": MCPServerInfo(...),
       ...
   }
```

---

## 📦 MCPServerInfo

When a server is discovered, it's stored as an `MCPServerInfo`:

```python
@dataclass
class MCPServerInfo:
    """Configuration for a single MCP server binary."""
    
    name: str               # "weather"
    command: str            # "python"
    args: List[str]         # ["C:/path/to/weather.py"]
    env: Dict[str, str]     # {"API_KEY": "xxx"}
    cwd: Optional[str]      # Working directory
    description: str        # "Get weather information"
```

---

## 🚀 Server Loading

Discovery just finds configurations. Loading actually starts the server:

```python
async def load_server(self, server_name: str) -> None:
    """Start an MCP server and connect to it."""
    
    # Skip if already loaded
    if server_name in self.loaded_servers:
        return
    
    # Find the config
    info = self.servers.get(server_name)
    if not info:
        raise SandboxError(f"Unknown MCP server: {server_name}")
    
    # Create client and start the server process
    client = PersistentMCPClient(info)
    await client.start()
    
    # Store the client
    self.clients[server_name] = client
    self.loaded_servers.add(server_name)
```

### What `client.start()` Does

```python
async def start(self) -> None:
    """Start the MCP server and establish connection."""
    
    # Create stdio parameters
    params = StdioServerParameters(
        command=self.server_info.command,   # "python"
        args=self.server_info.args,         # ["weather.py"]
        env=self.server_info.env,           # {"API_KEY": "..."}
        cwd=self.server_info.cwd,           # Working directory
    )
    
    # Start the server process with stdio communication
    self._stdio_cm = stdio_client(params)
    read_stream, write_stream = await self._stdio_cm.__aenter__()
    
    # Create MCP session
    session = ClientSession(read_stream, write_stream)
    await session.__aenter__()
    
    # Initialize MCP protocol
    await session.initialize()
    
    self._session = session
```

After this, the server is running and ready to receive tool calls.

---

## 🔄 Lazy Loading

Servers are loaded **on demand**, not at startup:

```python
# First run_python call requesting weather
await bridge.execute_code("...", servers=["weather"], timeout=30)
# → weather server is loaded

# Second call also requesting weather
await bridge.execute_code("...", servers=["weather"], timeout=30)
# → weather is already loaded, skipped

# Third call requesting both
await bridge.execute_code("...", servers=["weather", "soccer"], timeout=30)
# → weather already loaded, soccer is loaded now
```

This improves startup time and resource usage.

---

## 📋 Metadata Caching

Once a server is loaded, we cache its tool metadata:

```python
async def _ensure_server_metadata(self, server_name: str) -> None:
    """Fetch and cache tool metadata for a server."""
    
    if server_name in self._server_metadata_cache:
        return  # Already cached
    
    client = self.clients.get(server_name)
    
    # Get all tools from the server
    tool_specs = await client.list_tools()
    
    # Create alias for use in sandbox
    alias = self._alias_for(server_name)  # "weather"
    
    # Process each tool
    tools = []
    for spec in tool_specs:
        tool = {
            "name": spec["name"],          # "get_weather"
            "alias": tool_alias,            # "get_weather"
            "description": spec["description"],
            "input_schema": spec["inputSchema"],
        }
        tools.append(tool)
    
    # Cache the metadata
    self._server_metadata_cache[server_name] = {
        "name": server_name,
        "alias": alias,
        "tools": tools,
    }
```

This metadata is what gets passed to the container as `AVAILABLE_SERVERS`.

---

## 🏷️ Aliasing

Server names might not be valid Python identifiers. The bridge creates aliases:

```python
def _alias_for(self, name: str) -> str:
    """Convert server name to valid Python identifier."""
    
    # Clean: remove non-alphanumeric characters
    base = re.sub(r"[^a-z0-9_]+", "_", name.lower())
    
    # Handle leading digits
    if base[0].isdigit():
        base = f"_{base}"
    
    # Handle duplicates
    alias = base
    suffix = 1
    used = set(self._aliases.values())
    while alias in used:
        suffix += 1
        alias = f"{base}_{suffix}"
    
    self._aliases[name] = alias
    return alias
```

**Examples:**

| Server Name | Alias |
|-------------|-------|
| `weather` | `weather` |
| `my-cool-server` | `my_cool_server` |
| `123service` | `_123service` |
| `weather` (duplicate) | `weather_2` |

The alias is used for proxy names: `mcp_weather`, `mcp_my_cool_server`, etc.

---

## 📍 Example: Setting Up Your Own Servers

### Step 1: Create Server Directory

```bash
mkdir ~/MCPs
```

### Step 2: Add Configuration

Create `~/MCPs/mcp-servers.json`:

```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["C:/Users/you/servers/weather.py"],
      "description": "Get weather information for cities (uses Open-Meteo, no API key needed!)"
    },
    "soccer": {
      "command": "python",
      "args": ["C:/Users/you/servers/soccer.py"],
      "env": {
        "FOOTBALL_API_KEY": "your-key-here"
      },
      "description": "Get live soccer matches and standings"
    }
  }
}
```

> 💡 **Note:** The weather server uses [Open-Meteo](https://open-meteo.com/) which is free and requires no API key. The soccer server returns mock data without an API key.

### Step 3: Verify Discovery

```python
# In sandbox
import mcp.runtime as runtime
servers = runtime.discovered_servers(detailed=True)
print(servers)
# → (
#     {'name': 'weather', 'description': 'Get weather...'},
#     {'name': 'soccer', 'description': 'Get live soccer...'}
# )
```

---

## 🔒 Self-Server Protection

The bridge prevents loading itself, avoiding infinite recursion:

```python
def _looks_like_self_server(info, name=None) -> bool:
    """Return True if config appears to launch this bridge."""
    
    server_name = (name or "").lower()
    
    # Check name
    if server_name in {"mcp-server-code-execution-mode", ...}:
        return True
    
    # Check command
    command_name = Path(command).name.lower()
    if command_name.endswith("mcp_server_code_execution_mode.py"):
        return True
    
    # Check args
    for arg in args:
        if "mcp_server_code_execution_mode" in arg.lower():
            return True
    
    return False
```

If detected, the server is skipped with a warning.

---

## 🌍 Environment Variables

### MCP_SERVERS_CONFIG

Override the discovery path:

```bash
export MCP_SERVERS_CONFIG=/path/to/my-config.json
```

### Per-Server Environment

Each server can have its own environment variables (useful for API keys):

```json
{
  "mcpServers": {
    "soccer": {
      "command": "python",
      "args": ["soccer.py"],
      "env": {
        "FOOTBALL_API_KEY": "your-key-here",
        "LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

These variables are passed to the server process, not to the sandbox.

> 💡 **Note:** The included `weather.py` uses Open-Meteo (no API key needed). The `soccer.py` server works without an API key (mock data).

---

## 🔄 Discovery vs Runtime

| Phase | What Happens | Data Structure |
|-------|--------------|----------------|
| **Discovery** | Find configs | `self.servers: Dict[str, MCPServerInfo]` |
| **Loading** | Start server process | `self.clients: Dict[str, PersistentMCPClient]` |
| **Metadata** | Fetch tools | `self._server_metadata_cache: Dict[str, Dict]` |

**Timeline:**

```
Bridge starts
      │
      ▼
 discover_servers()  ─── Scans all CONFIG_SOURCES
      │                   Populates self.servers
      │                   (No processes started yet)
      ▼
 run_python(servers=["weather"])
      │
      ▼
 load_server("weather")  ─── Starts weather.py process
      │                       Creates PersistentMCPClient
      │                       Establishes MCP session
      ▼
 _ensure_server_metadata("weather")  ─── Calls list_tools
      │                                   Caches tool info
      ▼
 Create SandboxInvocation with metadata
      │
      ▼
 Execute code in container
```

---

## 📊 Discovery Summary

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        DISCOVERY LOCATIONS                                │
├────────────────────────────────────┬─────────────────────────────────────┤
│           Location                 │        Type                          │
├────────────────────────────────────┼─────────────────────────────────────┤
│  ~/MCPs/                           │  Directory (recommended)             │
│  ~/.config/mcp/servers/            │  Directory                           │
│  ./mcp-servers/                    │  Directory                           │
│  ./.vscode/mcp.json                │  File                                │
│  ~/.claude.json                    │  File                                │
│  ~/.cursor/mcp.json                │  File                                │
│  ~/.opencode.json                  │  File                                │
│  ~/.codeium/windsurf/mcp_config.json │  File                             │
│  (Platform-specific paths...)      │  Various                             │
└────────────────────────────────────┴─────────────────────────────────────┘
```

---

## Next Steps

→ [Creating MCP Servers](08-creating-mcp-servers.md) - Build your own servers
