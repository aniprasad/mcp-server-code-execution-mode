# 4. Execution Flow

This document walks through a complete execution step-by-step, from the AI calling `run_python` to receiving the result.

## 🎬 The Scenario

Let's trace what happens when Claude executes:

```python
# Claude calls run_python with:
{
    "code": "weather = await mcp_weather.get_weather(city='Seattle')\nprint(weather)",
    "servers": ["weather"],
    "timeout": 30
}
```

---

## Phase 1: Request Reception

### Step 1.1: MCP Protocol Handler

```python
# In mcp_server_code_execution_mode.py

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, object]) -> CallToolResult:
    if name != "run_python":
        return _build_tool_response(status="error", ...)
    
    code = arguments.get("code")           # "weather = await mcp_weather..."
    servers = arguments.get("servers", [])  # ["weather"]
    timeout_value = arguments.get("timeout", 30)
```

### Step 1.2: Input Validation

```python
    # Check code is valid
    if not isinstance(code, str) or not code.strip():
        return _build_tool_response(status="validation_error", ...)
    
    # Check servers is a list
    if not isinstance(servers, list):
        return _build_tool_response(status="validation_error", ...)
    
    # Clamp timeout
    timeout_value = max(1, min(MAX_TIMEOUT, timeout_value))
```

### Step 1.3: Call Bridge

```python
    result = await bridge.execute_code(code, servers, timeout_value)
```

---

## Phase 2: Server Loading

### Step 2.1: MCPBridge.execute_code()

```python
# In MCPBridge class

async def execute_code(self, code, server_names, timeout):
    # Load each requested server
    for name in server_names:
        await self.load_server(name)  # "weather"
```

### Step 2.2: Server Discovery

The bridge finds server configs by scanning multiple locations:

```python
CONFIG_SOURCES = [
    Path.home() / "MCPs",                    # ~/MCPs/
    Path.home() / ".config" / "mcp" / "servers",
    Path.home() / ".claude.json",
    Path.home() / ".cursor" / "mcp.json",
    # ... more locations
]
```

For "weather", it might find `~/MCPs/mcp-servers.json`:

```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["C:/path/to/weather.py"],
      "description": "Get weather information"
    }
  }
}
```

### Step 2.3: Start MCP Client

```python
# In load_server()

info = self.servers.get("weather")  # MCPServerInfo object
client = PersistentMCPClient(info)
await client.start()
self.clients["weather"] = client
```

**What `client.start()` does:**

```python
# In PersistentMCPClient.start()

# Create stdio parameters
params = StdioServerParameters(
    command="python",
    args=["C:/path/to/weather.py"],
)

# Start the server process and get read/write streams
client_cm = stdio_client(params)
read_stream, write_stream = await client_cm.__aenter__()

# Create MCP session
session = ClientSession(read_stream, write_stream)
await session.__aenter__()
await session.initialize()  # MCP handshake
```

Now `weather.py` is running as a subprocess, ready to receive tool calls.

---

## Phase 3: Sandbox Preparation

### Step 3.1: Create Invocation Context

```python
async with SandboxInvocation(self, server_names) as invocation:
```

### Step 3.2: Gather Metadata

```python
# In SandboxInvocation.__aenter__()

for server_name in self.active_servers:
    metadata = await self.bridge.get_cached_server_metadata(server_name)
    self.server_metadata.append(metadata)
```

The metadata looks like:
```python
{
    "name": "weather",
    "alias": "weather",
    "tools": [
        {
            "name": "get_weather",
            "alias": "get_weather",
            "description": "Get current weather for a city...",
            "input_schema": {...}
        },
        {
            "name": "get_forecast",
            "alias": "get_forecast",
            "description": "Get weather forecast...",
            "input_schema": {...}
        }
    ]
}
```

### Step 3.3: Create IPC Directory

```python
# Create temp directory on host
self._temp_dir = tempfile.TemporaryDirectory(prefix="mcp-bridge-ipc-")
host_dir = Path(self._temp_dir.name)  # e.g., /tmp/mcp-bridge-ipc-abc123/

# Set up volume mounts
self.volume_mounts.append(f"{host_dir}:/ipc:rw")
```

### Step 3.4: Set Environment

```python
self.container_env["MCP_AVAILABLE_SERVERS"] = json.dumps(self.server_metadata)
self.container_env["MCP_DISCOVERED_SERVERS"] = json.dumps(self.discovered_servers)
```

---

## Phase 4: Container Startup

### Step 4.1: Check If Already Running

```python
# In RootlessContainerSandbox._ensure_started()

if self._process and self._process.returncode is None:
    return  # Container already running, reuse it!
```

**Key insight:** The container is reused across multiple `run_python` calls. This is what makes it "persistent" and allows variables to survive between calls.

### Step 4.2: Generate Entrypoint (First Time Only)

```python
entrypoint_path = host_dir / "entrypoint.py"
entrypoint_path.write_text(
    self._render_entrypoint(servers_metadata, discovered_servers)
)
```

