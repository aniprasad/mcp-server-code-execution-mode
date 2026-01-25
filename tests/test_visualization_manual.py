#!/usr/bin/env python3
"""
Manual test for visualization workflow.

Run with:
    $env:MCP_BRIDGE_IMAGE = "python-sandbox:latest"
    uv run python tests/test_visualization_manual.py

This tests:
1. Custom image with matplotlib pre-installed
2. save_image() returns file:// URL
3. Image file is created in execution folder
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server_code_execution_mode import MCPBridge


async def main():
    # Verify custom image is set
    image = os.environ.get("MCP_BRIDGE_IMAGE", "")
    if not image:
        print("⚠️  MCP_BRIDGE_IMAGE not set. Using default image (matplotlib may not be available)")
        print("   Set with: $env:MCP_BRIDGE_IMAGE = 'python-sandbox:latest'")
    else:
        print(f"✓ Using custom image: {image}")

    bridge = MCPBridge()
    
    # Test code that creates a chart and saves it
    code = '''
import matplotlib.pyplot as plt

# Create a simple chart
fig, ax = plt.subplots()
ax.plot([1, 2, 3, 4, 5], [2, 4, 1, 5, 3], 'b-o', label='Data')
ax.set_xlabel('X axis')
ax.set_ylabel('Y axis')
ax.set_title('Test Chart from Python Sandbox')
ax.legend()

# Save using the sandbox helper
url = save_image("test_chart.png", plt)
print(f"Chart saved to: {url}")

# Also test save_file
csv_data = "x,y\\n1,2\\n2,4\\n3,1\\n4,5\\n5,3"
data_url = save_file("test_data.csv", csv_data)
print(f"Data saved to: {data_url}")

# List what we saved
files = list_execution_files()
print(f"Execution files: {files}")
'''

    print("\n" + "=" * 60)
    print("Running visualization test...")
    print("=" * 60 + "\n")
    
    result = await bridge.execute_code(code, servers=[])
    
    print("\n" + "=" * 60)
    print("Result:")
    print("=" * 60)
    print(f"Success: {result.success}")
    
    if result.stdout:
        print(f"\nStdout:\n{result.stdout}")
    
    if result.stderr:
        print(f"\nStderr:\n{result.stderr}")
    
    # Check if files were created
    state_dir = os.environ.get("MCP_BRIDGE_STATE_DIR", str(Path(__file__).parent.parent / ".mcp"))
    exec_dir = Path(state_dir) / "executions"
    if exec_dir.exists():
        latest_dirs = sorted(exec_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if latest_dirs:
            latest = latest_dirs[0]
            print(f"\nExecution folder: {latest}")
            
            images_dir = latest / "images"
            if images_dir.exists():
                images = list(images_dir.iterdir())
                print(f"Images: {[f.name for f in images]}")
                if images:
                    print(f"✓ Image file exists: {images[0]}")
            
            data_dir = latest / "data"
            if data_dir.exists():
                data_files = list(data_dir.iterdir())
                print(f"Data files: {[f.name for f in data_files]}")
                if data_files:
                    print(f"✓ Data file exists: {data_files[0]}")


if __name__ == "__main__":
    asyncio.run(main())
