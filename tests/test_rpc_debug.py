#!/usr/bin/env python3
"""Test RPC calls with enhanced debugging."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server_code_execution_mode import MCPBridge


async def main():
    print(f"Using image: {os.environ.get('MCP_BRIDGE_IMAGE', 'default')}")

    bridge = MCPBridge()
    
    # Simple test with ONE MCP call
    code = '''
result = await mcp_weather.get_weather(city="Toronto")
print(f"Toronto weather: {result}")
'''

    print("\n" + "=" * 60)
    print("Test 1: Single MCP call")
    print("=" * 60 + "\n")
    
    result = await bridge.execute_code(code, servers=["weather"], timeout=30)
    
    print(f"Success: {result.success}")
    if result.stdout:
        print(f"Stdout:\n{result.stdout}")
    if result.stderr:
        print(f"Stderr:\n{result.stderr}")

    # Now test with TWO MCP calls
    code2 = '''
toronto = await mcp_weather.get_weather(city="Toronto")
print(f"Toronto: {toronto.get('temp', 'N/A')}°C")

ottawa = await mcp_weather.get_weather(city="Ottawa")
print(f"Ottawa: {ottawa.get('temp', 'N/A')}°C")
'''

    print("\n" + "=" * 60)
    print("Test 2: Two sequential MCP calls")
    print("=" * 60 + "\n")
    
    result2 = await bridge.execute_code(code2, servers=["weather"], timeout=60)
    
    print(f"Success: {result2.success}")
    if result2.stdout:
        print(f"Stdout:\n{result2.stdout}")
    if result2.stderr:
        print(f"Stderr:\n{result2.stderr}")


if __name__ == "__main__":
    asyncio.run(main())
