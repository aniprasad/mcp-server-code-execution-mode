#!/usr/bin/env python3
"""
Stocks MCP Server

Provides real-time stock quotes, historical prices, and market data using Yahoo Finance API.

Features:
- Real-time quotes for stocks and ETFs
- Historical price data (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
- Ticker search
- Market summary (major indices)
- Cryptocurrency prices

Usage in sandbox:
    quote = await mcp_stocks.quote(symbol="AAPL")
    history = await mcp_stocks.history(symbol="MSFT", period="1mo")
    results = await mcp_stocks.search(query="tesla")
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request
import urllib.parse

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Import schemas for output validation
try:
    from schemas import (
        StockQuote, HistoricalPrice, MarketIndex, MarketSummary,
        StockSearchResult, StockHistory
    )
    HAS_SCHEMAS = True
except ImportError:
    try:
        from .schemas import (
            StockQuote, HistoricalPrice, MarketIndex, MarketSummary,
            StockSearchResult, StockHistory
        )
        HAS_SCHEMAS = True
    except ImportError:
        HAS_SCHEMAS = False

SERVER_NAME = "stocks"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"

# Valid periods for historical data
VALID_PERIODS = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]

# Major market indices
MARKET_INDICES = [
    {"symbol": "^GSPC", "name": "S&P 500"},
    {"symbol": "^DJI", "name": "Dow Jones"},
    {"symbol": "^IXIC", "name": "NASDAQ"},
    {"symbol": "^RUT", "name": "Russell 2000"},
    {"symbol": "^VIX", "name": "VIX"},
    {"symbol": "^FTSE", "name": "FTSE 100"},
    {"symbol": "^N225", "name": "Nikkei 225"},
]

# Popular cryptocurrencies
CRYPTO_SYMBOLS = {
    "bitcoin": "BTC-USD",
    "btc": "BTC-USD",
    "ethereum": "ETH-USD",
    "eth": "ETH-USD",
    "dogecoin": "DOGE-USD",
    "doge": "DOGE-USD",
    "solana": "SOL-USD",
    "sol": "SOL-USD",
    "cardano": "ADA-USD",
    "ada": "ADA-USD",
    "ripple": "XRP-USD",
    "xrp": "XRP-USD",
}

logging.basicConfig(level=logging.INFO, format="%(name)s - %(message)s")
logger = logging.getLogger(SERVER_NAME)

app = Server(SERVER_NAME)


# =============================================================================
# Yahoo Finance API Helpers
# =============================================================================

def _yahoo_request(url: str) -> Dict[str, Any]:
    """Make HTTP request to Yahoo Finance API."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"Symbol not found")
        raise ValueError(f"Yahoo Finance API error: {e.code}")
    except urllib.error.URLError as e:
        raise ValueError(f"Network error: {e.reason}")


def _format_number(value: float, decimals: int = 2) -> str:
    """Format large numbers with K, M, B suffixes."""
    if value is None:
        return "N/A"
    if value >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.{decimals}f}T"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.{decimals}f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.{decimals}f}M"
    if value >= 1_000:
        return f"{value / 1_000:.{decimals}f}K"
    return f"{value:.{decimals}f}"


