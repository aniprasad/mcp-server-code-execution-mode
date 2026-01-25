# 2. Core Concepts

Before diving deeper, let's establish the key terms and concepts you'll encounter throughout this documentation.

## 📖 Glossary

### MCP (Model Context Protocol)

A standard protocol for AI models to communicate with external tools and services. Think of it as a "USB standard" for AI tools—any MCP-compatible client can talk to any MCP server.

```
┌─────────────────┐         MCP Protocol        ┌─────────────────┐
│   Claude,       │◄───────────────────────────►│  Any MCP Server │
│   ChatGPT, etc  │    (JSON-RPC over stdio)    │  (tools)        │
└─────────────────┘                             └─────────────────┘
```

### MCP Server

A program that exposes "tools" to an AI. Examples:
- **Filesystem server** - read/write files
- **Weather server** - get weather data
- **Database server** - query databases

Each server defines tools with:
- **Name**: e.g., `read_file`
- **Description**: What it does
- **Input Schema**: What parameters it accepts
- **Output**: What it returns

### MCP Client

A program that calls MCP servers. In our case, this bridge acts as a client to connect to weather, soccer, and other MCP servers.

### The Bridge

This project! It sits between:
- The **AI** (which sends Python code)
- The **container** (which runs the code)
- The **MCP servers** (which provide actual capabilities)

### Sandbox / Container

An isolated environment where code runs. Think of it as a "virtual computer" with:
- No internet access
- No ability to write to the host filesystem
- No special permissions
- Limited memory and CPU

We use **Docker** or **Podman** containers for this isolation.

### Entrypoint

The Python script that runs inside the container before the AI's code. It sets up:
- Stream proxies (so `print()` works)
- MCP proxies (so `mcp_weather.get_weather()` works)
- The main loop (waiting for code to execute)

Think of it as the "operating system" for the sandbox.

### RPC (Remote Procedure Call)

A way for the sandbox to call code on the host. Since the sandbox has no network, it can't call MCP servers directly. Instead:

1. Sandbox sends a JSON message: "Please call `weather.get_weather`"
2. Host receives it, calls the real MCP server
3. Host sends response back to sandbox

### Proxy

A "fake" object that looks real but actually forwards calls elsewhere. In the sandbox:

```python
# This looks like a direct call:
await mcp_weather.get_weather(city="Seattle")

# But mcp_weather is a PROXY that:
# 1. Catches the method call
# 2. Sends it as JSON to the host
# 3. Waits for the response
# 4. Returns the result
```

### Discovery

The process of finding out what MCP servers and tools are available, without loading their full schemas upfront:

```python
# "What servers exist?"
runtime.discovered_servers()
# → ['weather', 'soccer', 'filesystem']

# "What tools does 'weather' have?"
await runtime.query_tool_docs('weather')
# → [{'name': 'get_weather', 'description': '...'}]
```

### Persistence

The ability to save data/functions across multiple code executions:

```python
# First execution:
save_memory("user_city", "Seattle")

# Later execution:
city = load_memory("user_city")  # → "Seattle"
```

---

## 🧩 Component Overview

