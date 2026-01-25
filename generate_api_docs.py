#!/usr/bin/env python3
"""
Generate MCP API Documentation

Connects to all configured MCP servers, lists their tools, and generates
human-readable API documentation for the agent.

Usage:
    python generate_api_docs.py

The docs are saved to ~/MCPs/mcp-tools.md.
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


def generate_api_markdown(servers_data: Dict[str, Any]) -> str:
    """Generate compact, LLM-friendly API documentation."""
    lines = [
        "# MCP Servers API Reference",
        "",
        "Load servers with `servers=['name']`, call via `await mcp_<server>.<tool>(...)`",
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
        output_path = Path.home() / "MCPs" / "mcp-tools.md"
    
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
    
    # Generate mcp-tools.md (human-readable docs)
    api_md = generate_api_markdown(servers_data)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(api_md)
    
    logger.info(f"API docs saved to {output_path}")
    
    # Print summary
    total_tools = sum(len(s.get("tools", [])) for s in servers_data.values())
    print(f"\n{'=' * 60}")
    print(f"MCP API Documentation Generated")
    print(f"{'=' * 60}")
    print(f"Servers: {len(servers_data)}")
    print(f"Total tools: {total_tools}")
    print(f"Output: {output_path}")
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
        help="Output path for mcp-tools.md (default: ~/MCPs/mcp-tools.md)"
    )
    
    args = parser.parse_args()
    
    # Run async generator
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(generate_api_docs(args.output))


if __name__ == "__main__":
    main()
