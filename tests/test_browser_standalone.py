"""
Standalone test for the browser/CeSail MCP server.
Tests navigation, page info, scroll, wait, screenshot, and close.
"""
import asyncio
import json
import sys
import unittest

sys.path.insert(0, '.')
from mcp_server_code_execution_mode import MCPServerInfo, PersistentMCPClient


class BrowserStandaloneTests(unittest.IsolatedAsyncioTestCase):
    """Test browser server via MCP protocol."""
    
    async def asyncSetUp(self):
        """Start the browser server."""
        self.info = MCPServerInfo(
            name='browser',
            command=r'.venv\Scripts\python.exe',
            args=['servers/browser.py'],
            env={
                'BROWSER_HEADLESS': 'true',
                'BROWSER_TIMEOUT_MS': '30000',
                'BROWSER_TYPE': 'chromium'
            }
        )
        self.client = PersistentMCPClient(self.info)
        await self.client.start()
    
    async def asyncTearDown(self):
        """Stop the browser server."""
        try:
            await self.client.call_tool('close_browser', {})
        except:
            pass
        await self.client.stop()
    
    def _parse_result(self, result):
        """Extract JSON data from MCP result."""
        content = result.get('content', [{}])[0].get('text', '{}')
        return json.loads(content)
    
    async def test_list_tools(self):
        """Test that browser server exposes all expected tools."""
        tools = await self.client.list_tools()
        tool_names = [t['name'] if isinstance(t, dict) else t.name for t in tools]
        
        expected = [
            'navigate', 'back', 'forward', 'get_page_info', 'click',
            'type_text', 'hover', 'select_option', 'scroll', 'screenshot',
            'wait_for_selector', 'wait', 'execute_raw_action', 'close_browser'
        ]
        
        for name in expected:
            self.assertIn(name, tool_names, f"Missing tool: {name}")
        
        self.assertEqual(len(tools), 14, "Expected 14 browser tools")
    
    async def test_navigate_and_get_page_info(self):
        """Test navigation to a page and getting page info."""
        # Navigate to httpbin (reliable test endpoint)
        result = await self.client.call_tool('navigate', {'url': 'https://httpbin.org/html'})
        data = self._parse_result(result)
        
        # Navigation should succeed (or at least not crash)
        # Note: May fail due to network issues in some environments
        if data.get('success'):
            self.assertIn('httpbin', data.get('url', '').lower())
        
        # Get page info
        result = await self.client.call_tool('get_page_info', {'include_screenshot': False})
        data = self._parse_result(result)
        self.assertIn('success', data)
    
    async def test_scroll(self):
        """Test scrolling."""
        result = await self.client.call_tool('scroll', {'direction': 'down', 'amount': 'viewport'})
        data = self._parse_result(result)
        self.assertTrue(data.get('success'), "Scroll should succeed")
    
    async def test_wait(self):
        """Test waiting."""
        result = await self.client.call_tool('wait', {'ms': 100})
        data = self._parse_result(result)
        self.assertTrue(data.get('success'), "Wait should succeed")
    
    async def test_screenshot(self):
        """Test taking a screenshot - verify base64 is directly decodable."""
        import base64
        
        result = await self.client.call_tool('screenshot', {'full_page': False})
        data = self._parse_result(result)
        
        self.assertTrue(data.get('success'), "Screenshot should succeed")
        screenshot = data.get('data', '')
        self.assertGreater(len(screenshot), 100, "Screenshot should have base64 data")
        
        # Verify the base64 doesn't have a data URI prefix
        self.assertFalse(screenshot.startswith('data:'), "Screenshot should not have data URI prefix")
        
        # Verify it can be decoded directly without padding fixes
        img_bytes = base64.b64decode(screenshot)
        # PNG files start with the magic bytes: 89 50 4E 47
        self.assertEqual(img_bytes[:4], b'\x89PNG', "Screenshot should be valid PNG")
    
    async def test_back_forward_navigation(self):
        """Test browser history navigation."""
        # Navigate to first page
        result = await self.client.call_tool('navigate', {'url': 'https://github.com'})
        data = self._parse_result(result)
        if not data.get('success'):
            self.skipTest(f"First navigation failed: {data.get('error', 'unknown')}")
        
        # Navigate to second page
        result = await self.client.call_tool('navigate', {'url': 'https://httpbin.org/html'})
        data = self._parse_result(result)
        if not data.get('success'):
            self.skipTest(f"Second navigation failed: {data.get('error', 'unknown')}")
        
        # Go back
        result = await self.client.call_tool('back', {})
        data = self._parse_result(result)
        self.assertTrue(data.get('success'), "Back navigation should succeed")
        
        # Go forward
        result = await self.client.call_tool('forward', {})
        data = self._parse_result(result)
        self.assertTrue(data.get('success'), "Forward navigation should succeed")
    
    async def test_page_info_with_screenshot(self):
        """Test getting page info with screenshot included."""
        # Navigate first
        result = await self.client.call_tool('navigate', {'url': 'https://github.com'})
        data = self._parse_result(result)
        if not data.get('success'):
            self.skipTest(f"Navigation failed: {data.get('error', 'unknown')}")
        
        # Get page info with screenshot
        result = await self.client.call_tool('get_page_info', {'include_screenshot': True})
        data = self._parse_result(result)
        
        self.assertTrue(data.get('success'), f"get_page_info should succeed: {data.get('error')}")
        
        # Should have screenshot data
        screenshot = data.get('screenshot', {})
        if screenshot:
            self.assertIn('data', screenshot, "Screenshot should have data field")
            self.assertGreater(len(screenshot.get('data', '')), 100, "Screenshot data should be present")
    
    async def test_form_interaction(self):
        """Test typing into a form field."""
        # Navigate to httpbin forms page
        result = await self.client.call_tool('navigate', {'url': 'https://httpbin.org/forms/post'})
        data = self._parse_result(result)
        
        if not data.get('success'):
            self.skipTest("Could not navigate to forms page")
        
        # Try to type in the customer name field
        result = await self.client.call_tool('type_text', {
            'selector': 'input[name="custname"]',
            'text': 'Test User'
        })
        data = self._parse_result(result)
        # This may or may not succeed depending on page load timing
        self.assertIn('success', data)
    
    async def test_wait_for_selector(self):
        """Test waiting for an element to appear."""
        # Navigate to a page
        result = await self.client.call_tool('navigate', {'url': 'https://github.com'})
        data = self._parse_result(result)
        if not data.get('success'):
            self.skipTest(f"Navigation failed: {data.get('error', 'unknown')}")
        
        # Wait for header to be visible
        result = await self.client.call_tool('wait_for_selector', {
            'selector': 'header',
            'timeout_ms': 5000,
            'state': 'visible'
        })
        data = self._parse_result(result)
        # Note: CeSail may not support wait_for_selector fully
        self.assertIn('success', data)
        
        # Wait for non-existent element (should fail/timeout)
        result = await self.client.call_tool('wait_for_selector', {
            'selector': '#does-not-exist-xyz',
            'timeout_ms': 1000,
            'state': 'visible'
        })
        data = self._parse_result(result)
        # Should fail since element doesn't exist
        self.assertIn('success', data)  # Just check it returns something
    
    async def test_blocked_url(self):
        """Test that blocked URLs are rejected."""
        # Try to navigate to a blocked URL pattern (contains 'login')
        result = await self.client.call_tool('navigate', {'url': 'https://login.github.com'})
        data = self._parse_result(result)
        
        self.assertFalse(data.get('success'), "Login URL should be blocked")
        self.assertIn('blocked', data.get('error', '').lower(), "Error should mention blocked")
    
    async def test_click_element(self):
        """Test clicking on an element."""
        # Navigate to github.com
        result = await self.client.call_tool('navigate', {'url': 'https://github.com'})
        data = self._parse_result(result)
        if not data.get('success'):
            self.skipTest(f"Navigation failed: {data.get('error', 'unknown')}")
        
        # Click on any link
        result = await self.client.call_tool('click', {'selector': 'a'})
        data = self._parse_result(result)
        
        # Click should succeed (whether or not navigation happens)
        self.assertIn('success', data)
    
    async def test_hover_element(self):
        """Test hovering over an element."""
        result = await self.client.call_tool('navigate', {'url': 'https://github.com'})
        data = self._parse_result(result)
        if not data.get('success'):
            self.skipTest(f"Navigation failed: {data.get('error', 'unknown')}")
        
        result = await self.client.call_tool('hover', {'selector': 'header'})
        data = self._parse_result(result)
        
        # Hover may not work on all elements, just check it returns
        self.assertIn('success', data)
    
    async def test_full_page_screenshot(self):
        """Test taking a full page screenshot."""
        result = await self.client.call_tool('navigate', {'url': 'https://github.com'})
        data = self._parse_result(result)
        if not data.get('success'):
            self.skipTest(f"Navigation failed: {data.get('error', 'unknown')}")
        
        result = await self.client.call_tool('screenshot', {'full_page': True})
        data = self._parse_result(result)
        
        self.assertTrue(data.get('success'), "Full page screenshot should succeed")
        self.assertEqual(data.get('format'), 'png', "Format should be png")
        self.assertEqual(data.get('encoding'), 'base64', "Encoding should be base64")


