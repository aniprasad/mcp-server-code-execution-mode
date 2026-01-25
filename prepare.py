#!/usr/bin/env python3
"""
Prepare the MCP Server Code Execution Mode environment.

This script:
1. Creates ~/MCPs directory structure
2. Copies example server configs if not present
3. Generates API documentation (mcp-tools.md)

Usage:
    uv run python prepare.py
"""

import argparse
import json
import shutil
import sys
from pathlib import Path


def get_mcps_dir() -> Path:
    """Get the MCPs directory path."""
    import os
    state_dir = os.environ.get("MCP_BRIDGE_STATE_DIR")
    if state_dir:
        return Path(state_dir).expanduser().resolve()
    return Path.home() / "MCPs"


def create_directory_structure(mcps_dir: Path, verbose: bool = True) -> None:
    """Create the MCPs directory structure."""
    directories = [
        mcps_dir,
        mcps_dir / "user_tools",
        mcps_dir / "user_tools" / "memory",
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        if verbose:
            print(f"✓ Created: {directory}")


def copy_example_configs(mcps_dir: Path, force: bool = False, verbose: bool = True) -> None:
    """Copy example server configs to ~/MCPs if they don't exist."""
    script_dir = Path(__file__).parent
    servers_dir = script_dir / "servers"
    
    # Check if mcp-servers.json exists in servers/
    source_config = servers_dir / "mcp-servers.json"
    if not source_config.exists():
        if verbose:
            print(f"⚠ No example config found at {source_config}")
        return
    
    dest_config = mcps_dir / "mcp-servers.json"
    
    if dest_config.exists() and not force:
        if verbose:
            print(f"⏭ Skipped: {dest_config} (already exists, use --force to overwrite)")
        return
    
    # Read and update paths in the config
    with open(source_config, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    # Update paths to point to the actual server locations
    if "mcpServers" in config:
        for server_name, server_config in config["mcpServers"].items():
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
        print(f"✓ Created: {dest_config}")


def generate_api_docs(verbose: bool = True) -> bool:
    """Generate mcp-tools.md by running generate_api_docs.py."""
    script_dir = Path(__file__).parent
    gen_script = script_dir / "generate_api_docs.py"
    
    if not gen_script.exists():
        if verbose:
            print(f"⚠ generate_api_docs.py not found at {gen_script}")
        return False
    
    if verbose:
        print("\n📝 Generating API documentation...")
    
    import subprocess
    result = subprocess.run(
        [sys.executable, str(gen_script)],
        cwd=str(script_dir),
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        if verbose:
            print("✓ API documentation generated successfully")
            # Print summary from output
            for line in result.stdout.split("\n"):
                if line.strip() and not line.startswith("2"):  # Skip log lines
                    print(f"  {line}")
        return True
    else:
        if verbose:
            print(f"✗ Failed to generate API docs: {result.stderr}")
        return False


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
        "--skip-docs",
        action="store_true",
        help="Skip API documentation generation"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress output"
    )
    
    args = parser.parse_args()
    verbose = not args.quiet
    
    mcps_dir = get_mcps_dir()
    
    if verbose:
        print(f"\n🚀 Preparing MCP Server Code Execution Mode")
        print(f"   Target directory: {mcps_dir}\n")
    
    # Step 1: Create directory structure
    if verbose:
        print("📁 Creating directory structure...")
    create_directory_structure(mcps_dir, verbose=verbose)
    
    # Step 2: Copy example configs
    if verbose:
        print("\n📋 Setting up server configurations...")
    copy_example_configs(mcps_dir, force=args.force, verbose=verbose)
    
    # Step 3: Generate API docs
    if not args.skip_docs:
        generate_api_docs(verbose=verbose)
    
    if verbose:
        print(f"\n✅ Setup complete!")
        print(f"\n📖 Next steps:")
        print(f"   1. Review/edit server configs in {mcps_dir}")
        print(f"   2. Run: uv run python mcp_server_code_execution_mode.py")
        print(f"   3. Or use VS Code: @python-sandbox in Copilot Chat")


if __name__ == "__main__":
    main()
