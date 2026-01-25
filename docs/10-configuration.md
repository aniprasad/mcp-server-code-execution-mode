# 10. Configuration

This document covers all configuration options for the MCP Server Code Execution Mode bridge.

## 🔧 Environment Variables

### Container Runtime

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MCP_BRIDGE_RUNTIME` | Force specific runtime | Auto-detect | `podman` or `docker` |
| `MCP_BRIDGE_IMAGE` | Container image | `python:3.14-slim` | `python:3.12-slim` |

```bash
# Force podman
export MCP_BRIDGE_RUNTIME=podman

# Use a different Python version
export MCP_BRIDGE_IMAGE=python:3.12-slim
```

### Resource Limits

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MCP_BRIDGE_MEMORY` | Memory limit | `512m` | `1g` |
| `MCP_BRIDGE_PIDS` | Max processes | `128` | `256` |
| `MCP_BRIDGE_CPUS` | CPU quota | (host default) | `2.0` |
| `MCP_BRIDGE_CONTAINER_USER` | UID:GID | `65534:65534` | `1000:1000` |

```bash
# Give more memory for data science work
export MCP_BRIDGE_MEMORY=2g

# Allow more processes for parallel work
export MCP_BRIDGE_PIDS=256

# Limit to 2 CPU cores
export MCP_BRIDGE_CPUS=2.0
```

### Timeouts

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MCP_BRIDGE_TIMEOUT` | Default execution timeout (seconds) | `30` | `60` |
| `MCP_BRIDGE_MAX_TIMEOUT` | Maximum allowed timeout | `120` | `300` |
| `MCP_BRIDGE_RUNTIME_IDLE_TIMEOUT` | Auto-shutdown delay (seconds) | `300` | `600` |

```bash
# Allow longer-running code by default
export MCP_BRIDGE_TIMEOUT=60

# Allow up to 5 minutes for heavy computation
export MCP_BRIDGE_MAX_TIMEOUT=300

# Keep runtime warm for 10 minutes
export MCP_BRIDGE_RUNTIME_IDLE_TIMEOUT=600
```

### Output Format

| Variable | Description | Default | Values |
|----------|-------------|---------|--------|
| `MCP_BRIDGE_OUTPUT_MODE` | Response format | `compact` | `compact`, `toon` |

```bash
# Use TOON format for structured output
export MCP_BRIDGE_OUTPUT_MODE=toon
```

### Logging

| Variable | Description | Default | Values |
|----------|-------------|---------|--------|
| `MCP_BRIDGE_LOG_LEVEL` | Log verbosity | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

```bash
# Enable debug logging
export MCP_BRIDGE_LOG_LEVEL=DEBUG
```

### Windows Support

The bridge includes Windows-specific handling:

- **Event Loop**: Uses `WindowsProactorEventLoopPolicy` for proper async subprocess support
- **Handle Cleanup**: Properly cleans up process handles to avoid `ResourceWarning`
- **IPC Cleanup**: LRU-based cleanup keeps max 50 IPC directories to prevent accumulation

### State Directory

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_BRIDGE_STATE_DIR` | Directory for persistence | `~/MCPs` |

```bash
# Use a different state directory
export MCP_BRIDGE_STATE_DIR=/var/lib/mcp-state
```

### Server Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_SERVERS_CONFIG` | Override config path | (auto-discover) |

```bash
# Use a specific config file
export MCP_SERVERS_CONFIG=/path/to/my-servers.json
```

---

## 📄 MCP Server Configuration

### Configuration File Format

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

### Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `command` | Yes | Executable to run |
| `args` | No | Command line arguments (array) |
| `env` | No | Environment variables (object) |
| `cwd` | No | Working directory |
| `description` | No | Human-readable description |

### Example Configurations

**Python server (no API key needed):**
```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["C:/Users/you/servers/weather.py"],
      "description": "Get weather information (uses Open-Meteo, free!)"
    }
  }
}
```

**Python server with API key:**
```json
{
  "mcpServers": {
    "soccer": {
      "command": "python",
      "args": ["C:/Users/you/servers/soccer.py"],
      "env": {
        "FOOTBALL_API_KEY": "your-api-key"
      },
      "description": "Get live soccer matches and standings"
    }
  }
}
```