Here's how all the pieces fit together:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              THE BIG PICTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                         HOST MACHINE                                 │  │
│   │                                                                      │  │
│   │   ┌───────────┐    MCP      ┌──────────────────────────────────┐    │  │
│   │   │  Claude   │◄──────────►│        MCPBridge                  │    │  │
│   │   │  Desktop  │  (stdio)   │  (mcp_server_code_execution_mode) │    │  │
│   │   └───────────┘            │                                   │    │  │
│   │                            │  • Exposes run_python tool        │    │  │
│   │                            │  • Manages container lifecycle    │    │  │
│   │                            │  • Routes RPC calls               │    │  │
│   │                            │  • Connects to MCP servers        │    │  │
│   │                            └───────────────┬──────────────────┘    │  │
│   │                                            │                        │  │
│   │                            ┌───────────────┼───────────────┐        │  │
│   │                            │               │               │        │  │
│   │                            ▼               ▼               ▼        │  │
│   │                     ┌──────────┐    ┌──────────┐    ┌──────────┐    │  │
│   │                     │ MCP      │    │ MCP      │    │ MCP      │    │  │
│   │                     │ weather  │    │ soccer   │    │ other    │    │  │
│   │                     └──────────┘    └──────────┘    └──────────┘    │  │
│   │                                                                      │  │
│   │   ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │  │
│   │                                                                      │  │
│   │   ┌──────────────────────────────────────────────────────────────┐  │  │
│   │   │              CONTAINER (Docker/Podman)                       │  │  │
│   │   │              ═══════════════════════════                     │  │  │
│   │   │                                                              │  │  │
│   │   │    🔒 Network: DISABLED     🔒 Filesystem: READ-ONLY        │  │  │
│   │   │    🔒 Privileges: NONE      🔒 Resources: LIMITED           │  │  │
│   │   │                                                              │  │  │
│   │   │    ┌────────────────────────────────────────────────────┐   │  │  │
│   │   │    │              entrypoint.py                         │   │  │  │
│   │   │    │              (~600 lines)                          │   │  │  │
│   │   │    │                                                    │   │  │  │
│   │   │    │  • Stream proxies (print → JSON)                   │   │  │  │
│   │   │    │  • MCP proxies (mcp_weather, mcp_soccer)           │   │  │  │
│   │   │    │  • RPC mechanism (_rpc_call)                       │   │  │  │
│   │   │    │  • Runtime helpers (save_memory, etc)              │   │  │  │
│   │   │    │  • Main loop (wait for code)                       │   │  │  │
│   │   │    └────────────────────────────────────────────────────┘   │  │  │
│   │   │                           │                                  │  │  │
│   │   │                           ▼                                  │  │  │
│   │   │    ┌────────────────────────────────────────────────────┐   │  │  │
│   │   │    │              LLM's Python Code                     │   │  │  │
│   │   │    │                                                    │   │  │  │
│   │   │    │  weather = await mcp_weather.get_weather("NYC")    │   │  │  │
│   │   │    │  print(weather)                                    │   │  │  │
│   │   │    └────────────────────────────────────────────────────┘   │  │  │
│   │   │                                                              │  │  │
│   │   └──────────────────────────────────────────────────────────────┘  │  │
│   │                                                                      │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 💡 Key Insight: Two Types of Code

A crucial thing to understand is that there are **two different pieces of Python code**:

### 1. Entrypoint Code (Infrastructure)
- Written by the bridge developers (us)
- ~600 lines
- Runs ONCE when container starts
- Provides: proxies, helpers, main loop
- Lives in: `/ipc/entrypoint.py` inside the container

### 2. LLM's Code (User Code)
- Generated by the AI (Claude, etc.)
- Usually just a few lines
- Runs EACH TIME `run_python` is called
- Uses the infrastructure from entrypoint
- Sent via stdin as JSON

```
Timeline:
─────────────────────────────────────────────────────────────────►

Container      Entrypoint     Wait for    Execute      Wait for    Execute
  starts    →   code runs  →   code...  → LLM code1 →  code...  → LLM code2 ...
                  (once)      (idle)      (2 lines)    (idle)     (5 lines)
```

---

## 🔄 Message Types

Communication between host and container uses JSON "messages" over stdin/stdout:

### Host → Container

| Type | Purpose | Example |
|------|---------|---------|
| `execute` | Run some Python code | `{"type": "execute", "code": "print(1+1)"}` |
| `rpc_response` | Reply to an RPC request | `{"type": "rpc_response", "id": 1, "payload": {...}}` |

### Container → Host

| Type | Purpose | Example |
|------|---------|---------|
| `stdout` | Print output | `{"type": "stdout", "data": "Hello"}` |
| `stderr` | Error output | `{"type": "stderr", "data": "Error!"}` |
| `rpc_request` | Call MCP tool | `{"type": "rpc_request", "id": 1, "payload": {...}}` |
| `execution_done` | Code finished | `{"type": "execution_done"}` |

---

## Next Steps

→ [Architecture](03-architecture.md) - See how components are structured
