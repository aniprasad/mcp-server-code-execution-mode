#!/usr/bin/env python3
"""
Browser Automation MCP Server

Provides web automation capabilities using CeSail/Playwright.
Runs on the HOST (not in sandbox) - sandbox code makes RPC calls to this server.

Environment Variables:
    BROWSER_HEADLESS: Run browser in headless mode (default: "true")
    BROWSER_TIMEOUT_MS: Default timeout for operations (default: "30000")
    BROWSER_TYPE: Browser type - chromium, firefox, webkit (default: "chromium")
    BROWSER_BLOCKED_PATTERNS: Comma-separated URL patterns to block (default: see BLOCKED_PATTERNS)

This **heavily** leverages Akila Jayawardane's tool here https://github.com/AkilaJay/CeSail/tree/main/cesail.
The idea was to use this as a tool and see if the LLM is able to reason about web pages effectively.
One of the core advantages of CeSail (atleast from my opinion) is its ability to properly analyze in a structured output format - which sort of plays well
with the overall design of this solution.
    
Usage in sandbox:
    page = await mcp_browser.navigate(url="https://example.com")
    info = await mcp_browser.get_page_info()
    await mcp_browser.click(selector="#login-button")
    await mcp_browser.type_text(selector="#email", text="user@example.com")
    screenshot = await mcp_browser.screenshot()
"""

import asyncio
import base64
import json
import logging
import os
from typing import Annotated, Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

# Schema imports
try:
    from schemas import (
        BrowserAction,
        BrowserScreenshot,
        BrowserPageInfo,
        BrowserNavigateResult,
        BrowserActionResult,
        BrowserScreenshotResult,
    )
except ImportError:
    from .schemas import (
        BrowserAction,
        BrowserScreenshot,
        BrowserPageInfo,
        BrowserNavigateResult,
        BrowserActionResult,
        BrowserScreenshotResult,
    )

# CeSail imports - suppress SimpleAgent warning that corrupts MCP stdio
import warnings
try:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="SimpleAgent subpackage not available")
        from cesail import DOMParser, Action, ActionType
    HAS_CESAIL = True
except ImportError:
    HAS_CESAIL = False
    DOMParser = None
    Action = None
    ActionType = None

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")
logger = logging.getLogger("browser")

# =============================================================================
# Configuration (from environment, set via mcp-servers.json)
# =============================================================================

HEADLESS = os.environ.get("BROWSER_HEADLESS", "true").lower() == "true"
TIMEOUT_MS = int(os.environ.get("BROWSER_TIMEOUT_MS", "30000"))
BROWSER_TYPE = os.environ.get("BROWSER_TYPE", "chromium")

# Security: URL blocklist
DEFAULT_BLOCKED_PATTERNS = [
    # Financial
    "bank", "paypal", "chase", "wellsfargo", "citibank", "bankofamerica",
    # Authentication
    "login", "signin", "signup", "oauth", "auth", "password", "credential",
    # Admin/Internal
    "admin", "dashboard", "internal", "intranet",
    # Local/Private networks
    "localhost", "127.0.0.1", "192.168.", "10.0.", "172.16.",
    # Sensitive services
    "aws.amazon.com/console", "console.cloud.google", "portal.azure",
]

_blocked_env = os.environ.get("BROWSER_BLOCKED_PATTERNS", "")
if _blocked_env:
    BLOCKED_PATTERNS = [p.strip() for p in _blocked_env.split(",") if p.strip()]
else:
    BLOCKED_PATTERNS = DEFAULT_BLOCKED_PATTERNS

# =============================================================================
# Initialize MCP Server
# =============================================================================

mcp = FastMCP("browser")

# =============================================================================
# Singleton Browser Session
# =============================================================================

_parser: Optional[Any] = None  # CeSail DOMParser instance


async def get_parser() -> Any:
    """Get or create the singleton DOMParser instance."""
    global _parser
    
    if not HAS_CESAIL:
        raise RuntimeError(
            "CeSail is not installed. Run: pip install cesail && playwright install chromium"
        )
    
    if _parser is None:
        logger.info(f"Starting browser (headless={HEADLESS}, type={BROWSER_TYPE})")
        _parser = DOMParser(
            headless=HEADLESS,
            browser_type=BROWSER_TYPE,
        )
        await _parser.__aenter__()
        logger.info("Browser started successfully")
    
    return _parser


async def close_parser():
    """Close the browser session."""
    global _parser
    if _parser is not None:
        await _parser.__aexit__(None, None, None)
        _parser = None
        logger.info("Browser closed")