**Node.js server:**
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "node",
      "args": ["C:/Users/you/servers/filesystem.js"],
      "cwd": "C:/Users/you/projects",
      "description": "File system operations"
    }
  }
}
```

**UV-managed Python:**
```json
{
  "mcpServers": {
    "my-server": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/user/my-mcp-server",
        "my-mcp-server",
        "run"
      ],
      "description": "My custom MCP server"
    }
  }
}
```

---

## 📍 Configuration Locations

The bridge searches these locations (in order):

### Primary Locations

| Location | Type | Priority |
|----------|------|----------|
| `~/MCPs/` | Directory | 1 (Highest) |
| `~/.config/mcp/servers/` | Directory | 2 |
| `./mcp-servers/` | Directory | 3 |
| `./.vscode/mcp.json` | File | 4 |

### Application-Specific

| Location | Application |
|----------|-------------|
| `~/.claude.json` | Claude CLI |
| `~/.cursor/mcp.json` | Cursor |
| `~/.opencode.json` | OpenCode |
| `~/.codeium/windsurf/mcp_config.json` | Windsurf |

### Platform-Specific (macOS)

| Location |
|----------|
| `~/Library/Application Support/Claude/claude_desktop_config.json` |
| `~/Library/Application Support/Code/User/settings.json` |

### Platform-Specific (Linux)

| Location |
|----------|
| `~/.config/Code/User/settings.json` |

---

## 🎛️ Run Python Tool Parameters

When the LLM calls `run_python`, it can specify:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `code` | string | Yes | - | Python code to execute |
| `servers` | array | No | `[]` | MCP servers to load |
| `timeout` | integer | No | `30` | Execution timeout (seconds) |

**Example:**
```json
{
  "name": "run_python",
  "arguments": {
    "code": "weather = await mcp_weather.get_weather(city='NYC')\nprint(weather)",
    "servers": ["weather"],
    "timeout": 60
  }
}
```

---

## 🏗️ Recommended Setup

### Development

```bash
# Create config directory
mkdir -p ~/MCPs

# Create config file
cat > ~/MCPs/mcp-servers.json << 'EOF'
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["/path/to/weather.py"],
      "description": "Weather info (Open-Meteo, no key needed!)"
    }
  }
}
EOF

# Set environment for development
export MCP_BRIDGE_LOG_LEVEL=DEBUG
export MCP_BRIDGE_TIMEOUT=60
```

### Production

```bash
# Use specific config
export MCP_SERVERS_CONFIG=/etc/mcp/servers.json

# Tighter limits
export MCP_BRIDGE_MEMORY=256m
export MCP_BRIDGE_TIMEOUT=30
export MCP_BRIDGE_MAX_TIMEOUT=60

# Standard logging
export MCP_BRIDGE_LOG_LEVEL=INFO
```

---

## 📋 Configuration Checklist

### First-Time Setup

- [ ] Install podman or rootless docker
- [ ] Pull the container image: `podman pull python:3.14-slim`
- [ ] Create `~/MCPs/` directory
- [ ] Create at least one server configuration
- [ ] Test the bridge: `python mcp_server_code_execution_mode.py`

### MCP Server Setup

- [ ] Server script is executable or uses interpreter
- [ ] Required environment variables are set
- [ ] Working directory is correct (if needed)
- [ ] Server dependencies are installed

### Security Review

- [ ] Resource limits are appropriate
- [ ] Timeout values are reasonable
- [ ] Only needed servers are configured
- [ ] API keys are not in code (use env vars)

---

## 🔍 Troubleshooting Configuration

### Server Not Found

```
Error: Unknown MCP server: weather
```

**Check:**
1. Config file exists in a discovery location
2. Server name in config matches requested name
3. Config file is valid JSON

### Server Won't Start

```
Error: Failed to start MCP server
```

**Check:**
1. Command exists and is in PATH
2. Script path is absolute
3. Required environment variables are set
4. Dependencies are installed

### Permission Denied

```
Error: Permission denied
```

**Check:**
1. Script is executable: `chmod +x server.py`
2. Working directory is accessible
3. Environment variables don't contain secrets in logs

### Container Runtime Not Found

```
Error: No container runtime found
```

**Check:**
1. Podman or Docker is installed
2. Runtime is in PATH
3. Set `MCP_BRIDGE_RUNTIME` if needed

---

## 📊 Full Configuration Example

**`~/MCPs/mcp-servers.json`:**

```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["C:/Users/dev/servers/weather.py"],
      "description": "Weather information (Open-Meteo, no key needed!)"
    },
    "soccer": {
      "command": "python",
      "args": ["C:/Users/dev/servers/soccer.py"],
      "env": {
        "FOOTBALL_API_KEY": "${FOOTBALL_API_KEY}"
      },
      "description": "Live soccer matches and standings"
    },
    "calculator": {
      "command": "python",
      "args": ["C:/Users/dev/servers/calculator.py"],
      "description": "Mathematical operations"
    },
    "filesystem": {
      "command": "node",
      "args": ["C:/Users/dev/servers/filesystem.js"],
      "cwd": "C:/Users/dev/projects",
      "description": "File system operations"
    }
  }
}
```

**Environment setup (`~/.bashrc` or equivalent):**

```bash
# MCP Bridge configuration
export MCP_BRIDGE_RUNTIME=podman
export MCP_BRIDGE_MEMORY=1g
export MCP_BRIDGE_TIMEOUT=60
export MCP_BRIDGE_MAX_TIMEOUT=180
export MCP_BRIDGE_LOG_LEVEL=INFO

# API keys for servers that need them
# (Note: weather.py uses Open-Meteo which is free and needs no key!)
export FOOTBALL_API_KEY=your-key-here
```

---

## 🔗 Related Documentation

- [Architecture](03-architecture.md) - System design
- [Server Discovery](07-server-discovery.md) - How servers are found
- [Creating MCP Servers](08-creating-mcp-servers.md) - Build your own
- [Security Model](09-security-model.md) - Security features

---

This completes the configuration documentation. For questions or issues, refer to the main README or open an issue on GitHub.
