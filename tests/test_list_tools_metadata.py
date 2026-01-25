import json
import unittest

from mcp_server_code_execution_mode import list_tools as list_tools_handler


class ListToolsMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_python_tool_schema_is_valid(self) -> None:
        """Verify the run_python tool has a valid schema with required fields."""
        tools = await list_tools_handler()
        self.assertEqual(len(tools), 1)
        tool = tools[0]
        self.assertEqual(tool.name, "run_python")
        self.assertIn("code", tool.inputSchema["properties"])
        self.assertIn("servers", tool.inputSchema["properties"])
        self.assertIn("timeout", tool.inputSchema["properties"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
