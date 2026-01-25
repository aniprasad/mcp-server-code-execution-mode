#!/usr/bin/env python3
"""Debug test for weather MCP server integration."""

import asyncio
import logging
import sys

# Add parent to path
sys.path.insert(0, ".")

logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test")

from mcp_server_code_execution_mode import bridge

async def main():
    print("Testing weather call...")
    
    # Test WITH servers
    code = """
print("Hello from sandbox!")
print(runtime.discovered_servers())
"""
    
    result = await bridge.execute_code(
        code=code,
        servers=["weather"],  # WITH server
        timeout=30,
    )
    
    print(f"Result stdout: {result.stdout}")
    if result.stderr:
        print(f"Result stderr: {result.stderr}")

def _custom_exception_handler(loop, context):
    """Suppress benign async generator cleanup errors."""
    message = context.get("message", "")
    exception = context.get("exception")
    
    if "error occurred during closing of asynchronous generator" in message:
        asyncgen = context.get("asyncgen")
        if asyncgen and "stdio_client" in str(asyncgen):
            logger.debug("Suppressed benign stdio_client cleanup error")
            return
    
    if exception and "exit cancel scope in a different task" in str(exception):
        logger.debug("Suppressed benign cancel scope cleanup error")
        return
    
    loop.default_exception_handler(context)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.set_exception_handler(_custom_exception_handler)
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