def _parse_quote(meta: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    """Parse quote data from Yahoo Finance chart response."""
    price = meta.get("regularMarketPrice", 0)
    prev_close = meta.get("chartPreviousClose", meta.get("previousClose", price))
    change = price - prev_close if prev_close else 0
    change_pct = (change / prev_close * 100) if prev_close else 0
    
    return {
        "symbol": symbol.upper(),
        "name": meta.get("longName", meta.get("shortName", symbol)),
        "price": round(price, 2),
        "change": round(change, 2),
        "change_percent": round(change_pct, 2),
        "currency": meta.get("currency", "USD"),
        "exchange": meta.get("exchangeName", ""),
        "market_state": meta.get("marketState", "REGULAR"),
        "volume": meta.get("regularMarketVolume", 0),
        "volume_formatted": _format_number(meta.get("regularMarketVolume", 0), 0),
        "day_high": meta.get("regularMarketDayHigh"),
        "day_low": meta.get("regularMarketDayLow"),
        "year_high": meta.get("fiftyTwoWeekHigh"),
        "year_low": meta.get("fiftyTwoWeekLow"),
        "market_cap": meta.get("marketCap"),
        "market_cap_formatted": _format_number(meta.get("marketCap"), 2) if meta.get("marketCap") else None,
        "timestamp": datetime.now().isoformat(),
    }


# =============================================================================
# Tool Definitions
# =============================================================================

@app.list_tools()
async def list_tools() -> List[Tool]:
    period_list = ", ".join(VALID_PERIODS)
    
    return [
        Tool(
            name="quote",
            description="Get real-time stock quote with price, change, volume, and key metrics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT', 'GOOGL')",
                    },
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="history",
            description="Get historical price data (OHLCV) for a stock.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
                    },
                    "period": {
                        "type": "string",
                        "description": f"Time period. Options: {period_list}. Default: 1mo",
                        "default": "1mo",
                    },
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="search",
            description="Search for stock ticker symbols by company name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Company name or partial ticker to search (e.g., 'apple', 'tesla', 'micro')",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="market_summary",
            description="Get current prices for major market indices (S&P 500, Dow Jones, NASDAQ, etc.).",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="crypto",
            description="Get cryptocurrency price in USD. Supports: bitcoin, ethereum, dogecoin, solana, cardano, ripple.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Crypto name or symbol (e.g., 'bitcoin', 'btc', 'ethereum', 'eth')",
                    },
                },
                "required": ["symbol"],
            },
        ),
    ]


# =============================================================================
# Tool Implementations
# =============================================================================

async def get_quote(symbol: str) -> Dict[str, Any]:
    """Get real-time quote for a stock."""
    symbol = symbol.upper().strip()
    
    url = f"{YAHOO_CHART_URL}/{symbol}?interval=1d&range=1d"
    data = _yahoo_request(url)
    
    result = data.get("chart", {}).get("result", [])
    if not result:
        raise ValueError(f"Symbol '{symbol}' not found")
    
    meta = result[0].get("meta", {})
    return _parse_quote(meta, symbol)


async def get_history(symbol: str, period: str = "1mo") -> Dict[str, Any]:
    """Get historical OHLCV data for a stock."""
    symbol = symbol.upper().strip()
    period = period.lower()
    
    if period not in VALID_PERIODS:
        raise ValueError(f"Invalid period '{period}'. Options: {', '.join(VALID_PERIODS)}")
    
    # Determine interval based on period
    interval = "1d"  # default daily
    if period in ["1d", "5d"]:
        interval = "5m" if period == "1d" else "15m"
    elif period in ["1mo", "3mo"]:
        interval = "1d"
    else:
        interval = "1wk"
    
    url = f"{YAHOO_CHART_URL}/{symbol}?interval={interval}&range={period}"
    data = _yahoo_request(url)
    
    result = data.get("chart", {}).get("result", [])
    if not result:
        raise ValueError(f"Symbol '{symbol}' not found")
    
    meta = result[0].get("meta", {})
    timestamps = result[0].get("timestamp", [])
    indicators = result[0].get("indicators", {})
    quote_data = indicators.get("quote", [{}])[0]
    
    # Build price history
    prices = []
    opens = quote_data.get("open", [])
    highs = quote_data.get("high", [])
    lows = quote_data.get("low", [])
    closes = quote_data.get("close", [])
    volumes = quote_data.get("volume", [])
    
    for i, ts in enumerate(timestamps):
        if closes[i] is None:
            continue  # Skip missing data points
        
        date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M" if interval in ["5m", "15m"] else "%Y-%m-%d")
        prices.append({
            "date": date_str,
            "open": round(opens[i], 2) if opens[i] else None,
            "high": round(highs[i], 2) if highs[i] else None,
            "low": round(lows[i], 2) if lows[i] else None,
            "close": round(closes[i], 2) if closes[i] else None,
            "volume": volumes[i] if volumes[i] else 0,
        })
    
    return {
        "symbol": symbol,
        "name": meta.get("longName", meta.get("shortName", symbol)),
        "currency": meta.get("currency", "USD"),
        "period": period,
        "interval": interval,
        "prices_count": len(prices),
        "prices": prices,
    }


