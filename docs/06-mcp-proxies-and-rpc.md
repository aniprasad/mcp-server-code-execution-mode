# 6. MCP Proxies & RPC

This document provides an in-depth look at how the sandbox communicates with external MCP servers through proxies and RPC (Remote Procedure Calls).

## 🎯 The Challenge

The sandbox runs in an isolated container with **no network access**. But LLM code needs to call MCP tools like `mcp_weather.get_weather()`. How do we bridge this gap?

**Solution:** Proxy objects that convert method calls into JSON messages sent to the host over stdio.

---

## 🔀 Communication Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CONTAINER                                       │
│                                                                             │
│   LLM Code                                                                  │
│   ────────                                                                  │
│   weather = await mcp_weather.get_weather(city="Seattle")                   │
│                        │                                                    │
│                        ▼                                                    │
│   ┌──────────────────────────────────────────────────┐                      │
│   │ _MCPProxy.__getattr__("get_weather")             │                      │
│   │                                                  │                      │
│   │ Returns async function that calls _rpc_call()    │                      │
│   └────────────────────────┬─────────────────────────┘                      │
│                            │                                                │
│                            ▼                                                │
│   ┌──────────────────────────────────────────────────┐                      │
│   │ _rpc_call({                                      │                      │
│   │   "type": "call_tool",                           │                      │
│   │   "server": "weather",                           │                      │
│   │   "tool": "get_weather",                         │                      │
│   │   "arguments": {"city": "Seattle"}               │                      │
│   │ })                                               │                      │
│   │                                                  │                      │
│   │ 1. Create Future                                 │                      │
│   │ 2. Store in _PENDING_RESPONSES[id=1]             │                      │
│   │ 3. Send JSON to stdout                           │                      │
│   │ 4. await Future (blocks here)                    │                      │
│   └────────────────────────┬─────────────────────────┘                      │
│                            │                                                │
│                            ▼ (stdout)                                       │
│   {"type":"rpc_request","id":1,"payload":{...}}                             │
│                                                                             │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
══════════════════════════════╪════════════════════════════════════════════════
                              │ (stdio pipe)
══════════════════════════════╪════════════════════════════════════════════════
                              │
┌─────────────────────────────▼───────────────────────────────────────────────┐
│                              HOST                                            │
│                                                                             │
│   ┌──────────────────────────────────────────────────┐                      │
│   │ RootlessContainerSandbox.execute()               │                      │
│   │                                                  │                      │
│   │ Reads JSON from container stdout                 │                      │
│   │ Sees type="rpc_request"                          │                      │
│   │ Calls rpc_handler(payload)                       │                      │
│   └────────────────────────┬─────────────────────────┘                      │
│                            │                                                │
│                            ▼                                                │
│   ┌──────────────────────────────────────────────────┐                      │
│   │ SandboxInvocation.handle_rpc()                   │                      │
│   │                                                  │                      │
│   │ Validates server is allowed                      │                      │
│   │ Routes to appropriate handler                    │                      │
│   └────────────────────────┬─────────────────────────┘                      │
│                            │                                                │
│                            ▼                                                │
│   ┌──────────────────────────────────────────────────┐                      │
│   │ PersistentMCPClient.call_tool()                  │                      │
│   │                                                  │                      │
│   │ Calls the REAL MCP server via MCP protocol       │                      │
│   └────────────────────────┬─────────────────────────┘                      │
│                            │                                                │
│                            ▼                                                │
│   ┌──────────────────────────────────────────────────┐                      │
│   │ Real MCP Server (weather.py)                     │                      │
│   │                                                  │                      │
│   │ Makes actual API call to Open-Meteo              │                      │
│   │ Returns result                                   │                      │
│   └────────────────────────┬─────────────────────────┘                      │
│                            │                                                │
│                            ▼ (back up the chain)                            │
│   {"type":"rpc_response","id":1,"payload":{...,"result":{...}}}             │
│                            │                                                │
│                            ▼ (stdin to container)                           │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
══════════════════════════════╪════════════════════════════════════════════════
                              │
