"""Test asyncio subprocess with podman."""
import asyncio
import subprocess as aio_subprocess

async def test_podman():
    print("Creating subprocess for 'podman info --format {{json .}}'...")
    process = await asyncio.create_subprocess_exec(
        "podman",
        "info",
        "--format",
        "{{json .}}",
        stdout=aio_subprocess.PIPE,
        stderr=aio_subprocess.PIPE,
    )
    print(f"Process created with PID {process.pid}, calling communicate()...")
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=10.0
        )
        print(f"communicate() done, returncode={process.returncode}")
        print(f"stdout length: {len(stdout_bytes)} bytes")
        print(f"stderr: {stderr_bytes.decode()[:200] if stderr_bytes else 'empty'}")
    except asyncio.TimeoutError:
        print("TIMEOUT! communicate() hung for 10 seconds")
        process.kill()

asyncio.run(test_podman())
