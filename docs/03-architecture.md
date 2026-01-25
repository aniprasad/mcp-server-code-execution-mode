# 3. Architecture

This document describes the system architecture—the major components and how they interact.

## 🏗️ System Layers

The system has three main layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 1: MCP INTERFACE                       │
│                                                                 │
│  What the AI sees:                                              │
│  • One tool: run_python                                         │
│  • One resource: code-execution-capabilities                    │
│                                                                 │
│  The AI sends Python code, gets back output.                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 2: BRIDGE ORCHESTRATION                │
│                                                                 │
│  What happens behind the scenes:                                │
│  • MCPBridge: Main coordinator                                  │
│  • SandboxInvocation: Per-execution context                     │
│  • PersistentMCPClient: Connection to each MCP server           │
│  • RootlessContainerSandbox: Container management               │
│                                                                 │
│  Manages the whole execution lifecycle.                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 3: ISOLATED EXECUTION                  │
│                                                                 │
│  Where code actually runs:                                      │
│  • Docker/Podman container                                      │
│  • Generated entrypoint.py                                      │
│  • MCP proxies and runtime helpers                              │
│                                                                 │
│  Complete isolation from the host.                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 Component Breakdown

### 1. MCP Server Interface

The bridge is itself an MCP server. When Claude connects to it, it sees:

**Tools:**
```python
{
    "name": "run_python",
    "description": "Execute Python code in a sandboxed environment...",
    "inputSchema": {
        "properties": {
            "code": {"type": "string"},
            "servers": {"type": "array", "items": {"type": "string"}},
            "timeout": {"type": "integer", "default": 30}
        },
        "required": ["code"]
    }
}
```

**Resources:**
```python
{
    "uri": "resource://mcp-server-code-execution-mode/capabilities",
    "name": "code-execution-capabilities",
    "description": "Capability overview and helper reference"
}
```

### 2. MCPBridge Class

The central coordinator. Key responsibilities:

| Responsibility | What It Does |
|----------------|--------------|
| **Server Discovery** | Scans config files to find MCP servers |
| **Server Loading** | Starts `PersistentMCPClient` for each server |
| **Metadata Caching** | Caches tool schemas to avoid repeated queries |
| **Code Execution** | Creates `SandboxInvocation`, runs code, returns results |
| **RPC Routing** | Forwards sandbox RPC requests to real MCP servers |

```python
# Simplified structure
class MCPBridge:
    def __init__(self):
        self.sandbox = RootlessContainerSandbox()  # Container manager
        self.servers = {}      # MCPServerInfo objects
        self.clients = {}      # PersistentMCPClient objects
        self._aliases = {}     # Server name → alias mapping
        self._server_metadata_cache = {}
        # Note: _cleanup_stale_ipc_dirs() runs on init to prune old IPC
        # directories using LRU, keeping max 50
        
    async def execute_code(self, code, servers, timeout):
        # 1. Load requested MCP servers
        # 2. Create SandboxInvocation context
        # 3. Run code in container
        # 4. Handle RPC calls
        # 5. Return result
```

### 3. RootlessContainerSandbox Class

Manages the container lifecycle:

```python
class RootlessContainerSandbox:
    def __init__(self):
        self.runtime = detect_runtime()  # 'podman' or 'docker'
        self.image = "python:3.14-slim"
        self._process = None  # The running container process
        
    def _render_entrypoint(self, servers_metadata, discovered_servers):
        # Generate the ~600 line entrypoint.py
        
    async def _ensure_started(self, ...):
        # Start container if not running
        
    async def execute(self, code, ...):
        # Send code to running container
```

**Container configuration:**
```bash
podman run \
    --rm \
    --interactive \
    --network none \                    # No network access
    --read-only \                       # Read-only filesystem
    --pids-limit 128 \                  # Max 128 processes
    --memory 512m \                     # Max 512MB RAM
    --tmpfs /tmp:rw,noexec,size=64m \   # Writable /tmp
    --tmpfs /workspace:rw,size=128m \   # Writable workspace
    --security-opt no-new-privileges \  # Can't escalate
    --cap-drop ALL \                    # No capabilities
    --user 65534:65534 \                # Nobody user
    python:3.14-slim python3 -u /ipc/entrypoint.py
```

### 4. PersistentMCPClient Class

Maintains connections to real MCP servers:

```python
class PersistentMCPClient:
    def __init__(self, server_info: MCPServerInfo):
        self.server_info = server_info  # command, args, env
        self._session = None
        
    async def start(self):
        # Start the MCP server process
        # Establish stdio communication
        # Initialize MCP session
        
    async def list_tools(self):
        # Get available tools from server
        
    async def call_tool(self, name, arguments):
        # Call a specific tool
```

### 5. SandboxInvocation Class

Per-execution context manager:

```python
class SandboxInvocation:
    def __init__(self, bridge, active_servers):
        self.bridge = bridge
        self.active_servers = active_servers
        
    async def __aenter__(self):
        # 1. Gather server metadata
        # 2. Create temp directory for IPC
        # 3. Set up volume mounts
        # 4. Set environment variables
        
    async def handle_rpc(self, request):
        # Route RPC requests to appropriate MCP server
        # Supported types: list_servers, call_tool, list_tools,
        #                  query_tool_docs, search_tool_docs
```

