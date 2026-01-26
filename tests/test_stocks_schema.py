#!/usr/bin/env python3
"""
Test that stocks server returns data matching the documented schema.

Validates output structure matches what's documented in API.md:
- quote: {symbol, name, price, change, change_percent, ...}
- history: {symbol, name, currency, period, interval, prices_count, prices: [...]}
- search: {query, results_count, results: [...]}
- market_summary: {timestamp, indices_count, indices: [...]}
- crypto: same as quote
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "servers"))

from servers.stocks import get_quote, get_history, search_symbol, get_market_summary, get_crypto


def validate_quote_schema(data: dict, label: str = "quote"):
    """Validate quote response matches documented schema."""
    required_fields = [
        "symbol", "name", "price", "change", "change_percent",
        "currency", "exchange", "market_state", "volume", "volume_formatted",
        "day_high", "day_low", "year_high", "year_low",
        "market_cap", "market_cap_formatted"
    ]
    
    missing = [f for f in required_fields if f not in data]
    if missing:
        print(f"❌ {label}: Missing fields: {missing}")
        return False
    
    # Type checks
    assert isinstance(data["symbol"], str), f"{label}: symbol should be str"
    assert isinstance(data["price"], (int, float)), f"{label}: price should be number"
    assert isinstance(data["change"], (int, float)), f"{label}: change should be number"
    assert isinstance(data["change_percent"], (int, float)), f"{label}: change_percent should be number"
    
    print(f"✅ {label}: All {len(required_fields)} fields present, types valid")
    return True


def validate_history_schema(data: dict):
    """Validate history response matches documented schema."""
    # Wrapper fields
    wrapper_fields = ["symbol", "name", "currency", "period", "interval", "prices_count", "prices"]
    missing = [f for f in wrapper_fields if f not in data]
    if missing:
        print(f"❌ history: Missing wrapper fields: {missing}")
        return False
    
    # prices should be an array
    prices = data["prices"]
    assert isinstance(prices, list), "history: prices should be a list"
    assert len(prices) > 0, "history: prices should not be empty"
    
    # Each price entry
    price_fields = ["date", "open", "high", "low", "close", "volume"]
    for i, p in enumerate(prices[:3]):  # Check first 3
        missing_price = [f for f in price_fields if f not in p]
        if missing_price:
            print(f"❌ history: prices[{i}] missing fields: {missing_price}")
            return False
    
    print(f"✅ history: Wrapper OK, prices array has {len(prices)} entries with correct schema")
    return True


def validate_search_schema(data: dict):
    """Validate search response matches documented schema."""
    wrapper_fields = ["query", "results_count", "results"]
    missing = [f for f in wrapper_fields if f not in data]
    if missing:
        print(f"❌ search: Missing wrapper fields: {missing}")
        return False
    
    results = data["results"]
    assert isinstance(results, list), "search: results should be a list"
    
    if len(results) > 0:
        result_fields = ["symbol", "name", "type", "exchange"]
        for i, r in enumerate(results[:3]):
            missing_result = [f for f in result_fields if f not in r]
            if missing_result:
                print(f"❌ search: results[{i}] missing fields: {missing_result}")
                return False
    
    print(f"✅ search: Wrapper OK, {len(results)} results with correct schema")
    return True


def validate_market_summary_schema(data: dict):
    """Validate market_summary response matches documented schema."""
    wrapper_fields = ["timestamp", "indices_count", "indices"]
    missing = [f for f in wrapper_fields if f not in data]
    if missing:
        print(f"❌ market_summary: Missing wrapper fields: {missing}")
        return False
    
    indices = data["indices"]
    assert isinstance(indices, list), "market_summary: indices should be a list"
    assert len(indices) > 0, "market_summary: indices should not be empty"
    
    index_fields = ["symbol", "name", "price", "change", "change_percent"]
    for i, idx in enumerate(indices[:3]):
        # Some may have "error" instead of price data
        if "error" not in idx:
            missing_idx = [f for f in index_fields if f not in idx]
            if missing_idx:
                print(f"❌ market_summary: indices[{i}] missing fields: {missing_idx}")
                return False
    
    print(f"✅ market_summary: Wrapper OK, {len(indices)} indices with correct schema")
    return True


async def test_all_schemas():
    """Test all stocks tools return correct schema."""
    print("=" * 60)
    print("Testing stocks server output schemas")
    print("=" * 60)
    
    all_passed = True
    
    # Test quote
    print("\n--- quote(symbol='AAPL') ---")
    try:
        result = await get_quote("AAPL")
        print(f"   Raw keys: {list(result.keys())}")
        if not validate_quote_schema(result, "quote"):
            all_passed = False
    except Exception as e:
        print(f"❌ quote failed: {e}")
        all_passed = False
    
    # Test history
    print("\n--- history(symbol='MSFT', period='1mo') ---")
    try:
        result = await get_history("MSFT", "1mo")
        print(f"   Raw keys: {list(result.keys())}")
        if not validate_history_schema(result):
            all_passed = False
    except Exception as e:
        print(f"❌ history failed: {e}")
        all_passed = False
    
    # Test search
    print("\n--- search(query='apple') ---")
    try:
        result = await search_symbol("apple")
        print(f"   Raw keys: {list(result.keys())}")
        if not validate_search_schema(result):
            all_passed = False
    except Exception as e:
        print(f"❌ search failed: {e}")
        all_passed = False
    
    # Test market_summary
    print("\n--- market_summary() ---")
    try:
        result = await get_market_summary()
        print(f"   Raw keys: {list(result.keys())}")
        if not validate_market_summary_schema(result):
            all_passed = False
    except Exception as e:
        print(f"❌ market_summary failed: {e}")
        all_passed = False
    
    # Test crypto (should match quote schema)
    print("\n--- crypto(symbol='bitcoin') ---")
    try:
        result = await get_crypto("bitcoin")
        print(f"   Raw keys: {list(result.keys())}")
        if not validate_quote_schema(result, "crypto"):
            all_passed = False
    except Exception as e:
        print(f"❌ crypto failed: {e}")
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL SCHEMA TESTS PASSED")
    else:
        print("❌ SOME SCHEMA TESTS FAILED")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(test_all_schemas())
    sys.exit(0 if success else 1)
