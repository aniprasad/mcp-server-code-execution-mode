#!/usr/bin/env python3
"""
MCP Server Template

Copy this file to create a new MCP server.
Replace TODO comments with your implementation.

Usage:
    python my_server.py

Then register in .mcp/mcp-servers.json:
{
  "mcpServers": {
    "my-server": {
      "command": "python",
      "args": ["path/to/my_server.py"],
      "description": "Description of what this server does"
    }
  }
}
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Optional: Import schemas for output validation
# from schemas import MyOutputSchema

# TODO: Change this to your server name
SERVER_NAME = "template"

# Configure logging (writes to stderr, won't interfere with MCP protocol)
logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")
logger = logging.getLogger(SERVER_NAME)

app = Server(SERVER_NAME)


# =============================================================================
# Tool Definitions
# =============================================================================

@app.list_tools()
async def list_tools() -> List[Tool]:
    """Return the list of tools this server provides."""
    return [
        Tool(
            name="example_tool",
            # Include output structure in description for LLM understanding
            description="""TODO: Describe what this tool does.

Returns dict with fields:
  - message (str): A greeting message
  - param1 (str): The input parameter echoed back
  - param2 (int): The numeric parameter""",
            inputSchema={
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "TODO: Describe this parameter",
                    },
                    "param2": {
                        "type": "integer",
                        "description": "TODO: Describe this parameter",
                        "default": 10,
                    },
                },
                "required": ["param1"],
            },
        ),
        # TODO: Add more tools here
    ]


# =============================================================================
# Tool Implementations
# =============================================================================

async def example_tool(param1: str, param2: int = 10) -> Dict[str, Any]:
    """
    TODO: Implement your tool logic here.
    
    This function can:
    - Make HTTP requests (the host has network access)
    - Access files (if needed)
    - Call external APIs
    
    Return a dict that will be JSON-serialized.
    """
    logger.info(f"example_tool called with param1={param1}, param2={param2}")
    
    # TODO: Replace with actual implementation
    return {
        "message": f"Hello from {SERVER_NAME}!",
        "param1": param1,
        "param2": param2,
    }


# =============================================================================
# Tool Dispatcher
# =============================================================================

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Dispatch tool calls to implementations."""
    
    logger.info(f"Tool called: {name} with args: {arguments}")
    
    try:
        if name == "example_tool":
            result = await example_tool(
                param1=arguments.get("param1", ""),
                param2=arguments.get("param2", 10),
            )
        # TODO: Add more tool dispatches here
        # elif name == "another_tool":
        #     result = await another_tool(...)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        # Return result as JSON text
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# =============================================================================
# Entry Point
# =============================================================================

async def main() -> None:
    """Run the MCP server."""
    logger.info(f"Starting {SERVER_NAME} MCP server...")
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
