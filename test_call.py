"""Simple test to call the MCP server with run_python."""
import subprocess
import json
import sys

# Start the server as a subprocess
proc = subprocess.Popen(
    [r".venv\Scripts\python.exe", "mcp_server_code_execution_mode.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
    env={
        **__import__('os').environ,
        "MCP_BRIDGE_LOG_LEVEL": "DEBUG",
    },
)

# Send initialize request
init_request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0.1.0"}
    }
}
print(f"Sending: {json.dumps(init_request)}", file=sys.stderr)
proc.stdin.write(json.dumps(init_request) + "\n")
proc.stdin.flush()

# Read response
print("Waiting for initialize response...", file=sys.stderr)
response = proc.stdout.readline()
print(f"Got: {response}", file=sys.stderr)

# Send initialized notification
init_notif = {
    "jsonrpc": "2.0",
    "method": "notifications/initialized"
}
print(f"Sending: {json.dumps(init_notif)}", file=sys.stderr)
proc.stdin.write(json.dumps(init_notif) + "\n")
proc.stdin.flush()

# Send tools/call request with a simple print
call_request = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "run_python",
        "arguments": {"code": "print(42)"}
    }
}
print(f"\nSending run_python request...", file=sys.stderr)
proc.stdin.write(json.dumps(call_request) + "\n")
proc.stdin.flush()

# Read response with timeout
print("Waiting for run_python response (this may take a while for container startup)...", file=sys.stderr)
import threading
import time

def read_stderr():
    while True:
        line = proc.stderr.readline()
        if not line:
            break
        print(f"STDERR: {line.rstrip()}", file=sys.stderr)

stderr_thread = threading.Thread(target=read_stderr, daemon=True)
stderr_thread.start()

# Wait for response
response = proc.stdout.readline()
print(f"\nGot response: {response}", file=sys.stderr)

proc.terminate()