`_render_entrypoint()` generates ~600 lines of Python including:

```python
# Generated entrypoint.py structure:

# === IMPORTS ===
import asyncio, json, sys, types, ...

# === CONFIGURATION ===
AVAILABLE_SERVERS = [{"name": "weather", "alias": "weather", ...}]
DISCOVERED_SERVERS = {"weather": "Get weather info", ...}

# === STREAM PROXIES ===
class _StreamProxy:
    def write(self, data):
        _send_message({"type": self._kind, "data": data})

sys.stdout = _StreamProxy("stdout")
sys.stderr = _StreamProxy("stderr")

# === STDIN READER ===
async def _stdin_reader():
    while True:
        line = await reader.readline()
        message = json.loads(line)
        
        if message["type"] == "rpc_response":
            # Resolve pending RPC
        elif message["type"] == "execute":
            # Queue code for execution

# === RPC MECHANISM ===
async def _rpc_call(payload):
    _send_message({"type": "rpc_request", "id": request_id, "payload": payload})
    return await future  # Wait for response

# === MCP MODULES ===
def _install_mcp_modules():
    # Create mcp.runtime module
    # Create mcp.servers module
    # Add helper functions: save_memory, load_memory, etc.

# === MCP PROXY ===
class _MCPProxy:
    def __getattr__(self, tool_alias):
        async def _invoke(**kwargs):
            return await _rpc_call({
                "type": "call_tool",
                "server": self._server_name,
                "tool": tool_alias,
                "arguments": kwargs,
            })
        return _invoke

# === GLOBAL NAMESPACE ===
_GLOBAL_NAMESPACE = {"__name__": "__sandbox__"}
for server in AVAILABLE_SERVERS:
    proxy = _MCPProxy(server)
    _GLOBAL_NAMESPACE[f"mcp_{server['alias']}"] = proxy  # mcp_weather

# === EXECUTION ===
async def _execute_code(code):
    compiled = compile(code, "<sandbox>", "exec", flags=PyCF_ALLOW_TOP_LEVEL_AWAIT)
    result = eval(compiled, _GLOBAL_NAMESPACE)
    if inspect.isawaitable(result):
        await result

# === MAIN LOOP ===
async def _main_loop():
    asyncio.create_task(_stdin_reader())
    while True:
        code = await _EXECUTION_QUEUE.get()
        await _execute_code(code)
        _send_message({"type": "execution_done"})

asyncio.run(_main_loop())
```

### Step 4.3: Start Container

```python
cmd = [
    "podman", "run",
    "--rm", "--interactive",
    "--network", "none",
    "--read-only",
    "--volume", f"{host_dir}:/ipc:rw",
    # ... more security flags ...
    "python:3.14-slim",
    "python3", "-u", "/ipc/entrypoint.py"
]

self._process = await asyncio.create_subprocess_exec(*cmd, ...)
```

Now the container is running, with `entrypoint.py` waiting for code.

---

## Phase 5: Code Execution

### Step 5.1: Send Code

```python
# In RootlessContainerSandbox.execute()

request = {"type": "execute", "code": code}
process.stdin.write(json.dumps(request).encode() + b"\n")
await process.stdin.drain()
```

The container receives:
```json
{"type": "execute", "code": "weather = await mcp_weather.get_weather(city='Seattle')\nprint(weather)"}
```

### Step 5.2: Container Executes

Inside the container, `_stdin_reader()` receives the message:

```python
# In entrypoint.py

message = json.loads(line)  # {"type": "execute", "code": "..."}
if msg_type == "execute":
    await _EXECUTION_QUEUE.put(message.get("code"))
```

Then `_main_loop()` picks it up:

```python
code = await _EXECUTION_QUEUE.get()
await _execute_code(code)
```

### Step 5.3: Code Calls MCP Proxy

The code does:
```python
weather = await mcp_weather.get_weather(city='Seattle')
```

But `mcp_weather` is an `_MCPProxy`. When you access `get_weather`, Python calls `__getattr__`:

```python
# In _MCPProxy.__getattr__()

def __getattr__(self, tool_alias):  # tool_alias = "get_weather"
    async def _invoke(**kwargs):    # kwargs = {"city": "Seattle"}
        response = await _rpc_call({
            "type": "call_tool",
            "server": "weather",
            "tool": "get_weather",
            "arguments": {"city": "Seattle"},
        })
        return response.get("result")
    return _invoke
```

### Step 5.4: RPC Request

`_rpc_call` sends a request and waits:

```python
async def _rpc_call(payload):
    request_id = _REQUEST_COUNTER  # e.g., 1
    future = loop.create_future()
    _PENDING_RESPONSES[request_id] = future
    
    # Send to host
    _send_message({
        "type": "rpc_request",
        "id": 1,
        "payload": {"type": "call_tool", "server": "weather", ...}
    })
    
    return await future  # Block until response arrives
```

---

## Phase 6: RPC Handling

### Step 6.1: Host Receives RPC

