import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the module under test
# We need to add the repo root to sys.path to import the module
sys.path.insert(0, str(Path(__file__).parents[1]))
from mcp_server_code_execution_mode import MCPBridge, MCPServerInfo


@pytest.fixture
def mock_bridge():
    bridge = MCPBridge()
    # Mock the internal caches to avoid side effects
    bridge.servers = {}
    return bridge


def test_discover_servers_vscode_global(mock_bridge, tmp_path):
    """Test discovery of VS Code global settings."""

    # Create a mock settings.json
    settings_content = {
        "mcpServers": {"vscode-global-server": {"command": "echo", "args": ["hello"]}}
    }

    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps(settings_content))

    # Patch the VSCODE_GLOBAL_CONFIG_PATHS to point to our mock file
    with patch(
        "mcp_server_code_execution_mode.VSCODE_GLOBAL_CONFIG_PATHS", [settings_file]
    ):
        # Run discovery
        import asyncio

        asyncio.run(mock_bridge.discover_servers())

        # Verify
        assert "vscode-global-server" in mock_bridge.servers
        server = mock_bridge.servers["vscode-global-server"]
        assert server.command == "echo"
        assert server.args == ["hello"]


def test_discover_servers_antigravity(mock_bridge, tmp_path):
    """Test discovery of Antigravity IDE settings."""

    # Create a mock settings.json
    settings_content = {
        "mcpServers": {
            "antigravity-server": {"command": "python", "args": ["-m", "http.server"]}
        }
    }

    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps(settings_content))

    # Patch the ANTIGRAVITY_CONFIG_PATHS to point to our mock file
    with patch(
        "mcp_server_code_execution_mode.ANTIGRAVITY_CONFIG_PATHS", [settings_file]
    ):
        # Run discovery
        import asyncio

        asyncio.run(mock_bridge.discover_servers())

        # Verify
        assert "antigravity-server" in mock_bridge.servers
        server = mock_bridge.servers["antigravity-server"]
        assert server.command == "python"
        assert server.args == ["-m", "http.server"]


def test_discover_servers_precedence(mock_bridge, tmp_path):
    """Test that earlier discovered servers take precedence."""

    # Mock existing server
    mock_bridge.servers["conflict-server"] = MCPServerInfo(
        name="conflict-server", command="original", args=[], env={}
    )

    # Create a mock config that tries to override it
    settings_content = {
        "mcpServers": {
            "conflict-server": {"command": "override", "args": []},
            "new-server": {"command": "new", "args": []},
        }
    }

    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps(settings_content))

    # Patch ANTIGRAVITY_CONFIG_PATHS
    with patch(
        "mcp_server_code_execution_mode.ANTIGRAVITY_CONFIG_PATHS", [settings_file]
    ):
        import asyncio

        asyncio.run(mock_bridge.discover_servers())

        # Verify original was NOT overridden
        assert mock_bridge.servers["conflict-server"].command == "original"

        # Verify new server WAS added
        assert "new-server" in mock_bridge.servers
