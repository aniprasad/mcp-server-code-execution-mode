"""Test subprocess.run in executor."""
import asyncio
import subprocess

async def test_podman():
    print("Running podman info via run_in_executor...")
    loop = asyncio.get_event_loop()
    
    def run_sync():
        print("  Inside run_sync, about to call subprocess.run...")
        result = subprocess.run(
            ["podman", "info", "--format", "{{json .}}"],
            capture_output=True,
            timeout=30,
        )
        print(f"  subprocess.run returned, rc={result.returncode}")
        return result.returncode, result.stdout, result.stderr
    
    try:
        returncode, stdout_bytes, stderr_bytes = await asyncio.wait_for(
            loop.run_in_executor(None, run_sync),
            timeout=35.0
        )
        print(f"Done, returncode={returncode}")
        print(f"stdout length: {len(stdout_bytes)} bytes")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test_podman())