```python
# In RootlessContainerSandbox.execute()

async for line in process.stdout:
    message = json.loads(line)
    
    if message["type"] == "rpc_request":
        response = await rpc_handler(message["payload"])
        # Send response back
```

### Step 6.2: Route to MCP Server

```python
# In SandboxInvocation.handle_rpc()

if req_type == "call_tool":
    server = request.get("server")   # "weather"
    tool = request.get("tool")       # "get_weather"
    arguments = request.get("arguments")  # {"city": "Seattle"}
    
    client = self.bridge.clients.get(server)
    result = await client.call_tool(tool, arguments)
    return {"success": True, "result": result}
```

### Step 6.3: Call Real MCP Server

```python
# In PersistentMCPClient.call_tool()

call_result = await self._session.call_tool(
    name="get_weather",
    arguments={"city": "Seattle"}
)
return call_result.model_dump()
```

This talks to the actual `weather.py` MCP server via stdio, which makes the real API call and returns:

```python
{
    "city": "Seattle",
    "temp": 62,
    "conditions": "cloudy",
    "humidity": 78
}
```

### Step 6.4: Send RPC Response

```python
# Back in RootlessContainerSandbox.execute()

process.stdin.write(json.dumps({
    "type": "rpc_response",
    "id": 1,
    "payload": {"success": True, "result": {"city": "Seattle", ...}}
}).encode() + b"\n")
```

---

## Phase 7: Completion

### Step 7.1: Container Receives Response

```python
# In _stdin_reader()

if msg_type == "rpc_response":
    request_id = message.get("id")  # 1
    future = _PENDING_RESPONSES.pop(request_id)
    future.set_result(message.get("payload"))  # Unblocks _rpc_call
```

### Step 7.2: Code Continues

Now `_rpc_call` returns, and the original code continues:

```python
weather = await mcp_weather.get_weather(city='Seattle')  # Returns {"city": "Seattle", ...}
print(weather)  # Goes to _StreamProxy
```

`print()` goes through `_StreamProxy`:

```python
# _StreamProxy.write()
_send_message({"type": "stdout", "data": "{'city': 'Seattle', 'temp': 62, ...}"})
```

### Step 7.3: Execution Done

```python
# After _execute_code() completes
_send_message({"type": "execution_done"})
```

### Step 7.4: Host Collects Output

```python
# In RootlessContainerSandbox.execute()

if message["type"] == "stdout":
    stdout_chunks.append(message["data"])
elif message["type"] == "execution_done":
    break  # Exit the loop

return SandboxResult(
    success=True,
    exit_code=0,
    stdout="".join(stdout_chunks),
    stderr=""
)
```

---

## Phase 8: Response

### Step 8.1: Build Response

```python
# Back in call_tool()

return _build_tool_response(
    status="success",
    summary="Success",
    exit_code=0,
    stdout="{'city': 'Seattle', 'temp': 62, ...}",
    servers=["weather"]
)
```

### Step 8.2: Return to AI

```python
CallToolResult(
    content=[
        TextContent(type="text", text="{'city': 'Seattle', 'temp': 62, ...}")
    ],
    structuredContent={
        "status": "success",
        "stdout": ["{'city': 'Seattle', 'temp': 62, ...}"]
    },
    isError=False
)
```

---

## 📊 Timeline Summary

```
Time
  │
  ├─── AI calls run_python ────────────────────────────────────┐
  │                                                            │
  │                      BRIDGE                                │
  ├─── Validate input ─────────────────────────────────────────┤
  ├─── Load "weather" server ──────────────────────────────────┤
  ├─── Create SandboxInvocation ───────────────────────────────┤
  ├─── Generate entrypoint.py (if first time) ─────────────────┤
  ├─── Start container (if first time) ────────────────────────┤
  │                                                            │
  │                      CONTAINER                             │
  ├─── Send code to container ─────────────────────────────────┤
  ├─── Container executes code ────────────────────────────────┤
  ├─── Code calls mcp_weather.get_weather() ───────────────────┤
  ├─── RPC request sent ───────────────────────────────────────┤
  │                                                            │
  │                      BRIDGE                                │
  ├─── Receive RPC request ────────────────────────────────────┤
  ├─── Call real weather MCP server ───────────────────────────┤
  ├─── Receive result from weather server ─────────────────────┤
  ├─── Send RPC response to container ─────────────────────────┤
  │                                                            │
  │                      CONTAINER                             │
  ├─── Receive RPC response ───────────────────────────────────┤
  ├─── Continue execution (print) ─────────────────────────────┤
  ├─── Send execution_done ────────────────────────────────────┤
  │                                                            │
  │                      BRIDGE                                │
  ├─── Collect output ─────────────────────────────────────────┤
  ├─── Build response ─────────────────────────────────────────┤
  └─── Return to AI ───────────────────────────────────────────┘
```

---

## Next Steps

→ [Sandbox Runtime](05-sandbox-runtime.md) - Deep dive into entrypoint.py