---

## 🔀 Data Flow

Here's how data flows through the system when the AI calls `run_python`:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                        │
└──────────────────────────────────────────────────────────────────────────────┘

1. AI calls run_python
   ─────────────────►
   
   {
     "name": "run_python",
     "arguments": {
       "code": "weather = await mcp_weather.get_weather('NYC')\nprint(weather)",
       "servers": ["weather"],
       "timeout": 30
     }
   }

2. Bridge validates input
   │
   ├── Check code is non-empty string
   ├── Check servers is a list
   └── Check timeout is valid integer

3. Bridge loads MCP servers
   │
   └── For each server in "servers":
       ├── Find config (from discovery)
       ├── Start PersistentMCPClient (if not running)
       └── Cache metadata

4. Create SandboxInvocation
   │
   ├── Collect server metadata (tools, schemas)
   ├── Create temp directory (/ipc)
   ├── Set up volume mounts
   └── Set environment variables

5. Ensure container is running
   │
   ├── If not started:
   │   ├── Generate entrypoint.py
   │   ├── Write to /ipc/entrypoint.py
   │   └── Start container process
   └── If already started:
       └── Reuse existing container

6. Send code to container
   ─────────────────►
   
   {"type": "execute", "code": "weather = await mcp_weather.get_weather('NYC')..."}

7. Container executes code
   │
   ├── Parse with async support
   ├── Execute in global namespace
   │
   │   Code calls: mcp_weather.get_weather('NYC')
   │              ↓
   │   Proxy intercepts, sends RPC:
   │   {"type": "rpc_request", "id": 1, "payload": {"type": "call_tool", ...}}
   │
   └── Wait for RPC response

8. Bridge receives RPC request
   ◄─────────────────
   
   Bridge routes to PersistentMCPClient for "weather"
   Calls real weather server
   Gets response

9. Bridge sends RPC response
   ─────────────────►
   
   {"type": "rpc_response", "id": 1, "payload": {"result": {"temp": 72, ...}}}

10. Container receives response, continues execution
    │
    ├── print(weather) → {"type": "stdout", "data": "{'temp': 72, ...}"}
    └── Done → {"type": "execution_done"}

11. Bridge collects output
    ◄─────────────────
    
    Aggregates stdout, stderr
    Builds response payload

12. Bridge returns to AI
    ◄─────────────────
    
    {
      "content": [{"type": "text", "text": "{'temp': 72, ...}"}],
      "structuredContent": {"status": "success", "stdout": [...]}
    }
```

---

## 📁 File Structure

```
mcp_server_code_execution_mode.py
├── Constants & Configuration
│   ├── DEFAULT_IMAGE, DEFAULT_TIMEOUT, etc.
│   └── CONFIG_SOURCES (where to find MCP configs)
│
├── Helper Functions
│   ├── _render_compact_output()
│   ├── _build_tool_response()
│   └── detect_runtime()
│
├── Data Classes
│   ├── SandboxResult
│   └── MCPServerInfo
│
├── Core Classes
│   ├── PersistentMCPClient
│   ├── RootlessContainerSandbox
│   │   └── _render_entrypoint() (generates 600-line script)
│   ├── SandboxInvocation
│   └── MCPBridge
│
├── MCP Server Setup
│   ├── @app.list_tools()
│   ├── @app.list_resources()
│   ├── @app.read_resource()
│   └── @app.call_tool()
│
└── main() entrypoint
```

---

## 🔑 Design Decisions

### Why One Tool (`run_python`) Instead of Many?

**Problem:** Traditional MCP loads all tool schemas into context (30,000+ tokens for 100 tools).

**Solution:** One tool that gives the AI the power to discover and call tools programmatically.

**Trade-off:** The AI must write Python code, but this is actually a benefit—LLMs are very good at generating code, and code can express complex logic (loops, conditions) that individual tool calls cannot.

### Why Containers?

**Options considered:**
1. **No isolation** - Too dangerous for untrusted code
2. **VM-based** - Too slow and resource-heavy
3. **Language-level (like Node.js vm)** - Not secure enough
4. **Containers** - Good balance of security and performance

**Containers provide:**
- Strong isolation (namespace separation)
- Lightweight (shared kernel)
- Configurable restrictions (network, filesystem, resources)

### Why Persistent Containers?

Instead of starting a new container for each execution, we keep one running:

| Approach | Cold Start | State Persistence | Resource Usage |
|----------|------------|-------------------|----------------|
| New container each time | ~1-2 seconds | None | High |
| Persistent container | ~0 seconds | Variables persist | Lower |

### Why stdio Communication?

```
Host                    Container
  │                        │
  ├── stdin ──────────────►│
  │                        │
  │◄────────── stdout ─────┤
  │                        │
  │◄────────── stderr ─────┤
```

**Benefits:**
- Simple and universal
- No networking required
- Easy to implement in any language
- Built-in backpressure

---

## Next Steps

→ [Execution Flow](04-execution-flow.md) - Walk through a complete execution
