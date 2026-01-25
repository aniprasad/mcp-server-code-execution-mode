#!/usr/bin/env python3
"""Test that matplotlib + MCP calls work together in one execution."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server_code_execution_mode import MCPBridge


async def main():
    print(f"Using image: {os.environ.get('MCP_BRIDGE_IMAGE', 'default')}")

    bridge = MCPBridge()
    
    # This is the problematic case: matplotlib + MCP call in same execution
    code = '''
import matplotlib.pyplot as plt
import json

# Fetch data via MCP
result = await mcp_weather.get_forecast(city="Chennai", days=7)
print("Got forecast data")

# Parse and visualize
data = json.loads(result['content'][0]['text'])
dates = [d['date'] for d in data['days']]
highs = [d['temp_high'] for d in data['days']]
lows = [d['temp_low'] for d in data['days']]

fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(dates, highs, 'ro-', label='High')
ax.plot(dates, lows, 'bo-', label='Low')
ax.fill_between(dates, lows, highs, alpha=0.3)
ax.set_title('Chennai 7-Day Forecast')
ax.legend()
ax.set_ylabel('Temperature (°C)')
plt.xticks(rotation=45)
plt.tight_layout()

url = save_image("chennai_test.png", fig)
print(f"Chart saved: {url}")
'''

    print("\n" + "=" * 60)
    print("Testing: matplotlib + MCP call in SAME execution")
    print("=" * 60 + "\n")
    
    result = await bridge.execute_code(code, servers=["weather"], timeout=90)
    
    print(f"Success: {result.success}")
    if result.stdout:
        print(f"Stdout:\n{result.stdout}")
    if result.stderr:
        print(f"Stderr:\n{result.stderr}")
    
    if result.success:
        print("\n✅ FIX WORKS! matplotlib + MCP calls work together")
    else:
        print("\n❌ Still failing")


if __name__ == "__main__":
    asyncio.run(main())