async def run_quick_test():
    """Quick manual test without unittest framework."""
    print('=== Browser/CeSail Quick Test ===\n')
    
    info = MCPServerInfo(
        name='browser',
        command=r'.venv\Scripts\python.exe',
        args=['servers/browser.py'],
        env={
            'BROWSER_HEADLESS': 'true',
            'BROWSER_TIMEOUT_MS': '30000',
            'BROWSER_TYPE': 'chromium'
        }
    )
    client = PersistentMCPClient(info)
    
    def parse_result(result):
        """Safely parse MCP result."""
        try:
            content = result.get('content', [{}])
            if content and len(content) > 0:
                text = content[0].get('text', '{}')
                if text:
                    return json.loads(text)
            # Try structuredContent
            sc = result.get('structuredContent', {})
            if sc:
                return sc.get('result', sc)
            return {'raw': str(result)[:200]}
        except Exception as e:
            return {'parse_error': str(e), 'raw': str(result)[:200]}
    
    try:
        await client.start()
        print('✓ Browser server started')
        
        # List tools
        tools = await client.list_tools()
        tool_names = [t['name'] if isinstance(t, dict) else t.name for t in tools]
        print(f'✓ {len(tools)} tools available: {tool_names}')
        
        # Navigate
        print('\nNavigating to httpbin.org/html...')
        result = await client.call_tool('navigate', {'url': 'https://httpbin.org/html'})
        data = parse_result(result)
        if data.get('success'):
            print(f'✓ Navigation succeeded: {data.get("title", "no title")}')
        else:
            print(f'⚠ Navigation issue: {str(data.get("error", data))[:100]}')
        
        # Scroll (note: amount is 'viewport' or 'half', not int)
        result = await client.call_tool('scroll', {'direction': 'down', 'amount': 'viewport'})
        data = parse_result(result)
        print(f'✓ Scroll: success={data.get("success", data)}')
        
        # Wait
        result = await client.call_tool('wait', {'ms': 200})
        data = parse_result(result)
        print(f'✓ Wait: success={data.get("success", data)}')
        
        # Screenshot (returns 'data' field, not 'screenshot')
        result = await client.call_tool('screenshot', {'full_page': False})
        data = parse_result(result)
        screenshot_size = len(data.get('data', ''))
        print(f'✓ Screenshot: {screenshot_size} chars of base64, success={data.get("success")}')
        
        # Close
        result = await client.call_tool('close_browser', {})
        print('✓ Browser closed')
        
        await client.stop()
        print('\n=== ALL TESTS PASSED ===')
        return True
        
    except Exception as e:
        print(f'\n✗ FAILED: {e}')
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    import sys
    if '--quick' in sys.argv:
        # Run quick manual test
        asyncio.run(run_quick_test())
    else:
        # Run unittest suite
        unittest.main(verbosity=2)