# =============================================================================
# Security Helpers
# =============================================================================

def is_url_allowed(url: str) -> bool:
    """Check if URL is allowed based on blocklist."""
    url_lower = url.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in url_lower:
            logger.warning(f"URL blocked by pattern '{pattern}': {url}")
            return False
    return True


# =============================================================================
# Tools - Navigation
# =============================================================================

@mcp.tool()
async def navigate(
    url: Annotated[str, Field(description="URL to navigate to (e.g., 'https://example.com')")]
) -> Dict[str, Any]:
    """Navigate to a URL and return page title and URL after navigation."""
    if not is_url_allowed(url):
        return {"success": False, "error": f"URL blocked by security policy: {url}"}
    
    try:
        parser = await get_parser()
        
        action = Action(
            type=ActionType.NAVIGATE,
            metadata={"url": url}
        )
        result = await parser.execute_action(action, wait_for_idle=True)
        
        if not result.get("success", False):
            return BrowserNavigateResult(
                success=False,
                url=url,
                title="",
                error=result.get("error", "Navigation failed")
            ).model_dump()
        
        # Get page info after navigation
        page = parser.page
        return BrowserNavigateResult(
            success=True,
            url=page.url,
            title=await page.title(),
        ).model_dump()
    except Exception as e:
        logger.exception("navigate failed")
        return BrowserNavigateResult(
            success=False,
            url=url,
            title="",
            error=str(e)
        ).model_dump()


@mcp.tool()
async def back() -> Dict[str, Any]:
    """Navigate back in browser history."""
    try:
        parser = await get_parser()
        action = Action(type=ActionType.BACK)
        await parser.execute_action(action, wait_for_idle=True)
        
        page = parser.page
        return BrowserNavigateResult(
            success=True,
            url=page.url,
            title=await page.title(),
        ).model_dump()
    except Exception as e:
        logger.exception("back failed")
        return BrowserNavigateResult(
            success=False,
            url="",
            title="",
            error=str(e)
        ).model_dump()


@mcp.tool()
async def forward() -> Dict[str, Any]:
    """Navigate forward in browser history."""
    try:
        parser = await get_parser()
        action = Action(type=ActionType.FORWARD)
        await parser.execute_action(action, wait_for_idle=True)
        
        page = parser.page
        return BrowserNavigateResult(
            success=True,
            url=page.url,
            title=await page.title(),
        ).model_dump()
    except Exception as e:
        logger.exception("forward failed")
        return BrowserNavigateResult(
            success=False,
            url="",
            title="",
            error=str(e)
        ).model_dump()


# =============================================================================
# Tools - Page Analysis
# =============================================================================

@mcp.tool()
async def get_page_info(
    include_screenshot: Annotated[bool, Field(description="Include base64 screenshot")] = False
) -> Dict[str, Any]:
    """Analyze current page and return interactive elements (buttons, links, inputs)."""
    try:
        parser = await get_parser()
        parsed_page = await parser.analyze_page()
        
        # Extract actions in simplified format
        actions = []
        if hasattr(parsed_page, 'actions') and hasattr(parsed_page.actions, 'actions'):
            for action in parsed_page.actions.actions:
                # ParsedAction has: type, selector (element index), text/importantText, score
                # selector is a numeric index used for execute_raw_action
                # score can be None, so default to 0.0
                selector_val = getattr(action, 'selector', '')
                actions.append(BrowserAction(
                    type=action.type if isinstance(action.type, str) else str(action.type),
                    selector=str(selector_val) if selector_val is not None else '',
                    text=getattr(action, 'text', '') or getattr(action, 'importantText', '') or '',
                    confidence=float(getattr(action, 'score', None) or 0.0),
                ))
        
        screenshot = None
        if include_screenshot:
            screenshot_b64 = await parser.take_screenshot(
                filepath="/tmp/browser_screenshot.png",
                return_base64=True,
                full_page=False,
            )
            # Strip data URI prefix if present
            clean_b64 = _strip_data_uri(screenshot_b64) if screenshot_b64 else ""
            screenshot = BrowserScreenshot(data=clean_b64)
        
        return BrowserPageInfo(
            success=True,
            url=parsed_page.metadata.url if hasattr(parsed_page, 'metadata') else parser.page.url,
            title=parsed_page.metadata.title if hasattr(parsed_page, 'metadata') else await parser.page.title(),
            actions=actions,
            actions_count=len(actions),
            screenshot=screenshot,
        ).model_dump()
    except Exception as e:
        logger.exception("get_page_info failed")
        return BrowserPageInfo(
            success=False,
            url="",
            title="",
            actions=[],
            actions_count=0,
            error=str(e)
        ).model_dump()