┌─────────────────────────────▼───────────────────────────────────────────────┐
│                              CONTAINER                                       │
│                                                                             │
│   ┌──────────────────────────────────────────────────┐                      │
│   │ _stdin_reader()                                  │                      │
│   │                                                  │                      │
│   │ Reads JSON from stdin                            │                      │
│   │ Sees type="rpc_response", id=1                   │                      │
│   │ Looks up _PENDING_RESPONSES[1]                   │                      │
│   │ Resolves the Future with payload                 │                      │
│   └────────────────────────┬─────────────────────────┘                      │
│                            │                                                │
│                            ▼                                                │
│   ┌──────────────────────────────────────────────────┐                      │
│   │ _rpc_call() resumes                              │                      │
│   │                                                  │                      │
│   │ Future resolved, returns result                  │                      │
│   └────────────────────────┬─────────────────────────┘                      │
│                            │                                                │
│                            ▼                                                │
│   weather = {"city": "Seattle", "temp": 62, ...}                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎭 The Proxy Class in Detail

```python
class _MCPProxy:
    """
    A proxy object that makes MCP tool calls look like regular method calls.
    
    Example:
        proxy = _MCPProxy({"name": "weather", "tools": [...]})
        result = await proxy.get_weather(city="NYC")
        
    What actually happens:
        1. proxy.get_weather triggers __getattr__("get_weather")
        2. __getattr__ returns an async function
        3. Calling that function sends RPC and awaits response
    """
    
    def __init__(self, server_info):
        # Store server name for RPC calls
        self._server_name = server_info["name"]  # "weather"
        
        # Build lookup table: tool alias → tool info
        self._tools = {
            tool["alias"]: tool 
            for tool in server_info.get("tools", [])
        }
        # Example: {"get_weather": {"name": "get_weather", ...}}
    
    async def list_tools(self):
        """Explicitly defined method to list available tools."""
        response = await _rpc_call({
            "type": "list_tools",
            "server": self._server_name,
        })
        if not response.get("success", True):
            raise RuntimeError(response.get("error"))
        return response.get("tools", [])
    
    def __getattr__(self, tool_alias):
        """
        Python magic method called when accessing undefined attributes.
        
        When you write: proxy.get_weather
        Python sees 'get_weather' is not defined, so it calls:
            proxy.__getattr__("get_weather")
        """
        
        # Look up the tool in our registry
        tool = self._tools.get(tool_alias)
        
        # Get the real tool name (might differ from alias)
        target = tool.get("name") if tool else tool_alias
        
        # Get description for documentation
        summary = (tool.get("description") if tool else "") or ""
        
        # Create and return an async function
        async def _invoke(_target=target, **kwargs):
            """
            This function is returned by __getattr__ and called by the user.
            
            _target is captured via default argument (closure trick).
            **kwargs captures all arguments like city="Seattle".
            """
            response = await _rpc_call({
                "type": "call_tool",
                "server": self._server_name,
                "tool": _target,
                "arguments": kwargs,
            })
            
            if not response.get("success", True):
                raise RuntimeError(response.get("error", "MCP call failed"))
            
            return response.get("result")
        
        # Add documentation to the function
        if summary:
            _invoke.__doc__ = summary
        _invoke.__name__ = tool_alias
        
        return _invoke
```

### Why `__getattr__` instead of regular methods?

We don't know what tools exist at development time. Different servers have different tools. `__getattr__` lets us handle **any** method name dynamically:

```python
# All of these work without pre-defining methods:
await mcp_weather.get_weather(city="NYC")
await mcp_weather.get_forecast(days=5)
await mcp_weather.some_new_tool()

# They all trigger __getattr__ with the method name
```

### The Default Argument Trick

Notice `_target=target` in the function definition:

```python
async def _invoke(_target=target, **kwargs):
```

This is a Python closure trick. Without it, `target` would be looked up when `_invoke` runs, not when it's created. By using a default argument, we "capture" the value at creation time.

---

## 📞 RPC Call Mechanism

