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


def _extract_output_schema_compact(description: str) -> str:
    """Extract output schema from description and format compactly."""
    # The description often contains "Fields:" sections - extract field names
    if "Fields:" not in description:
        return ""
    
    fields = []
    in_fields = False
    for line in description.split("\n"):
        line = line.strip()
        if line.startswith("Fields:"):
            in_fields = True
            continue
        if in_fields:
            if line.startswith("- "):
                # Extract field name from "- field_name (type): description"
                match = line[2:].split(" ")[0].strip()
                if match:
                    fields.append(match)
            elif line.startswith("Each ") or line == "" or not line.startswith("-"):
                # Stop at nested schemas or empty lines
                if fields:
                    break
    
    if fields:
        return "{" + ", ".join(fields) + "}"
    return ""


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


def generate_api_markdown(servers_data: Dict[str, Any]) -> str:
    """Generate compact, LLM-friendly API documentation for MCP servers only."""
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
        "# When calling run_python, specify servers=['weather'] or ['soccer']",
        "# The mcp_weather and mcp_soccer proxies only exist if loaded",
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
            output_schema = _extract_output_schema_compact(tool_desc)
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
    
    # Generate API.md (MCP servers only)
    api_md = generate_api_markdown(servers_data)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(api_md)
    
    logger.info(f"API docs saved to {output_path}")
    
    # Generate sandbox-helpers.md (built-in functions)
    helpers_path = output_path.parent / "sandbox-helpers.md"
    helpers_md = _generate_sandbox_helpers_markdown()
    with open(helpers_path, "w", encoding="utf-8") as f:
        f.write(helpers_md)
    
    logger.info(f"Sandbox helpers docs saved to {helpers_path}")
    
    # Print summary
    total_tools = sum(len(s.get("tools", [])) for s in servers_data.values())
    print(f"\n{'=' * 60}")
    print(f"MCP API Documentation Generated")
    print(f"{'=' * 60}")
    print(f"Servers: {len(servers_data)}")
    print(f"Total tools: {total_tools}")
    print(f"Output: {output_path}")
    print(f"Helpers: {helpers_path}")
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
