#!/usr/bin/env python3
"""
FX (Currency Exchange) MCP Server

Uses Frankfurter API for exchange rate data.
https://frankfurter.dev/

Usage in sandbox:
    result = await mcp_fx.convert(amount=100, from_currency='USD', to_currency='EUR')
    rates = await mcp_fx.rates(base='USD')
    history = await mcp_fx.history(from_currency='USD', to_currency='EUR', days=30)
"""

import asyncio
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Handle both direct execution and import from parent
try:
    from schemas import ConversionResult, ExchangeRates, RateHistory, RateHistoryEntry
except ImportError:
    from .schemas import ConversionResult, ExchangeRates, RateHistory, RateHistoryEntry

SERVER_NAME = "fx"
FRANKFURTER_API = "https://api.frankfurter.dev/v1"

logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")
logger = logging.getLogger(SERVER_NAME)

app = Server(SERVER_NAME)

# Supported currencies (ECB reference currencies)
SUPPORTED_CURRENCIES = [
    "AUD", "BGN", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP",
    "HKD", "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KRW", "MXN", "MYR",
    "NOK", "NZD", "PHP", "PLN", "RON", "SEK", "SGD", "THB", "TRY", "USD", "ZAR"
]


def _make_request(url: str) -> Dict[str, Any]:
    """Make HTTP GET request and return JSON."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"Currency not found or invalid date range")
        raise RuntimeError(f"HTTP error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")


def _validate_currency(code: str) -> str:
    """Validate and normalize currency code."""
    code = code.upper().strip()
    if code not in SUPPORTED_CURRENCIES:
        available = ", ".join(SUPPORTED_CURRENCIES)
        raise ValueError(f"Unsupported currency: {code}. Supported: {available}")
    return code


@app.list_tools()
async def list_tools() -> List[Tool]:
    currency_list = ", ".join(SUPPORTED_CURRENCIES[:10]) + ", ..."
    
    return [
        Tool(
            name="convert",
            description="Convert an amount from one currency to another.",
            inputSchema={
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "Amount to convert",
                    },
                    "from_currency": {
                        "type": "string",
                        "description": f"Source currency code (e.g., 'USD', 'EUR', 'GBP')",
                    },
                    "to_currency": {
                        "type": "string",
                        "description": f"Target currency code (e.g., 'EUR', 'JPY', 'CHF')",
                    },
                },
                "required": ["amount", "from_currency", "to_currency"],
            },
        ),
        Tool(
            name="rates",
            description="Get current exchange rates for a base currency.",
            inputSchema={
                "type": "object",
                "properties": {
                    "base": {
                        "type": "string",
                        "description": f"Base currency code. Options: {currency_list}",
                        "default": "EUR",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="history",
            description="Get historical exchange rates for charting.",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_currency": {
                        "type": "string",
                        "description": "Base currency code (e.g., 'USD')",
                    },
                    "to_currency": {
                        "type": "string",
                        "description": "Target currency code (e.g., 'EUR')",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days of history (1-365)",
                        "default": 30,
                    },
                },
                "required": ["from_currency", "to_currency"],
            },
        ),
    ]


# =============================================================================
# Tool Implementations
# =============================================================================

async def convert(amount: float, from_currency: str, to_currency: str) -> Dict[str, Any]:
    """Convert amount from one currency to another."""
    from_curr = _validate_currency(from_currency)
    to_curr = _validate_currency(to_currency)
    
    if from_curr == to_curr:
        return ConversionResult(
            amount=amount,
            from_currency=from_curr,
            to_currency=to_curr,
            result=amount,
            rate=1.0,
            date=datetime.now().strftime("%Y-%m-%d"),
        ).model_dump()
    
    url = f"{FRANKFURTER_API}/latest?base={from_curr}&symbols={to_curr}"
    data = _make_request(url)
    
    rate = data.get("rates", {}).get(to_curr, 0)
    result = amount * rate
    
    return ConversionResult(
        amount=amount,
        from_currency=from_curr,
        to_currency=to_curr,
        result=round(result, 2),
        rate=rate,
        date=data.get("date", ""),
    ).model_dump()


async def rates(base: str = "EUR") -> Dict[str, Any]:
    """Get all exchange rates for a base currency."""
    base_curr = _validate_currency(base)
    
    url = f"{FRANKFURTER_API}/latest?base={base_curr}"
    data = _make_request(url)
    
    return ExchangeRates(
        base=base_curr,
        date=data.get("date", ""),
        rates=data.get("rates", {}),
    ).model_dump()


async def history(from_currency: str, to_currency: str, days: int = 30) -> Dict[str, Any]:
    """Get historical exchange rates for a currency pair."""
    from_curr = _validate_currency(from_currency)
    to_curr = _validate_currency(to_currency)
    
    # Clamp days to valid range
    days = max(1, min(365, days))
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    url = f"{FRANKFURTER_API}/{start_str}..{end_str}?base={from_curr}&symbols={to_curr}"
    data = _make_request(url)
    
    # Convert rates dict to list of entries
    rates_dict = data.get("rates", {})
    rate_entries = []
    
    for date_str in sorted(rates_dict.keys()):
        rate_value = rates_dict[date_str].get(to_curr)
        if rate_value is not None:
            rate_entries.append(RateHistoryEntry(
                date=date_str,
                rate=rate_value,
            ))
    
    return RateHistory(
        base=from_curr,
        target=to_curr,
        start_date=data.get("start_date", start_str),
        end_date=data.get("end_date", end_str),
        rates=rate_entries,
    ).model_dump()


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    logger.info(f"Tool called: {name} with args: {arguments}")
    
    try:
        if name == "convert":
            result = await convert(
                amount=float(arguments.get("amount", 0)),
                from_currency=arguments.get("from_currency", ""),
                to_currency=arguments.get("to_currency", ""),
            )
        elif name == "rates":
            result = await rates(base=arguments.get("base", "EUR"))
        elif name == "history":
            result = await history(
                from_currency=arguments.get("from_currency", ""),
                to_currency=arguments.get("to_currency", ""),
                days=arguments.get("days", 30),
            )
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main() -> None:
    logger.info(f"Starting {SERVER_NAME} MCP server (Frankfurter API)...")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
