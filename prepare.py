#!/usr/bin/env python3
"""
Prepare the MCP Server Code Execution Mode environment.

This script:
1. Kills any stale MCP server processes
2. Cleans up stale sandbox containers  
3. Cleans up stale browser processes (Playwright/Chrome headless)
4. Creates .mcp/ directory structure in the workspace
5. Copies example server configs if not present
6. Generates API documentation (docs/sandbox-api.md)

Usage:
    uv run python prepare.py                    # Full prepare
    uv run python prepare.py --cleanup-only     # Just cleanup stale processes
    uv run python prepare.py --clear-executions # Clear saved execution artifacts
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def kill_stale_mcp_processes(verbose: bool = True) -> int:
    """Kill any stale MCP server processes. Returns count of processes killed."""
    killed = 0
    
    if sys.platform == "win32":
        # Windows: Use PowerShell to find and kill processes
        try:
            # First, find matching processes
            result = subprocess.run(
                ["powershell", "-Command", 
                 "Get-Process python* 2>$null | Where-Object { $_.CommandLine -like '*mcp_server*' -or $_.CommandLine -like '*mcp-server*' } | Select-Object -ExpandProperty Id"],
                capture_output=True, text=True, timeout=10
            )
            pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
            
            if pids:
                # Kill them
                subprocess.run(
                    ["powershell", "-Command", f"Stop-Process -Id {','.join(pids)} -Force"],
                    capture_output=True, timeout=10
                )
                killed = len(pids)
        except Exception as e:
            if verbose:
                print(f"[!] Failed to check for stale processes: {e}")
    else:
        # Unix: Use pkill or pgrep
        try:
            result = subprocess.run(
                ["pgrep", "-f", "mcp_server|mcp-server"],
                capture_output=True, text=True, timeout=10
            )
            pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
            
            if pids:
                subprocess.run(["kill", "-9"] + pids, capture_output=True, timeout=10)
                killed = len(pids)
        except FileNotFoundError:
            pass  # pgrep not available
        except Exception as e:
            if verbose:
                print(f"[!] Failed to check for stale processes: {e}")
    
    if killed > 0 and verbose:
        print(f"[x] Killed {killed} stale MCP server process(es)")
    
    return killed


def cleanup_stale_containers(verbose: bool = True) -> int:
    """Clean up stale sandbox containers. Returns count of containers removed."""
    removed = 0
    
    # Try podman first, then docker
    for runtime in ["podman", "docker"]:
        try:
            # List containers matching our naming pattern
            result = subprocess.run(
                [runtime, "ps", "-a", "--format", "{{.Names}}", "--filter", "name=mcp-sandbox-"],
                capture_output=True,
                text=True,
                timeout=10,
                stdin=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                continue
                
            containers = [c.strip() for c in result.stdout.strip().split("\n") if c.strip()]
            if not containers:
                continue
            
            # Force remove them
            subprocess.run(
                [runtime, "rm", "-f"] + containers,
                capture_output=True,
                timeout=15,
                stdin=subprocess.DEVNULL,
            )
            removed = len(containers)
            
            if verbose and removed > 0:
                print(f"[~] Cleaned up {removed} stale sandbox container(s)")
            break
            
        except subprocess.TimeoutExpired:
            if verbose:
                print(f"[!] {runtime} cleanup timed out")
            continue
        except FileNotFoundError:
            continue  # Runtime not installed
        except Exception:
            continue
    
    return removed


def cleanup_browser_processes(verbose: bool = True) -> int:
    """Clean up stale browser processes (Playwright/Chrome headless). Returns count killed."""
    killed = 0
    
    # Browser process names to clean up (from Playwright/CeSail)
    browser_patterns = ["chrome-headless-shell", "chromium", "firefox", "webkit"]
    
    if sys.platform == "win32":
        for pattern in browser_patterns:
            try:
                # Find processes matching pattern
                result = subprocess.run(
                    ["powershell", "-Command", 
                     f"Get-Process -Name '{pattern}*' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
                    capture_output=True, text=True, timeout=5
                )
                pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
                
                if pids:
                    subprocess.run(
                        ["powershell", "-Command", f"Stop-Process -Id {','.join(pids)} -Force -ErrorAction SilentlyContinue"],
                        capture_output=True, timeout=5
                    )
                    killed += len(pids)
            except Exception:
                pass
    else:
        # Unix: Use pkill
        for pattern in browser_patterns:
            try:
                result = subprocess.run(
                    ["pgrep", "-f", pattern],
                    capture_output=True, text=True, timeout=5
                )
                pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
                
                if pids:
                    subprocess.run(["kill", "-9"] + pids, capture_output=True, timeout=5)
                    killed += len(pids)
            except Exception:
                pass
    
    if killed > 0 and verbose:
        print(f"[~] Cleaned up {killed} stale browser process(es)")
    
    return killed


def get_mcps_dir() -> Path:
    """Get the .mcp directory path (workspace-relative)."""
    import os
    state_dir = os.environ.get("MCP_BRIDGE_STATE_DIR")
    if state_dir:
        return Path(state_dir).expanduser().resolve()
    # Default to workspace-relative .mcp/ directory
    script_dir = Path(__file__).parent.resolve()
    return script_dir / ".mcp"


def create_directory_structure(mcps_dir: Path, verbose: bool = True) -> None:
    """Create the MCPs directory structure."""
    directories = [
        mcps_dir,
        mcps_dir / "memory",           # Persistent memory (save_memory/load_memory)
        mcps_dir / "executions",       # Per-execution artifacts (LRU, max 50)
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        if verbose:
            print(f"[+] Created: {directory}")
    
    # Create user_tools.py at root (separate from memory data)
    # Write header if file doesn't exist OR is empty (0 bytes)
    user_tools_file = mcps_dir / "user_tools.py"
    if not user_tools_file.exists() or user_tools_file.stat().st_size == 0:
        user_tools_file.write_text("# User-defined tools saved via save_tool()\n# This file is auto-loaded at sandbox startup\n")
        if verbose:
            print(f"[+] Created: {user_tools_file}")


def copy_example_configs(mcps_dir: Path, force: bool = False, verbose: bool = True) -> None:
    """Copy example server configs to .mcp/ if they don't exist."""
    script_dir = Path(__file__).parent
    servers_dir = script_dir / "servers"
    
    # Check if mcp-servers.json exists in servers/
    source_config = servers_dir / "mcp-servers.json"
    if not source_config.exists():
        if verbose:
            print(f"[!] No example config found at {source_config}")
        return
    
    dest_config = mcps_dir / "mcp-servers.json"
    
    if dest_config.exists() and not force:
        if verbose:
            print(f"[-] Skipped: {dest_config} (already exists, use --force to overwrite)")
        return
    
    # Read and update paths in the config
    with open(source_config, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    # Update paths to point to the actual server locations
    if "mcpServers" in config:
        for server_name, server_config in config["mcpServers"].items():
            # Update command to absolute path if it's a relative .venv path
            if "command" in server_config:
                cmd = server_config["command"]
                if ".venv" in cmd and not Path(cmd).is_absolute():
                    # Resolve relative to script directory
                    cmd_path = script_dir / cmd.replace("/", os.sep)
                    if cmd_path.exists():
                        server_config["command"] = str(cmd_path.resolve())

            if "args" in server_config:
                # Update relative paths to absolute paths
                new_args = []
                for arg in server_config["args"]:
                    if arg.endswith(".py"):
                        # Check if it's a relative path to servers/
                        server_file = servers_dir / Path(arg).name
                        if server_file.exists():
                            new_args.append(str(server_file.resolve()))
                        else:
                            new_args.append(arg)
                    else:
                        new_args.append(arg)
                server_config["args"] = new_args
    
    with open(dest_config, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    if verbose:
        print(f"[+] Created: {dest_config}")


def generate_api_docs(verbose: bool = True) -> bool:
    """Generate mcp-tools.md by running generate_api_docs.py."""
    script_dir = Path(__file__).parent
    gen_script = script_dir / "generate_api_docs.py"
    
    if not gen_script.exists():
        if verbose:
            print(f"[!] generate_api_docs.py not found at {gen_script}")
        return False
    
    if verbose:
        print("\n[*] Generating API documentation...")
    
    import subprocess
    result = subprocess.run(
        [sys.executable, str(gen_script)],
        cwd=str(script_dir),
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        if verbose:
            print("[+] API documentation generated successfully")
            # Print summary from output
            for line in result.stdout.split("\n"):
                if line.strip() and not line.startswith("2"):  # Skip log lines
                    print(f"  {line}")
        return True
    else:
        if verbose:
            print(f"[X] Failed to generate API docs: {result.stderr}")
        return False


def generate_viz_guidelines(mcps_dir: Path, verbose: bool = True) -> None:
    """Generate viz-guidelines.md with visualization best practices."""
    content = """\
# Visualization Guidelines

`render_chart()` handles ALL common charts including multi-series comparisons.

## Rules

1. **Always use `render_chart()`** — Handles bar, line, scatter, multi-series, comparisons
2. **Never use matplotlib/plt** — `plt.show()` does nothing (headless sandbox)
3. **Use `series` for comparisons** — Comparing cities? Use `series='city'`

## Multi-Series Pattern (e.g., comparing cities)

```python
# Comparing Chennai vs Toronto temperatures
chart_data = []
for day in chennai['days']:
    chart_data.append({'date': day['date'], 'temp': day['temp_high'], 'city': 'Chennai'})
for day in toronto['days']:
    chart_data.append({'date': day['date'], 'temp': day['temp_high'], 'city': 'Toronto'})

render_chart(chart_data, 'line', x='date', y='temp', series='city', title='Temperature Comparison')
```

## Simple Pattern

```python
data = [{'day': 'Mon', 'sales': 100}, {'day': 'Tue', 'sales': 150}]
render_chart(data, 'bar', x='day', y='sales', title='Daily Sales')
```

## Common Mistakes

```python
# ❌ WRONG - matplotlib doesn't work in sandbox
import matplotlib.pyplot as plt
plt.plot(...)
plt.show()  # Does nothing! Causes timeout.

# ✅ CORRECT - render_chart handles everything
render_chart(data, 'line', x='date', y='value', series='category')
```
"""
    
    viz_file = mcps_dir / "docs" / "viz-guidelines.md"
    viz_file.parent.mkdir(parents=True, exist_ok=True)
    viz_file.write_text(content, encoding="utf-8")
    if verbose:
        print(f"[+] Created: {viz_file}")


def copy_templates(mcps_dir: Path, verbose: bool = True) -> None:
    """Copy code templates from servers/templates/ to .mcp/templates/."""
    source_dir = Path(__file__).parent / "servers" / "templates"
    target_dir = mcps_dir / "templates"
    
    if not source_dir.exists():
        if verbose:
            print(f"[-] No templates found in {source_dir}")
        return
    
    target_dir.mkdir(parents=True, exist_ok=True)
    
    copied = 0
    for template_file in source_dir.glob("*.md"):
        target_file = target_dir / template_file.name
        shutil.copy2(template_file, target_file)
        copied += 1
        if verbose:
            print(f"[+] Copied: {target_file}")
    
    if verbose and copied > 0:
        print(f"  ({copied} template(s) copied to {target_dir})")


def main():
    parser = argparse.ArgumentParser(
        description="Prepare the MCP Server Code Execution Mode environment"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing config files"
    )
    parser.add_argument(
        "--clear-executions",
        action="store_true",
        help="Clear the executions folder (removes all saved execution artifacts)"
    )
    parser.add_argument(
        "--skip-docs",
        action="store_true",
        help="Skip API documentation generation"
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Skip killing stale processes and containers"
    )
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Only run cleanup (kill stale processes, containers, browsers) then exit"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress output"
    )
    
    args = parser.parse_args()
    verbose = not args.quiet
    
    mcps_dir = get_mcps_dir()
    
    # Handle --cleanup-only mode
    if args.cleanup_only:
        if verbose:
            print("[~] Running cleanup only...")
        mcp_killed = kill_stale_mcp_processes(verbose=verbose)
        containers_removed = cleanup_stale_containers(verbose=verbose)
        browsers_killed = cleanup_browser_processes(verbose=verbose)
        total = mcp_killed + containers_removed + browsers_killed
        if verbose:
            if total == 0:
                print("[*] Nothing to clean up")
            else:
                print("[+] Cleanup complete")
        return
    
    if verbose:
        print(f"\n[*] Preparing MCP Server Code Execution Mode")
        print(f"    Target directory: {mcps_dir}\n")
    
    # Step 0a: Kill stale MCP server processes
    if not args.skip_cleanup:
        if verbose:
            print("[?] Checking for stale processes...")
        kill_stale_mcp_processes(verbose=verbose)
        cleanup_stale_containers(verbose=verbose)
        cleanup_browser_processes(verbose=verbose)
    
    # Step 0b: Clear executions if requested
    if args.clear_executions:
        executions_dir = mcps_dir / "executions"
        if executions_dir.exists():
            shutil.rmtree(executions_dir)
            if verbose:
                print(f"[~] Cleared: {executions_dir}")
        executions_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Create directory structure
    if verbose:
        print("[*] Creating directory structure...")
    create_directory_structure(mcps_dir, verbose=verbose)
    
    # Step 2: Copy example configs
    if verbose:
        print("\n[*] Setting up server configurations...")
    copy_example_configs(mcps_dir, force=args.force, verbose=verbose)
    
    # Step 3: Generate API docs
    if not args.skip_docs:
        generate_api_docs(verbose=verbose)
    
    # Step 4: Generate visualization guidelines
    if verbose:
        print("\n[*] Generating visualization guidelines...")
    generate_viz_guidelines(mcps_dir, verbose=verbose)
    
    # Step 5: Copy code templates
    if verbose:
        print("\n[*] Copying code templates...")
    copy_templates(mcps_dir, verbose=verbose)
    
    if verbose:
        print(f"\n[+] Setup complete!")
        print(f"\n[*] Next steps:")
        print(f"    1. Review/edit server configs in {mcps_dir}")
        print(f"    2. Run: uv run python mcp_server_code_execution_mode.py")
        print(f"    3. Or use VS Code: @python-sandbox in Copilot Chat")


if __name__ == "__main__":
    main()