# =============================================================================
# Tools - Interactions
# =============================================================================

@mcp.tool()
async def click(
    selector: Annotated[str, Field(description="CSS selector or element ID to click")]
) -> Dict[str, Any]:
    """Click on an element by CSS selector or element ID."""
    try:
        parser = await get_parser()
        action = Action(
            type=ActionType.CLICK,
            element_id=selector,
        )
        result = await parser.execute_action(action, wait_for_idle=True)
        return BrowserActionResult(
            success=result.get("success", False),
            error=result.get("error") if not result.get("success", False) else None,
        ).model_dump()
    except Exception as e:
        logger.exception("click failed")
        return BrowserActionResult(success=False, error=str(e)).model_dump()


@mcp.tool()
async def type_text(
    selector: Annotated[str, Field(description="CSS selector or element ID of input field")],
    text: Annotated[str, Field(description="Text to type into the field")]
) -> Dict[str, Any]:
    """Type text into an input field."""
    try:
        parser = await get_parser()
        action = Action(
            type=ActionType.TYPE,
            element_id=selector,
            text_to_type=text,
        )
        result = await parser.execute_action(action, wait_for_idle=True)
        return BrowserActionResult(
            success=result.get("success", False),
            error=result.get("error") if not result.get("success", False) else None,
        ).model_dump()
    except Exception as e:
        logger.exception("type_text failed")
        return BrowserActionResult(success=False, error=str(e)).model_dump()


@mcp.tool()
async def hover(
    selector: Annotated[str, Field(description="CSS selector or element ID to hover over")]
) -> Dict[str, Any]:
    """Hover over an element (useful for dropdowns, tooltips)."""
    try:
        parser = await get_parser()
        action = Action(
            type=ActionType.HOVER,
            element_id=selector,
        )
        result = await parser.execute_action(action, wait_for_idle=True)
        return BrowserActionResult(
            success=result.get("success", False),
            error=result.get("error") if not result.get("success", False) else None,
        ).model_dump()
    except Exception as e:
        logger.exception("hover failed")
        return BrowserActionResult(success=False, error=str(e)).model_dump()


@mcp.tool()
async def select_option(
    selector: Annotated[str, Field(description="CSS selector of <select> element")],
    value: Annotated[str, Field(description="Option value to select")]
) -> Dict[str, Any]:
    """Select an option from a dropdown/select element."""
    try:
        parser = await get_parser()
        action = Action(
            type=ActionType.SELECT,
            element_id=selector,
            options=value,
        )
        result = await parser.execute_action(action, wait_for_idle=True)
        return BrowserActionResult(
            success=result.get("success", False),
            error=result.get("error") if not result.get("success", False) else None,
        ).model_dump()
    except Exception as e:
        logger.exception("select_option failed")
        return BrowserActionResult(success=False, error=str(e)).model_dump()


# =============================================================================
# Tools - Scrolling
# =============================================================================

@mcp.tool()
async def scroll(
    direction: Annotated[str, Field(description="Scroll direction: 'down' or 'up'")] = "down",
    amount: Annotated[str, Field(description="Amount: 'viewport' (full page), 'half' (half page)")] = "viewport"
) -> Dict[str, Any]:
    """Scroll the page up or down by viewport or half-viewport."""
    try:
        parser = await get_parser()
        
        # Determine action type
        if amount == "half":
            action_type = ActionType.SCROLL_HALF_VIEWPORT
        else:
            action_type = ActionType.SCROLL_DOWN_VIEWPORT
        
        action = Action(type=action_type)
        
        # For "up" direction, we need to use scroll_by with negative value
        if direction == "up":
            # Get viewport height and scroll up
            viewport = await parser.page.viewport_size
            scroll_amount = -(viewport.get("height", 800) if viewport else 800)
            if amount == "half":
                scroll_amount = scroll_amount // 2
            action = Action(
                type=ActionType.SCROLL_BY,
                metadata={"x": 0, "y": scroll_amount}
            )
        
        result = await parser.execute_action(action, wait_for_idle=True)
        return BrowserActionResult(success=result.get("success", True)).model_dump()
    except Exception as e:
        logger.exception("scroll failed")
        return BrowserActionResult(success=False, error=str(e)).model_dump()


# =============================================================================
# Tools - Screenshots
# =============================================================================