```python
# Global state for tracking pending requests
_PENDING_RESPONSES = {}  # id → Future
_REQUEST_COUNTER = 0     # Incrementing counter for unique IDs


async def _rpc_call(payload):
    """
    Send an RPC request and wait for the response.
    
    This is the core of sandbox↔host communication.
    
    Args:
        payload: Dict with request details
            - type: "call_tool", "list_tools", "query_tool_docs", etc.
            - server: Server name for tool calls
            - tool: Tool name for tool calls
            - arguments: Dict of tool arguments
    
    Returns:
        Response payload from host
    
    Raises:
        RuntimeError: If host returns error
    """
    
    loop = asyncio.get_running_loop()
    
    # Generate unique request ID
    global _REQUEST_COUNTER
    _REQUEST_COUNTER += 1
    request_id = _REQUEST_COUNTER
    
    # Create a Future - this is an "awaitable promise"
    future = loop.create_future()
    
    # Store it so _stdin_reader can resolve it later
    _PENDING_RESPONSES[request_id] = future
    
    # Send the request to host via stdout
    _send_message({
        "type": "rpc_request",
        "id": request_id,
        "payload": payload
    })
    
    # Wait here until _stdin_reader resolves the future
    return await future
```

### How Futures Work

A `Future` is like a "promise" in JavaScript:

```python
# Creating a future
future = loop.create_future()

# This blocks until someone resolves it
result = await future  # <-- blocks here

# Somewhere else (in _stdin_reader):
future.set_result({"temp": 72})  # <-- unblocks the await
```

### Request Tracking

```python
# Step 1: Create request, store future
_PENDING_RESPONSES[1] = future
# State: {1: <Future pending>}

# Step 2: Send request
# Host processes it...

# Step 3: Host sends response with same ID
# _stdin_reader receives: {"type": "rpc_response", "id": 1, ...}

# Step 4: Look up and resolve
future = _PENDING_RESPONSES.pop(1)
future.set_result(response)
# State: {} (removed)
```

---

## 🛠️ RPC Types

The sandbox can send these RPC request types:

### call_tool

Execute an MCP tool:

```python
# Request
{
    "type": "rpc_request",
    "id": 1,
    "payload": {
        "type": "call_tool",
        "server": "weather",
        "tool": "get_weather",
        "arguments": {"city": "Seattle"}
    }
}

# Response
{
    "type": "rpc_response",
    "id": 1,
    "payload": {
        "success": True,
        "result": {"city": "Seattle", "temp": 62, ...}
    }
}
```

### list_tools

Get available tools for a server:

```python
# Request
{
    "type": "rpc_request",
    "id": 2,
    "payload": {
        "type": "list_tools",
        "server": "weather"
    }
}

# Response
{
    "type": "rpc_response",
    "id": 2,
    "payload": {
        "success": True,
        "tools": [
            {"name": "get_weather", ...},
            {"name": "get_forecast", ...}
        ]
    }
}
```

### list_servers

Get loaded servers:

```python
# Request
{"type": "rpc_request", "id": 3, "payload": {"type": "list_servers"}}

# Response
{
    "type": "rpc_response",
    "id": 3,
    "payload": {
        "success": True,
        "servers": ["weather", "sports"]
    }
}
```

### query_tool_docs

Get documentation for tools:

```python
# Request - all tools for a server
{
    "type": "rpc_request",
    "id": 4,
    "payload": {
        "type": "query_tool_docs",
        "server": "weather",
        "detail": "full"  # or "summary"
    }
}

# Request - specific tool
{
    "type": "rpc_request",
    "id": 5,
    "payload": {
        "type": "query_tool_docs",
        "server": "weather",
        "tool": "get_weather",
        "detail": "full"
    }
}
```

### search_tool_docs

Search across all loaded servers:

```python
# Request
{
    "type": "rpc_request",
    "id": 6,
    "payload": {
        "type": "search_tool_docs",
        "query": "current temperature",
        "limit": 5,
        "detail": "summary"
    }
}

# Response
{
    "type": "rpc_response",
    "id": 6,
    "payload": {
        "success": True,
        "results": [
            {"server": "weather", "tool": "get_weather", "description": "..."},
            ...
        ]
    }
}
```

---

## 🏠 Host-Side RPC Handling

On the host, `SandboxInvocation.handle_rpc()` processes requests:

