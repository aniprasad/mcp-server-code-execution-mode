#!/usr/bin/env python3
"""
Test client that simulates what VS Code does with the MCP server.
Starts the server as a subprocess, sends JSON-RPC messages, and checks responses.

Usage:
    python test_mcp_client.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Set up environment like VS Code does
os.environ["MCP_BRIDGE_LOG_LEVEL"] = "DEBUG"
os.environ["MCP_BRIDGE_IMAGE"] = "python-sandbox:latest"
os.environ["MCP_BRIDGE_STATE_DIR"] = str(Path(__file__).parent / ".mcp")
os.environ["PYTHONUNBUFFERED"] = "1"


async def test_mcp_server():
    """Test the MCP server by sending requests and checking responses."""
    
    server_script = Path(__file__).parent / "mcp_server_code_execution_mode.py"
    python_exe = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
    
    if not python_exe.exists():
        python_exe = sys.executable
    
    print(f"🚀 Starting MCP server: {python_exe} {server_script}")
    
    # Start the server as a subprocess
    process = await asyncio.create_subprocess_exec(
        str(python_exe), "-u", str(server_script),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    
    async def read_stderr():
        """Read and print stderr in background."""
        while True:
            line = await process.stderr.readline()
            if not line:
                break
            print(f"  [stderr] {line.decode().rstrip()}", file=sys.stderr)
    
    # Start reading stderr in background
    stderr_task = asyncio.create_task(read_stderr())
    
    try:
        # Give server time to start
        await asyncio.sleep(1)
        
        # Step 1: Send initialize request
        print("\n📤 Sending initialize request...")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        }
        process.stdin.write((json.dumps(init_request) + "\n").encode())
        await process.stdin.drain()
        
        # Read response
        response_line = await asyncio.wait_for(process.stdout.readline(), timeout=30)
        init_response = json.loads(response_line.decode())
        print(f"📥 Initialize response: {json.dumps(init_response, indent=2)[:500]}")
        
        # Step 2: Send initialized notification
        print("\n📤 Sending initialized notification...")
        init_notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        process.stdin.write((json.dumps(init_notif) + "\n").encode())
        await process.stdin.drain()
        
        await asyncio.sleep(0.5)
        
        # Step 3: List tools
        print("\n📤 Sending list_tools request...")
        list_tools = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        process.stdin.write((json.dumps(list_tools) + "\n").encode())
        await process.stdin.drain()
        
        response_line = await asyncio.wait_for(process.stdout.readline(), timeout=30)
        tools_response = json.loads(response_line.decode())
        print(f"📥 List tools response: {json.dumps(tools_response, indent=2)[:500]}")
        
        # Step 4: Call run_python with weather query
        print("\n📤 Sending run_python request (weather query)...")
        call_tool = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "run_python",
                "arguments": {
                    "code": "async def main():\n    result = await mcp_weather.get_weather(city='Seattle')\n    print(result)\n\nawait main()",
                    "servers": ["weather"],
                    "timeout": 60
                }
            }
        }
        process.stdin.write((json.dumps(call_tool) + "\n").encode())
        await process.stdin.drain()
        
        print("⏳ Waiting for response (up to 60s)...")
        
        # Wait for response with timeout
        try:
            response_line = await asyncio.wait_for(process.stdout.readline(), timeout=60)
            if response_line:
                call_response = json.loads(response_line.decode())
                print(f"\n✅ TURN 1 RESPONSE RECEIVED!")
                print(f"📥 Response: {json.dumps(call_response, indent=2)[:600]}...")
            else:
                print("\n❌ EMPTY RESPONSE - stdout closed without data")
                return
        except asyncio.TimeoutError:
            print("\n❌ TIMEOUT - No response after 60 seconds")
            return
        
        # ============================================================
        # TURN 2: Ask about sports
        # ============================================================
        print("\n" + "=" * 60)
        print("TURN 2: Sports query")
        print("=" * 60)
        
        call_tool_2 = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "run_python",
                "arguments": {
                    "code": "async def main():\n    result = await mcp_sports.get_nba_scores()\n    print(result)\n\nawait main()",
                    "servers": ["sports"],
                    "timeout": 60
                }
            }
        }
        print("📤 Sending run_python request (sports query)...")
        process.stdin.write((json.dumps(call_tool_2) + "\n").encode())
        await process.stdin.drain()
        
        print("⏳ Waiting for response...")
        try:
            response_line = await asyncio.wait_for(process.stdout.readline(), timeout=60)
            if response_line:
                call_response = json.loads(response_line.decode())
                print(f"\n✅ TURN 2 RESPONSE RECEIVED!")
                print(f"📥 Response: {json.dumps(call_response, indent=2)[:600]}...")
            else:
                print("\n❌ EMPTY RESPONSE")
                return
        except asyncio.TimeoutError:
            print("\n❌ TIMEOUT on turn 2")
            return
        
        # ============================================================
        # TURN 3: Simple Python code (no MCP servers)
        # ============================================================
        print("\n" + "=" * 60)
        print("TURN 3: Simple Python (no MCP servers)")
        print("=" * 60)
        
        call_tool_3 = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "run_python",
                "arguments": {
                    "code": "import sys\nprint(f'Python version: {sys.version}')\nprint(f'2 + 2 = {2 + 2}')",
                    "timeout": 30
                }
            }
        }
        print("📤 Sending run_python request (simple Python)...")
        process.stdin.write((json.dumps(call_tool_3) + "\n").encode())
        await process.stdin.drain()
        
        print("⏳ Waiting for response...")
        try:
            response_line = await asyncio.wait_for(process.stdout.readline(), timeout=60)
            if response_line:
                call_response = json.loads(response_line.decode())
                print(f"\n✅ TURN 3 RESPONSE RECEIVED!")
                print(f"📥 Response: {json.dumps(call_response, indent=2)[:600]}...")
            else:
                print("\n❌ EMPTY RESPONSE")
                return
        except asyncio.TimeoutError:
            print("\n❌ TIMEOUT on turn 3")
            return
        
        # ============================================================
        # TURN 4: Back to weather (different city)
        # ============================================================
        print("\n" + "=" * 60)
        print("TURN 4: Weather again (different city)")
        print("=" * 60)
        
        call_tool_4 = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "run_python",
                "arguments": {
                    "code": "async def main():\n    result = await mcp_weather.get_weather(city='Tokyo')\n    print(result)\n\nawait main()",
                    "servers": ["weather"],
                    "timeout": 60
                }
            }
        }
        print("📤 Sending run_python request (Tokyo weather)...")
        process.stdin.write((json.dumps(call_tool_4) + "\n").encode())
        await process.stdin.drain()
        
        print("⏳ Waiting for response...")
        try:
            response_line = await asyncio.wait_for(process.stdout.readline(), timeout=60)
            if response_line:
                call_response = json.loads(response_line.decode())
                print(f"\n✅ TURN 4 RESPONSE RECEIVED!")
                print(f"📥 Response: {json.dumps(call_response, indent=2)[:600]}...")
            else:
                print("\n❌ EMPTY RESPONSE")
                return
        except asyncio.TimeoutError:
            print("\n❌ TIMEOUT on turn 4")
            return
        
        # ============================================================
        # TURN 5: Use both servers in one call
        # ============================================================
        print("\n" + "=" * 60)
        print("TURN 5: Both servers in one call")
        print("=" * 60)
        
        call_tool_5 = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "run_python",
                "arguments": {
                    "code": "async def main():\n    weather = await mcp_weather.get_weather(city='New York')\n    sports = await mcp_sports.get_nba_scores()\n    print('Weather:', weather)\n    print('Sports:', sports)\n\nawait main()",
                    "servers": ["weather", "sports"],
                    "timeout": 60
                }
            }
        }
        print("📤 Sending run_python request (both servers)...")
        process.stdin.write((json.dumps(call_tool_5) + "\n").encode())
        await process.stdin.drain()
        
        print("⏳ Waiting for response...")
        try:
            response_line = await asyncio.wait_for(process.stdout.readline(), timeout=60)
            if response_line:
                call_response = json.loads(response_line.decode())
                print(f"\n✅ TURN 5 RESPONSE RECEIVED!")
                print(f"📥 Response: {json.dumps(call_response, indent=2)[:800]}...")
            else:
                print("\n❌ EMPTY RESPONSE")
                return
        except asyncio.TimeoutError:
            print("\n❌ TIMEOUT on turn 5")
            return
        
        print("\n" + "=" * 60)
        print("🎉 ALL 5 TURNS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
        # ============================================================
        # BONUS: Realistic multi-step query combining weather + sports
        # "Which Premier League game cities have temperature < 6°C?"
        # ============================================================
        print("\n" + "=" * 60)
        print("BONUS: Realistic multi-step query")
        print("'Which Premier League game cities have temp < 6°C?'")
        print("=" * 60)
        
        # This simulates what an LLM would do: 
        # 1. Get Premier League fixtures (sports server)
        # 2. Get weather for each city
        # 3. Filter and combine the results
        realistic_code = '''
async def main():
    # Step 1: Get today's Premier League fixtures
    print("Step 1: Getting Premier League fixtures...")
    fixtures = await mcp_sports.get_fixtures(league='premier_league')
    print(f"Fixtures: {fixtures}")
    
    # Step 2: Extract cities and get weather for each
    # (In real usage, we'd parse the fixtures to get actual cities)
    cities = ['London', 'Manchester', 'Liverpool', 'Newcastle', 'Birmingham']
    
    print("\\nStep 2: Getting weather for each city...")
    cold_game_cities = []
    
    for city in cities:
        weather = await mcp_weather.get_weather(city=city)
        temp = weather.get('temp', 0) if isinstance(weather, dict) else 0
        print(f"  {city}: {temp}°C")
        if temp < 6:
            cold_game_cities.append({'city': city, 'temp': temp})
    
    # Step 3: Report results
    print("\\n" + "=" * 50)
    print("RESULT: Cities with temp < 6°C:")
    for item in cold_game_cities:
        print(f"  ⚽ {item['city']}: {item['temp']}°C")
    print("=" * 50)

await main()
'''
        
        call_tool_bonus = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "run_python",
                "arguments": {
                    "code": realistic_code.strip(),
                    "servers": ["weather", "sports"],
                    "timeout": 120
                }
            }
        }
        print("📤 Sending multi-step query...")
        process.stdin.write((json.dumps(call_tool_bonus) + "\n").encode())
        await process.stdin.drain()
        
        print("⏳ Waiting for response (this may take a while - multiple API calls)...")
        try:
            response_line = await asyncio.wait_for(process.stdout.readline(), timeout=120)
            if response_line:
                call_response = json.loads(response_line.decode())
                print(f"\n✅ BONUS RESPONSE RECEIVED!")
                # Extract and pretty-print the actual output
                try:
                    content = call_response.get('result', {}).get('content', [{}])[0].get('text', '')
                    print(f"\n📊 Output:\n{content}")
                except:
                    print(f"📥 Response: {json.dumps(call_response, indent=2)[:1200]}...")
            else:
                print("\n❌ EMPTY RESPONSE")
        except asyncio.TimeoutError:
            print("\n❌ TIMEOUT on bonus query")
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS COMPLETED!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        stderr_task.cancel()
        process.terminate()
        await process.wait()
        print("\n🛑 Server stopped")


if __name__ == "__main__":
    print("=" * 60)
    print("MCP Server Test Client")
    print("=" * 60)
    asyncio.run(test_mcp_server())