def _strip_data_uri(data: str) -> str:
    """Strip data URI prefix from base64 string if present."""
    if data and data.startswith("data:"):
        # Format: data:image/png;base64,{base64_data}
        if "," in data:
            return data.split(",", 1)[1]
    return data


@mcp.tool()
async def screenshot(
    full_page: Annotated[bool, Field(description="Capture full scrollable page")] = False
) -> Dict[str, Any]:
    """Take a screenshot of the current page (returns base64 PNG)."""
    try:
        parser = await get_parser()
        screenshot_b64 = await parser.take_screenshot(
            filepath="/tmp/browser_screenshot.png",
            return_base64=True,
            full_page=full_page,
        )
        # Strip data URI prefix if present (CeSail returns "data:image/png;base64,...")
        clean_b64 = _strip_data_uri(screenshot_b64)
        return BrowserScreenshotResult(
            success=True,
            data=clean_b64,
            format="png",
            encoding="base64",
        ).model_dump()
    except Exception as e:
        logger.exception("screenshot failed")
        return BrowserScreenshotResult(
            success=False,
            error=str(e),
        ).model_dump()


# =============================================================================
# Tools - Waiting
# =============================================================================

@mcp.tool()
async def wait_for_selector(
    selector: Annotated[str, Field(description="CSS selector to wait for")],
    timeout_ms: Annotated[int, Field(description="Timeout in milliseconds")] = 5000,
    state: Annotated[str, Field(description="State: 'visible', 'hidden', 'attached'")] = "visible"
) -> Dict[str, Any]:
    """Wait for an element to appear, become visible, or disappear."""
    try:
        parser = await get_parser()
        action = Action(
            type=ActionType.WAIT_FOR_SELECTOR,
            metadata={
                "selector": selector,
                "timeout": timeout_ms,
                "state": state,
            }
        )
        result = await parser.execute_action(action, wait_for_idle=False)
        return BrowserActionResult(success=result.get("success", False)).model_dump()
    except Exception as e:
        logger.exception("wait_for_selector failed")
        return BrowserActionResult(success=False, error=str(e)).model_dump()


@mcp.tool()
async def wait(
    ms: Annotated[int, Field(description="Milliseconds to wait")] = 1000
) -> Dict[str, Any]:
    """Wait for a specified duration in milliseconds."""
    try:
        parser = await get_parser()
        action = Action(
            type=ActionType.WAIT,
            metadata={"duration_ms": ms}
        )
        await parser.execute_action(action, wait_for_idle=False)
        return BrowserActionResult(success=True).model_dump()
    except Exception as e:
        logger.exception("wait failed")
        return BrowserActionResult(success=False, error=str(e)).model_dump()


# =============================================================================
# Tools - Escape Hatch (Raw CeSail Actions)
# =============================================================================

@mcp.tool()
async def execute_raw_action(
    action_type: Annotated[str, Field(description="CeSail action type (e.g., 'click', 'type', 'navigate')")],
    params: Annotated[Dict[str, Any], Field(description="Action parameters (element_id, text_to_type, metadata, etc.)")]
) -> Dict[str, Any]:
    """Execute a raw CeSail action for advanced use cases."""
    try:
        parser = await get_parser()
        
        # Build action from type and params
        action_data = {"type": action_type, **params}
        action = Action.from_json(action_data)
        
        # Security check for navigate actions
        if action_type.lower() == "navigate":
            url = params.get("metadata", {}).get("url", "")
            if not is_url_allowed(url):
                return BrowserActionResult(
                    success=False,
                    error=f"URL blocked by security policy: {url}"
                ).model_dump()
        
        result = await parser.execute_action(action, wait_for_idle=True)
        return BrowserActionResult(
            success=result.get("success", False),
            error=result.get("error") if not result.get("success", False) else None,
        ).model_dump()
    except Exception as e:
        logger.exception("execute_raw_action failed")
        return BrowserActionResult(success=False, error=str(e)).model_dump()


# =============================================================================
# Tools - Session Management
# =============================================================================

@mcp.tool()
async def close_browser() -> Dict[str, Any]:
    """Close the browser session (a new one starts on next action)."""
    try:
        await close_parser()
        return BrowserActionResult(success=True).model_dump()
    except Exception as e:
        logger.exception("close_browser failed")
        return BrowserActionResult(success=False, error=str(e)).model_dump()


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    if not HAS_CESAIL:
        logger.error("CeSail is not installed!")
        logger.error("Run: pip install cesail && playwright install chromium")
        exit(1)
    
    logger.info(f"Starting browser MCP server (headless={HEADLESS})")
    mcp.run()