```python
# In SandboxInvocation class

async def handle_rpc(self, request: Dict[str, object]) -> Dict[str, object]:
    req_type = request.get("type")
    
    # List loaded servers
    if req_type == "list_servers":
        return {
            "success": True,
            "servers": sorted(self.allowed_servers),
        }
    
    # Query tool documentation
    if req_type == "query_tool_docs":
        server = request.get("server")
        if server not in self.allowed_servers:
            return {"success": False, "error": f"Server {server!r} not available"}
        
        docs = await self.bridge.get_tool_docs(server, ...)
        return {"success": True, "docs": docs}
    
    # Search tools
    if req_type == "search_tool_docs":
        results = await self.bridge.search_tool_docs(query, ...)
        return {"success": True, "results": results}
    
    # Call a tool
    if req_type == "call_tool":
        server = request.get("server")
        tool = request.get("tool")
        arguments = request.get("arguments", {})
        
        # Validate server is allowed
        if server not in self.allowed_servers:
            return {"success": False, "error": f"Server {server!r} not available"}
        
        # Get the MCP client for this server
        client = self.bridge.clients.get(server)
        
        # Call the actual tool
        result = await client.call_tool(tool, arguments)
        return {"success": True, "result": result}
```

---

## 🔒 Security Considerations

### Server Allowlist

The sandbox can only access servers that were requested in `run_python`:

```python
# If LLM called run_python(code="...", servers=["weather"])

# This works:
await mcp_weather.get_weather(city="NYC")

# This fails (sports wasn't requested):
await mcp_sports.scoreboard(sport='nba')
# Error: "Server 'sports' is not available"
```

### Request Validation

All RPC requests are validated:
- Server name must be in allowed list
- Tool name must exist on server
- Arguments are passed through to real MCP server for validation

### No Direct Network

Even if malicious code tries to make network calls, it can't:

```python
# This fails - no network in container
import requests
requests.get("https://evil.com")
# Error: Network unreachable
```

---

## 🔄 Parallel RPC Calls

Multiple RPC calls can be in flight simultaneously:

```python
# These run in parallel, not sequentially
results = await asyncio.gather(
    mcp_weather.get_weather(city="NYC"),
    mcp_weather.get_weather(city="LA"),
    mcp_sports.scoreboard(sport='nba'),
)
```

**How it works:**

```
Time →

Request 1 (id=1) ──────────────────────────────────────►
                    ↑ sent                    ↑ received

Request 2 (id=2) ──────────────────────────────────────►
                    ↑ sent                    ↑ received

Request 3 (id=3) ──────────────────────────────────────►
                    ↑ sent                    ↑ received

All three are awaited together via asyncio.gather()
```

Each request has a unique ID, so responses can arrive in any order and still be matched correctly.

---

## 🧪 Example: Complete RPC Trace

```python
# LLM code:
weather = await mcp_weather.get_weather(city="Seattle")
print(f"Temperature: {weather['temp']}")
```

**Step-by-step trace:**

```
1. Code accesses mcp_weather.get_weather
   → __getattr__("get_weather") called
   → Returns async function _invoke

2. Code calls _invoke(city="Seattle")
   → _rpc_call({
       "type": "call_tool",
       "server": "weather", 
       "tool": "get_weather",
       "arguments": {"city": "Seattle"}
     })

3. _rpc_call creates request
   → _REQUEST_COUNTER = 1
   → future = loop.create_future()
   → _PENDING_RESPONSES[1] = future

4. _rpc_call sends message
   → stdout: {"type":"rpc_request","id":1,"payload":{...}}

5. _rpc_call awaits future
   → Execution pauses here

6. Host receives request
   → Parses JSON
   → Sees type="rpc_request"
   → Calls handle_rpc(payload)

7. Host calls real MCP server
   → PersistentMCPClient.call_tool("get_weather", {"city": "Seattle"})
   → Weather server makes HTTP request to API
   → Returns {"city": "Seattle", "temp": 62, ...}

8. Host sends response
   → stdin: {"type":"rpc_response","id":1,"payload":{"success":true,"result":{...}}}

9. _stdin_reader receives response
   → Parses JSON
   → Sees type="rpc_response", id=1
   → future = _PENDING_RESPONSES.pop(1)
   → future.set_result(payload)

10. _rpc_call resumes
    → return await future  # Returns payload
    → _invoke returns payload["result"]
    → weather = {"city": "Seattle", "temp": 62, ...}

11. Code continues
    → print(f"Temperature: {weather['temp']}")
    → _StreamProxy.write("Temperature: 62\n")
    → stdout: {"type":"stdout","data":"Temperature: 62\n"}
```

---

## Next Steps

→ [Server Discovery](07-server-discovery.md) - How MCP servers are found
