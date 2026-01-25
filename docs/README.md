# MCP Server Code Execution Mode Documentation

Welcome to the comprehensive documentation for the MCP Server Code Execution Mode bridge. This documentation is designed to help you understand how the system works from the ground up, even if you're new to container-based code execution or the MCP protocol.

## 📚 Documentation Structure

| Document | Description | Skill Level |
|----------|-------------|-------------|
| [1. Overview](01-overview.md) | What this project does and why it exists | Beginner |
| [2. Core Concepts](02-core-concepts.md) | Key terminology and ideas you need to know | Beginner |
| [3. Architecture](03-architecture.md) | High-level system design and components | Intermediate |
| [4. Execution Flow](04-execution-flow.md) | Step-by-step walkthrough of how code runs | Intermediate |
| [5. The Sandbox Runtime](05-sandbox-runtime.md) | Deep dive into the container and entrypoint | Advanced |
| [6. MCP Proxies & RPC](06-mcp-proxies-and-rpc.md) | How MCP tool calls work across the sandbox boundary | Advanced |
| [7. Server Discovery](07-server-discovery.md) | How MCP servers are found and loaded | Intermediate |
| [8. Creating MCP Servers](08-creating-mcp-servers.md) | Guide to building your own MCP servers | Intermediate |
| [9. Security Model](09-security-model.md) | Container isolation and security features | Intermediate |
| [10. Configuration](10-configuration.md) | Environment variables and settings | Beginner |

## 🎯 Quick Start Reading Path

**If you're completely new:**
1. Start with [Overview](01-overview.md)
2. Read [Core Concepts](02-core-concepts.md)
3. Skim [Architecture](03-architecture.md)

**If you want to understand how code executes:**
1. Read [Execution Flow](04-execution-flow.md) 
2. Then [Sandbox Runtime](05-sandbox-runtime.md)
3. Then [MCP Proxies & RPC](06-mcp-proxies-and-rpc.md)

**If you want to add new capabilities:**
1. Read [Server Discovery](07-server-discovery.md)
2. Then [Creating MCP Servers](08-creating-mcp-servers.md)

## 🔑 Key Insight

The central idea of this project is:

> **Instead of exposing 100 MCP tools to an LLM (which costs thousands of tokens), expose ONE tool (`run_python`) that lets the LLM write Python code to discover and call tools on-demand.**

This dramatically reduces token usage while giving the LLM more flexibility through code.

## 📁 Project Structure

```
mcp-server-code-execution-mode/
├── main.py                              # Entry point
├── mcp_server_code_execution_mode.py    # Core implementation (~2800 lines)
├── docs/                                # This documentation folder
├── servers/                             # Example MCP servers
│   ├── _template.py                     # Template for new servers
│   ├── weather.py                       # Weather API server
│   ├── soccer.py                        # Soccer/football API server
│   └── schemas.py                       # Pydantic output schemas
└── tests/                               # Test suite
```

## 🆘 Getting Help

If something in this documentation is unclear:
1. Check the existing [GUIDE.md](../GUIDE.md) for installation/configuration help
2. Look at the [ARCHITECTURE.md](../ARCHITECTURE.md) for technical details
3. Review the source code comments in `mcp_server_code_execution_mode.py`
