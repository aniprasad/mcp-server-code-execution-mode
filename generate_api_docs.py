#!/usr/bin/env python3
"""
Generate MCP API Documentation

Connects to all configured MCP servers, lists their tools, and generates
human-readable API documentation for the agent.

Usage:
    python generate_api_docs.py

The docs are saved to docs/sandbox-api.md in the workspace.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from mcp_server_code_execution_mode import (
    MCPBridge,
    PersistentMCPClient,
    CONFIG_SOURCES,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _extract_output_schema_compact(description: str, tool_name: str = "") -> str:
    """Extract output schema from description and format compactly."""
    lines = description.split("\n")
    
    # First, check for explicit "Returns:" line in description (preferred)
    returns_line = ""
    for line in lines:
        line_stripped = line.strip()
        if line_stripped.startswith("Returns:"):
            # Extract the schema from "Returns: {field1, field2, ...}"
            returns_line = line_stripped[len("Returns:"):].strip()
            break
    
    if not returns_line:
        # Fall back to extracting from "Fields:" sections
        if "Fields:" not in description:
            return ""
        
        fields = []
        in_fields = False
        for line in lines:
            line = line.strip()
            if line.startswith("Fields:"):
                in_fields = True
                continue
            if in_fields:
                if line.startswith("- "):
                    match = line[2:].split(" ")[0].strip()
                    if match:
                        fields.append(match)
                elif line.startswith("Each ") or line == "" or not line.startswith("-"):
                    if fields:
                        break
        
        if fields:
            return "{" + ", ".join(fields) + "}"
        return ""
    
    # Check if there's a nested "Each entry" section and expand [...] to show item fields
    if "[...]" in returns_line or "prices:" in returns_line or "results:" in returns_line:
        # Look for "Each entry in X array:" followed by Fields:
        for i, line in enumerate(lines):
            if line.strip().startswith("Each ") and "array" in line.lower():
                # Find the Fields: section after this
                for j in range(i + 1, min(i + 20, len(lines))):
                    if "Fields:" in lines[j]:
                        # Extract field names from the Fields section
                        item_fields = []
                        for k in range(j + 1, min(j + 15, len(lines))):
                            field_line = lines[k].strip()
                            if field_line.startswith("- "):
                                field_name = field_line[2:].split(" ")[0].strip()
                                if field_name:
                                    item_fields.append(field_name)
                            elif field_line == "" or (not field_line.startswith("-") and not field_line.startswith(" ")):
                                break
                        
                        if item_fields:
                            # Replace [...] with actual field list
                            item_schema = "{" + ", ".join(item_fields) + "}"
                            returns_line = returns_line.replace("[...]", f"[{item_schema}, ...]")
                        break
                break
    
    return returns_line


def _generate_sandbox_helpers_markdown() -> str:
    """Generate standalone sandbox helpers documentation."""
    lines = [
        "# Sandbox Helpers Reference",
        "",
        "Built-in functions available in the sandbox (no import needed).",
        "",
        "---",
        "",
        "## render_chart(data, chart_type, x, y, ...)",
        "Render a chart using seaborn. See `.mcp/docs/viz-guidelines.md` for usage rules.",
        "- **data** (list|DataFrame, required): Data to plot",
        "- **chart_type** (str, required): `'bar'`, `'line'`, or `'scatter'`",
        "- **x** (str, required): Field name for X axis",
        "- **y** (str, required): Field name for Y axis",
        "- **title** (str, optional): Chart title",
        "- **series** (str, optional): Field for grouping (colored lines/bars). Alias: `hue`",
        "- **filename** (str, optional): Output filename (default: 'chart.png')",
        "- **Returns**: `file://` URL (auto-printed)",
        "",
        "---",
        "",
        "## save_file(filename, content, subdir='data')",
        "Save text or bytes to the execution folder.",
        "- **filename** (str, required): Output filename (e.g., 'results.csv')",
        "- **content** (str|bytes, required): Content to save",
        "- **subdir** (str, optional): Subdirectory ('data', 'images', or '')",
        "- **Returns**: `file://` URL",
        "",
        "## save_image(filename, figure_or_bytes)",
        "Save an image. For charts, use `render_chart()` instead.",
        "- **filename** (str, required): Output filename",
        "- **figure_or_bytes** (required): matplotlib Figure, PIL Image, or bytes",
        "- **Returns**: `file://` URL",
        "",
        "## list_execution_files()",
        "List all files saved in current execution.",
        "- **Returns**: `{images: [...], data: [...], other: [...]}`",
        "",
        "## execution_folder()",
        "Get Path to current execution folder.",
        "- **Returns**: `Path` object",
        "",
        "---",
        "",
        "## save_memory(key, value, metadata=None)",
        "Save data that persists across sessions.",
        "- **key** (str, required): Identifier (e.g., 'project_context')",
        "- **value** (required): Any JSON-serializable data",
        "- **metadata** (dict, optional): Extra info like `{'tags': ['important']}`",
        "",
        "## load_memory(key, default=None)",
        "Load previously saved data.",
        "- **key** (str, required): The memory identifier",
        "- **default** (optional): Value if not found",
        "- **Returns**: The stored value or default",
        "",
        "## list_memories()",
        "List all saved memory keys with metadata.",
        "- **Returns**: `[{key, metadata, created_at, updated_at}, ...]`",
        "",
        "## update_memory(key, updater)",
        "Update memory using a function.",
        "- **key** (str, required): Memory key",
        "- **updater** (callable, required): Function like `lambda x: x + ['new']`",
        "",
        "## delete_memory(key) / memory_exists(key) / get_memory_info(key)",
        "Delete, check existence, or get full info for a memory entry.",
        "",
        "---",
        "",
        "## save_tool(func)",
        "Save a function to `user_tools.py` for future sessions.",
        "- **func** (callable, required): Function to persist",
        "",
        "```python",
        "def my_helper(x): return x * 2",
        "save_tool(my_helper)  # Available in all future sessions",
        "```",
        "",
    ]
    return "\n".join(lines)


def generate_api_markdown(servers_data: Dict[str, Any], docs_prefix: str = ".mcp/docs") -> str:
    """Generate API index with server links and critical mistakes."""
    lines = [
        "# MCP Servers API Reference",
        "",
        "## Servers",
        "",
    ]
    
    # Build server index with relative links (same folder as API.md)
    # Note: For readFile, agent should use full path like ".mcp/docs/weather.md"
    for server_name, server_info in servers_data.items():
        description = server_info.get("description", "")
        first_sentence = description.split(".")[0] if description else server_name
        lines.append(f"- [{server_name}]({server_name}.md): {first_sentence}")
    
    lines.extend([
        "",
        "---",
        "",
        "## Critical Mistakes",
        "",
        "### 1. Use keyword arguments ONLY",
        "```python",
        "# ✅ CORRECT",
        "await mcp_weather.get_forecast(city='Toronto', days=5)",
        "",
        "# ❌ WRONG - positional args break the proxy",
        "await mcp_weather.get_forecast('Toronto', 5)",
        "```",
        "",
        "### 2. Use `await main()` not `asyncio.run()`",
        "```python",
        "# ✅ CORRECT - sandbox has running event loop",
        "async def main():",
        "    result = await mcp_weather.get_weather(city='Seattle')",
        "    print(result)",
        "",
        "await main()",
        "",
        "# ❌ WRONG - nested event loop error",
        "asyncio.run(main())",
        "```",
        "",
        "### 3. Always print results",
        "```python",
        "# ✅ CORRECT - user sees output",
        "result = await mcp_weather.get_weather(city='Seattle')",
        "print(result)",
        "",
        "# ❌ WRONG - no output shown",
        "result = await mcp_weather.get_weather(city='Seattle')",
        "```",
        "",
        "### 4. Load servers you use",
        "```python",
        "# servers=['weather'] creates mcp_weather proxy",
        "# servers=['stocks'] creates mcp_stocks proxy",
        "```",
        "",
        "### 5. Match parameter names exactly",
        "```python",
        "# ✅ CORRECT - parameter is 'city'",
        "await mcp_weather.get_weather(city='Seattle')",
        "",
        "# ❌ WRONG - 'location' is not valid",
        "await mcp_weather.get_weather(location='Seattle')",
        "```",
    ])
    
    return "\n".join(lines)


def generate_server_markdown(server_name: str, server_info: Dict[str, Any]) -> str:
    """Generate per-server API documentation with numbered tools."""
    description = server_info.get("description", "")
    tools = server_info.get("tools", [])
    error = server_info.get("error")
    
    lines = [
        f"# {server_name}",
        "",
        description.split(".")[0] if description else "",
        f"Load: servers=['{server_name}'] → mcp_{server_name}",
        "",
        "---",
        "",
    ]
    
    if error:
        lines.append(f"Error: {error}")
        return "\n".join(lines)
    
    for idx, tool in enumerate(tools, 1):
        tool_name = tool.get("name", "unknown")
        tool_desc = tool.get("description", "")
        input_schema = tool.get("inputSchema", {})
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        
        # Build signature
        params = []
        for param_name, param_info in properties.items():
            is_required = param_name in required
            default = param_info.get("default")
            if is_required:
                params.append(param_name)
            elif default is not None:
                params.append(f"{param_name}={default}")
            else:
                params.append(f"{param_name}=")
        signature = ", ".join(params)
        
        # First line of description
        first_line = tool_desc.split("\n")[0].strip() if tool_desc else ""
        
        # Numbered tool with signature
        lines.append(f"{idx}. {tool_name}({signature})")
        if first_line:
            lines.append(f"   {first_line}")
        
        # Input params as bullets
        if properties:
            for param_name, param_info in properties.items():
                is_required = param_name in required
                param_desc = param_info.get("description", "")
                req = "req" if is_required else "opt"
                lines.append(f"   - {param_name} ({req}): {param_desc}")
        
        # Output schema as bullet with bold Returns
        output_schema = _extract_output_schema_compact(tool_desc, tool_name)
        if output_schema:
            lines.append(f"   - **Returns**: {output_schema}")
        
        lines.append("")
    
    return "\n".join(lines)


def generate_agent_instructions(servers_data: Dict[str, Any], docs_prefix: str = ".mcp/docs") -> str:
    """Generate agent instructions file with dynamic server list."""
    
    # Build server list for display
    server_names = list(servers_data.keys())
    servers_str = ", ".join(server_names)
    servers_array = ", ".join(f"'{s}'" for s in server_names)
    
    return f'''---
name: Python Sandbox
description: Execute Python code in a secure Podman container with access to MCP servers for {servers_str}, and more.
model: GPT-5.2-Codex (copilot)
tools:
    - "read/readFile"
    - "search/fileSearch"
    - "search/listDirectory"
    - "search/textSearch"
    - "python-sandbox/run_python"
---

You answer questions by writing Python code and executing it via `run_python`. The sandbox runs in a Podman container. Write code when possible—the user expects YOU to take action and do work for them.

**Tool usage:**

- Use **VS Code file tools** (`readFile`, `fileSearch`, `listDirectory`, `textSearch`) to read files in the workspace.
- Use **`run_python`** to execute Python code—either plain Python or code that calls MCP server APIs.

## Plain Python

For tasks that don't need external data (math, string manipulation, algorithms), just run plain Python:

```python
# No servers needed - just omit the servers parameter
print(sum(range(1, 11)))  # Sum of first 10 numbers
```

## MCP Server APIs (for external data)

The sandbox provides MCP server proxies as globals (e.g., `mcp_weather`, `mcp_stocks`). For the full API reference with tool signatures and common mistakes, use `readFile` to read `{docs_prefix}/API.md`.

Additional docs (use `readFile` to read them when relevant):
- `{docs_prefix}/sandbox-helpers.md` — Built-in functions (render_chart, memory, save_file)
- `{docs_prefix}/viz-guidelines.md` — Chart styling (when creating visualizations)

## run_python Tool

- `code` (required): Python code to execute
- `servers` (optional): MCP servers to load, e.g., `[{servers_array}]`. Omit for plain Python.
- `timeout` (optional): Seconds (default 120)

## Core Rules

- **Keyword arguments only** — `await mcp_weather.get_weather(city='Seattle')` NOT `get_weather('Seattle')`
- **Async/await** — Use `await` for every MCP call: `await mcp_<server>.<tool>(...)`
- **Print results** — Always `print()` results so user sees output.
- **No invented values** — All data must come from the user query or API results.
- **Use `render_chart()` for ALL charts** — Never use matplotlib/plt directly.

## Workflow (Per Request)

1. **Identify the task** — Understand user intent.
2. **Plain Python or MCP?** — If external data needed, check `{docs_prefix}/API.md` (via `readFile`) for relevant server tools.
3. **Verify signatures** — Read the per-server docs (e.g., `{docs_prefix}/weather.md`) for parameter details.
4. **Write code** — Use async pattern for MCP calls, plain Python otherwise.
5. **Execute** — Call `run_python` with `servers` list if using MCP, omit otherwise.
6. **Present** — Show results in friendly format.

## Conventions

- **Async wrapper for MCP** — Wrap MCP calls in `async def main(): ... await main()`
- **Truncation** — Truncate verbose output unless the user asks for full details.
- **Pagination** — If many results, show totals + top samples.

```python
# MCP example (needs servers=['weather'])
async def main():
    result = await mcp_weather.get_weather(city='Seattle')
    print(result)

await main()
```
'''


def generate_api_markdown_full(servers_data: Dict[str, Any]) -> str:
    """Generate full API documentation (legacy, kept for reference)."""
    lines = [
        "# MCP Servers API Reference",
        "",
        "## CRITICAL: Common Mistakes",
        "",
        "### 1. Use keyword arguments ONLY",
        "```python",
        "# ✅ CORRECT",
        "await mcp_weather.get_forecast(city='Toronto', days=5)",
        "",
        "# ❌ WRONG - positional args break the proxy",
        "await mcp_weather.get_forecast('Toronto', 5)",
        "```",
        "",
        "### 2. Use `await main()` not `asyncio.run()`",
        "```python",
        "# ✅ CORRECT - sandbox has running event loop",
        "async def main():",
        "    result = await mcp_weather.get_weather(city='Seattle')",
        "    print(result)",
        "",
        "await main()",
        "",
        "# ❌ WRONG - nested event loop error",
        "asyncio.run(main())",
        "```",
        "",
        "### 3. Always print results",
        "```python",
        "# ✅ CORRECT - user sees output",
        "result = await mcp_weather.get_weather(city='Seattle')",
        "print(result)",
        "",
        "# ❌ WRONG - no output shown to user",
        "result = await mcp_weather.get_weather(city='Seattle')",
        "```",
        "",
        "### 4. Load servers you use",
        "```python",
        "# When calling run_python, specify servers=['weather'] or ['sports']",
        "# The mcp_weather and mcp_sports proxies only exist if loaded",
        "```",
        "",
        "### 5. Match parameter names exactly",
        "```python",
        "# ✅ CORRECT - parameter is 'city' not 'location'",
        "await mcp_weather.get_weather(city='Seattle')",
        "",
        "# ❌ WRONG - 'location' is not a valid parameter",
        "await mcp_weather.get_weather(location='Seattle')",
        "```",
        "",
        "---",
        "",
    ]
    
    for server_name, server_info in servers_data.items():
        description = server_info.get("description", "")
        tools = server_info.get("tools", [])
        error = server_info.get("error")
        
        lines.append(f"## {server_name}")
        # Server description on same line or next
        if description:
            # Take first sentence only
            first_sentence = description.split(".")[0] + "." if "." in description else description
            lines.append(f"{first_sentence} Load: `servers=['{server_name}']`")
        else:
            lines.append(f"Load: `servers=['{server_name}']`")
        lines.append("")
        
        if error:
            lines.append(f"⚠️ Error: {error}")
            lines.append("")
            continue
        
        for tool in tools:
            tool_name = tool.get("name", "unknown")
            tool_desc = tool.get("description", "")
            input_schema = tool.get("inputSchema", {})
            properties = input_schema.get("properties", {})
            required = input_schema.get("required", [])
            
            # Build compact signature
            params = []
            for param_name, param_info in properties.items():
                is_required = param_name in required
                if is_required:
                    params.append(param_name)
                else:
                    # Show default if available
                    default = param_info.get("default")
                    if default is not None:
                        params.append(f"{param_name}={default}")
                    else:
                        params.append(f"{param_name}=")
            
            signature = ", ".join(params)
            
            # First line of description only
            first_line = tool_desc.split("\n")[0].strip() if tool_desc else ""
            
            lines.append(f"### {tool_name}({signature})")
            if first_line:
                lines.append(first_line)
            
            # Parameters - compact format, full descriptions
            if properties:
                param_parts = []
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "any")
                    is_required = param_name in required
                    param_desc = param_info.get("description", "")
                    req = "required" if is_required else "optional"
                    param_parts.append(f"- **{param_name}** ({param_type}, {req}): {param_desc}")
                lines.extend(param_parts)
            
            # Output schema - extract and format compactly
            output_schema = _extract_output_schema_compact(tool_desc, tool_name)
            if output_schema:
                lines.append(f"- **Returns**: `{output_schema}`")
            
            lines.append("")
    
    return "\n".join(lines)


async def generate_api_docs(output_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Connect to all configured MCP servers and generate API documentation.
    
    Returns:
        Dict of server data.
    """
    if output_path is None:
        # Default to workspace-relative .mcp/docs/API.md
        script_dir = Path(__file__).parent
        output_path = script_dir / ".mcp" / "docs" / "API.md"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    bridge = MCPBridge()
    
    # Discover all servers
    logger.info("Discovering MCP servers...")
    discovered = await bridge.discover_servers()
    logger.info(f"Found {len(discovered)} servers: {list(discovered.keys())}")
    
    servers_data: Dict[str, Any] = {}
    
    # Connect to each server and list tools
    for server_name, server_description in discovered.items():
        logger.info(f"Connecting to {server_name}...")
        
        try:
            # Load the server
            await bridge.load_server(server_name)
            
            # Get client and list tools
            client = bridge.clients.get(server_name)
            if client:
                tool_specs = await client.list_tools()
                
                tools = []
                for spec in tool_specs:
                    input_schema = spec.get("input_schema") or spec.get("inputSchema") or {}
                    params = list(input_schema.get("properties", {}).keys())
                    
                    tools.append({
                        "name": spec.get("name"),
                        "params": params,
                        "description": spec.get("description", ""),
                        "inputSchema": input_schema,
                    })
                
                servers_data[server_name] = {
                    "description": server_description,
                    "tools": tools,
                }
                
                logger.info(f"  → {len(tools)} tools found")
                
                # Stop the client
                await client.stop()
                del bridge.clients[server_name]
                bridge.loaded_servers.discard(server_name)
            else:
                logger.warning(f"  → Failed to get client for {server_name}")
                servers_data[server_name] = {
                    "description": server_description,
                    "tools": [],
                    "error": "Failed to connect",
                }
                
        except Exception as e:
            logger.error(f"  → Error connecting to {server_name}: {e}")
            servers_data[server_name] = {
                "description": server_description,
                "tools": [],
                "error": str(e),
            }
    
    # Generate API.md (index + critical mistakes)
    api_md = generate_api_markdown(servers_data)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(api_md)
    
    logger.info(f"API docs saved to {output_path}")
    
    # Generate per-server docs (weather.md, sports.md, stocks.md, etc.)
    for server_name, server_info in servers_data.items():
        server_path = output_path.parent / f"{server_name}.md"
        server_md = generate_server_markdown(server_name, server_info)
        with open(server_path, "w", encoding="utf-8") as f:
            f.write(server_md)
        logger.info(f"  → {server_name}.md saved")
    
    # Generate sandbox-helpers.md (built-in functions)
    helpers_path = output_path.parent / "sandbox-helpers.md"
    helpers_md = _generate_sandbox_helpers_markdown()
    with open(helpers_path, "w", encoding="utf-8") as f:
        f.write(helpers_md)
    
    logger.info(f"Sandbox helpers docs saved to {helpers_path}")
    
    # Generate agent instructions file
    script_dir = Path(__file__).parent
    agent_path = script_dir / ".github" / "agents" / "python-sandbox.agent.md"
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    agent_md = generate_agent_instructions(servers_data)
    with open(agent_path, "w", encoding="utf-8") as f:
        f.write(agent_md)
    
    logger.info(f"Agent instructions saved to {agent_path}")
    
    # Print summary
    total_tools = sum(len(s.get("tools", [])) for s in servers_data.values())
    print(f"\n{'=' * 60}")
    print(f"MCP API Documentation Generated")
    print(f"{'=' * 60}")
    print(f"Servers: {len(servers_data)}")
    print(f"Total tools: {total_tools}")
    print(f"Output: {output_path}")
    print(f"Helpers: {helpers_path}")
    print(f"Agent: {agent_path}")
    print(f"{'=' * 60}\n")
    
    for server_name, server_info in servers_data.items():
        tools = server_info.get("tools", [])
        error = server_info.get("error")
        if error:
            print(f"[{server_name}] ERROR: {error}")
        else:
            print(f"[{server_name}] OK - {len(tools)} tools")
            for tool in tools:
                params = ", ".join(tool.get("params", []))
                print(f"  - {tool['name']}({params})")
    
    return servers_data


def main():
    parser = argparse.ArgumentParser(
        description="Generate MCP API documentation for the agent"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Output path for docs (default: docs/sandbox-api.md)"
    )
    
    args = parser.parse_args()
    
    # Run async generator
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(generate_api_docs(args.output))


if __name__ == "__main__":
    main()