async def search_symbol(query: str) -> Dict[str, Any]:
    """Search for stock symbols by company name."""
    query = query.strip()
    encoded_query = urllib.parse.quote(query)
    
    url = f"{YAHOO_SEARCH_URL}?q={encoded_query}&quotesCount=10&newsCount=0"
    data = _yahoo_request(url)
    
    quotes = data.get("quotes", [])
    results = []
    
    for q in quotes:
        quote_type = q.get("quoteType", "")
        if quote_type in ["EQUITY", "ETF", "MUTUALFUND", "INDEX"]:
            results.append({
                "symbol": q.get("symbol", ""),
                "name": q.get("shortname", q.get("longname", "")),
                "type": quote_type,
                "exchange": q.get("exchange", ""),
            })
    
    return {
        "query": query,
        "results_count": len(results),
        "results": results,
    }


async def get_market_summary() -> Dict[str, Any]:
    """Get major market indices."""
    indices = []
    
    for idx in MARKET_INDICES:
        try:
            url = f"{YAHOO_CHART_URL}/{idx['symbol']}?interval=1d&range=1d"
            data = _yahoo_request(url)
            result = data.get("chart", {}).get("result", [])
            
            if result:
                meta = result[0].get("meta", {})
                price = meta.get("regularMarketPrice", 0)
                prev = meta.get("chartPreviousClose", price)
                change = price - prev if prev else 0
                change_pct = (change / prev * 100) if prev else 0
                
                indices.append({
                    "symbol": idx["symbol"],
                    "name": idx["name"],
                    "price": round(price, 2),
                    "change": round(change, 2),
                    "change_percent": round(change_pct, 2),
                })
        except Exception as e:
            logger.warning(f"Failed to fetch {idx['symbol']}: {e}")
            indices.append({
                "symbol": idx["symbol"],
                "name": idx["name"],
                "error": str(e),
            })
    
    return {
        "timestamp": datetime.now().isoformat(),
        "indices_count": len(indices),
        "indices": indices,
    }


async def get_crypto(symbol: str) -> Dict[str, Any]:
    """Get cryptocurrency price."""
    symbol = symbol.lower().strip()
    
    # Map common names to Yahoo Finance symbols
    yahoo_symbol = CRYPTO_SYMBOLS.get(symbol, f"{symbol.upper()}-USD")
    
    url = f"{YAHOO_CHART_URL}/{yahoo_symbol}?interval=1d&range=1d"
    data = _yahoo_request(url)
    
    result = data.get("chart", {}).get("result", [])
    if not result:
        available = ", ".join(CRYPTO_SYMBOLS.keys())
        raise ValueError(f"Crypto '{symbol}' not found. Try: {available}")
    
    meta = result[0].get("meta", {})
    quote = _parse_quote(meta, yahoo_symbol)
    quote["crypto_name"] = symbol.upper()
    
    return quote


# =============================================================================
# Tool Dispatcher
# =============================================================================

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    logger.info(f"Tool called: {name} with args: {arguments}")
    
    try:
        if name == "quote":
            result = await get_quote(symbol=arguments["symbol"])
        elif name == "history":
            result = await get_history(
                symbol=arguments["symbol"],
                period=arguments.get("period", "1mo"),
            )
        elif name == "search":
            result = await search_symbol(query=arguments["query"])
        elif name == "market_summary":
            result = await get_market_summary()
        elif name == "crypto":
            result = await get_crypto(symbol=arguments["symbol"])
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# =============================================================================
# Entry Point
# =============================================================================

async def main() -> None:
    logger.info(f"Starting {SERVER_NAME} MCP server...")
    
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
