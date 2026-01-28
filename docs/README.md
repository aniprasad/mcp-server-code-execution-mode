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
├── mcp_server_code_execution_mode.py    # Core implementation (~3800 lines)
├── prepare.py                           # Setup script (creates .mcp/, generates docs)
├── generate_api_docs.py                 # Generates .mcp/docs/API.md
├── docs/                                # This documentation folder
├── servers/                             # Example MCP servers
│   ├── _template.py                     # Template for new servers
│   ├── weather.py                       # Weather API server (Open-Meteo)
│   ├── sports.py                        # Multi-sport API server (ESPN)
│   ├── stocks.py                        # Stock/crypto API server (Yahoo Finance)
│   ├── fx.py                            # Currency exchange API server (Frankfurter)
│   ├── wikipedia.py                     # Wikipedia API server
│   ├── countries.py                     # Country data API server (REST Countries)
│   ├── openlibrary.py                   # Book search API server (Open Library)
│   ├── hackernews.py                    # Tech news API server (HN Firebase API)
│   ├── msforms.py                       # Microsoft Forms API server
│   ├── browser.py                       # Web automation server (Playwright)
│   ├── schemas.py                       # Pydantic output schemas
│   └── templates/                       # Workflow templates for servers
├── .github/agents/                      # VS Code Copilot agent configuration
│   └── python-sandbox.agent.md          # Agent instructions
└── tests/                               # Test suite
```

## 🤖 Agent Mode

This project supports VS Code Copilot Agent mode via `.github/agents/python-sandbox.agent.md`. The agent:
- Uses Claude Opus 4.5 model
- Has access to `run_python` tool and VS Code file tools
- Reads `.mcp/docs/API.md` for available MCP server APIs

To use: Type `@python-sandbox` in VS Code Copilot Chat. Or choose it in the dropdown in Copilot Chat

## 🆘 Getting Help

If something in this documentation is unclear:
1. Check the existing [GUIDE.md](../GUIDE.md) for installation/configuration help
2. Look at the [ARCHITECTURE.md](../ARCHITECTURE.md) for technical details
3. Review the source code comments in `mcp_server_code_execution_mode.py`
