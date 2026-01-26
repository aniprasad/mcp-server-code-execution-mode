#!/usr/bin/env python3
"""
Test that FX server returns data matching the documented schema.

Validates output structure matches what's documented in API.md:
- convert: {amount, from_currency, to_currency, result, rate, date}
- rates: {base, date, rates}
- history: {base, target, start_date, end_date, rates: [{date, rate}]}

The history tool is particularly important because models need to know
that the data is nested under 'rates' (not returned as a flat list).
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "servers"))

from servers.fx import convert, rates, history


def validate_convert_schema(data: dict):
    """Validate convert response matches documented schema."""
    required_fields = ["amount", "from_currency", "to_currency", "result", "rate", "date"]
    
    missing = [f for f in required_fields if f not in data]
    if missing:
        print(f"❌ convert: Missing fields: {missing}")
        return False
    
    # Type checks
    assert isinstance(data["amount"], (int, float)), "convert: amount should be number"
    assert isinstance(data["from_currency"], str), "convert: from_currency should be str"
    assert isinstance(data["to_currency"], str), "convert: to_currency should be str"
    assert isinstance(data["result"], (int, float)), "convert: result should be number"
    assert isinstance(data["rate"], (int, float)), "convert: rate should be number"
    assert isinstance(data["date"], str), "convert: date should be str (YYYY-MM-DD)"
    
    print(f"✅ convert: All {len(required_fields)} fields present, types valid")
    print(f"   Example: {data['amount']} {data['from_currency']} = {data['result']} {data['to_currency']} (rate: {data['rate']})")
    return True


def validate_rates_schema(data: dict):
    """Validate rates response matches documented schema."""
    required_fields = ["base", "date", "rates"]
    
    missing = [f for f in required_fields if f not in data]
    if missing:
        print(f"❌ rates: Missing fields: {missing}")
        return False
    
    # Type checks
    assert isinstance(data["base"], str), "rates: base should be str"
    assert isinstance(data["date"], str), "rates: date should be str"
    assert isinstance(data["rates"], dict), "rates: rates should be dict"
    
    # Check rates dict has currency codes as keys and numbers as values
    rates_dict = data["rates"]
    assert len(rates_dict) > 0, "rates: rates dict should not be empty"
    
    sample_key = list(rates_dict.keys())[0]
    sample_val = rates_dict[sample_key]
    assert isinstance(sample_key, str) and len(sample_key) == 3, "rates: keys should be 3-letter currency codes"
    assert isinstance(sample_val, (int, float)), "rates: values should be numbers"
    
    print(f"✅ rates: All {len(required_fields)} wrapper fields present")
    print(f"   Base: {data['base']}, Date: {data['date']}, {len(rates_dict)} currencies")
    return True


def validate_history_schema(data: dict):
    """
    Validate history response matches documented schema.
    
    CRITICAL: This tests the nested structure that models need to understand:
    - data['rates'] is the array (not data itself)
    - Each entry has {date, rate}
    """
    # Wrapper fields - this is what the model was getting wrong!
    wrapper_fields = ["base", "target", "start_date", "end_date", "rates"]
    missing = [f for f in wrapper_fields if f not in data]
    if missing:
        print(f"❌ history: Missing wrapper fields: {missing}")
        print(f"   This is the root cause - model expected flat list but got nested object")
        return False
    
    # Type checks for wrapper
    assert isinstance(data["base"], str), "history: base should be str"
    assert isinstance(data["target"], str), "history: target should be str"
    assert isinstance(data["start_date"], str), "history: start_date should be str"
    assert isinstance(data["end_date"], str), "history: end_date should be str"
    
    # rates should be a list (this is what the model needs to access!)
    rates_list = data["rates"]
    assert isinstance(rates_list, list), "history: rates should be a list"
    assert len(rates_list) > 0, "history: rates should not be empty"
    
    # Each entry in rates
    entry_fields = ["date", "rate"]
    for i, entry in enumerate(rates_list[:3]):  # Check first 3
        missing_entry = [f for f in entry_fields if f not in entry]
        if missing_entry:
            print(f"❌ history: rates[{i}] missing fields: {missing_entry}")
            return False
        assert isinstance(entry["date"], str), f"history: rates[{i}].date should be str"
        assert isinstance(entry["rate"], (int, float)), f"history: rates[{i}].rate should be number"
    
    print(f"✅ history: Wrapper OK, rates array has {len(rates_list)} entries with correct schema")
    print(f"   {data['base']}/{data['target']}: {data['start_date']} to {data['end_date']}")
    print(f"   ⚠️  Model should use: df = pd.DataFrame(result['rates'])  # NOT DataFrame(result)")
    return True


async def test_all_schemas():
    """Test all FX tools return correct schema."""
    print("=" * 60)
    print("Testing FX server output schemas")
    print("=" * 60)
    
    all_passed = True
    
    # Test convert
    print("\n--- convert(amount=100, from_currency='USD', to_currency='EUR') ---")
    try:
        result = await convert(100, "USD", "EUR")
        print(f"   Raw keys: {list(result.keys())}")
        if not validate_convert_schema(result):
            all_passed = False
    except Exception as e:
        print(f"❌ convert failed: {e}")
        all_passed = False
    
    # Test rates
    print("\n--- rates(base='USD') ---")
    try:
        result = await rates("USD")
        print(f"   Raw keys: {list(result.keys())}")
        if not validate_rates_schema(result):
            all_passed = False
    except Exception as e:
        print(f"❌ rates failed: {e}")
        all_passed = False
    
    # Test history (THIS IS THE CRITICAL ONE)
    print("\n--- history(from_currency='USD', to_currency='CAD', days=30) ---")
    try:
        result = await history("USD", "CAD", 30)
        print(f"   Raw keys: {list(result.keys())}")
        if not validate_history_schema(result):
            all_passed = False
        
        # Show what the model SHOULD do vs what it DID
        print("\n   📝 Correct usage pattern:")
        print("      result = await mcp_fx.history('USD', 'CAD', 30)")
        print("      df = pd.DataFrame(result['rates'])  # Access nested 'rates' list")
        print("      # NOT: df = pd.DataFrame(result)  # Wrong - result is a dict with metadata")
        
    except Exception as e:
        print(f"❌ history failed: {e}")
        all_passed = False
    
    # Test history with larger range (183 days like the failing example)
    print("\n--- history(from_currency='USD', to_currency='CAD', days=183) ---")
    try:
        result = await history("USD", "CAD", 183)
        rates_count = len(result.get("rates", []))
        print(f"   Raw keys: {list(result.keys())}")
        print(f"   rates array length: {rates_count} entries")
        if rates_count > 0:
            print(f"   First: {result['rates'][0]}")
            print(f"   Last:  {result['rates'][-1]}")
    except Exception as e:
        print(f"❌ history (183 days) failed: {e}")
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL FX SCHEMA TESTS PASSED")
    else:
        print("❌ SOME FX SCHEMA TESTS FAILED")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(test_all_schemas())
    sys.exit(0 if success else 1)
