#!/usr/bin/env python3
"""
Test that Wikipedia server returns data matching the documented schema.

Validates output structure:
- summary: {title, extract, description, url, thumbnail?, coordinates?}
- search: {query, results: [{title, description, url}]}
- on_this_day: {date, events: [{year, text, pages}]}
- random: {title, extract, description, url, thumbnail?}
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "servers"))

from servers.wikipedia import summary, search, on_this_day, random_article, trending, featured


def validate_summary_schema(data: dict):
    """Validate summary response matches documented schema."""
    required_fields = ["title", "extract", "description", "url"]
    optional_fields = ["thumbnail", "coordinates"]
    
    missing = [f for f in required_fields if f not in data]
    if missing:
        print(f"❌ summary: Missing required fields: {missing}")
        return False
    
    # Type checks
    assert isinstance(data["title"], str), "summary: title should be str"
    assert isinstance(data["extract"], str), "summary: extract should be str"
    assert isinstance(data["url"], str), "summary: url should be str"
    
    print(f"✅ summary: All required fields present, types valid")
    print(f"   Title: {data['title']}")
    print(f"   Extract: {data['extract'][:100]}...")
    if data.get("thumbnail"):
        print(f"   Thumbnail: {data['thumbnail'][:60]}...")
    return True


def validate_search_schema(data: dict):
    """Validate search response matches documented schema."""
    required_fields = ["query", "results"]
    
    missing = [f for f in required_fields if f not in data]
    if missing:
        print(f"❌ search: Missing fields: {missing}")
        return False
    
    assert isinstance(data["results"], list), "search: results should be list"
    
    if len(data["results"]) > 0:
        result_fields = ["title", "description", "url"]
        for i, r in enumerate(data["results"][:3]):
            missing_r = [f for f in result_fields if f not in r]
            if missing_r:
                print(f"❌ search: results[{i}] missing fields: {missing_r}")
                return False
    
    print(f"✅ search: Wrapper OK, {len(data['results'])} results")
    for r in data["results"][:3]:
        print(f"   - {r['title']}")
    return True


def validate_on_this_day_schema(data: dict):
    """Validate on_this_day response matches documented schema."""
    required_fields = ["date", "events"]
    
    missing = [f for f in required_fields if f not in data]
    if missing:
        print(f"❌ on_this_day: Missing fields: {missing}")
        return False
    
    assert isinstance(data["events"], list), "on_this_day: events should be list"
    
    if len(data["events"]) > 0:
        for i, e in enumerate(data["events"][:3]):
            if "text" not in e:
                print(f"❌ on_this_day: events[{i}] missing 'text' field")
                return False
    
    print(f"✅ on_this_day: Date {data['date']}, {len(data['events'])} events")
    for e in data["events"][:3]:
        year = e.get("year", "?")
        print(f"   - {year}: {e['text'][:60]}...")
    return True


async def test_all_schemas():
    """Test all Wikipedia tools return correct schema."""
    print("=" * 60)
    print("Testing Wikipedia server output schemas")
    print("=" * 60)
    
    all_passed = True
    
    # Test summary
    print("\n--- summary(title='Python (programming language)') ---")
    try:
        result = await summary("Python (programming language)")
        print(f"   Raw keys: {list(result.keys())}")
        if not validate_summary_schema(result):
            all_passed = False
    except Exception as e:
        print(f"❌ summary failed: {e}")
        all_passed = False
    
    # Test search
    print("\n--- search(query='machine learning', limit=5) ---")
    try:
        result = await search("machine learning", 5)
        print(f"   Raw keys: {list(result.keys())}")
        if not validate_search_schema(result):
            all_passed = False
    except Exception as e:
        print(f"❌ search failed: {e}")
        all_passed = False
    
    # Test on_this_day
    print("\n--- on_this_day(month=1, day=25) ---")
    try:
        result = await on_this_day(1, 25)
        print(f"   Raw keys: {list(result.keys())}")
        if not validate_on_this_day_schema(result):
            all_passed = False
    except Exception as e:
        print(f"❌ on_this_day failed: {e}")
        all_passed = False
    
    # Test random
    print("\n--- random() ---")
    try:
        result = await random_article()
        print(f"   Raw keys: {list(result.keys())}")
        if not validate_summary_schema(result):
            all_passed = False
    except Exception as e:
        print(f"❌ random failed: {e}")
        all_passed = False
    
    # Test trending
    print("\n--- trending(limit=5) ---")
    try:
        result = await trending(5)
        print(f"   Raw keys: {list(result.keys())}")
        if "date" not in result or "articles" not in result:
            print(f"❌ trending: Missing 'date' or 'articles' fields")
            all_passed = False
        else:
            print(f"✅ trending: {len(result['articles'])} articles on {result['date']}")
            for a in result["articles"][:5]:
                print(f"   #{a['rank']}: {a['title']} ({a['views']:,} views)")
    except Exception as e:
        print(f"❌ trending failed: {e}")
        all_passed = False
    
    # Test featured
    print("\n--- featured() ---")
    try:
        result = await featured()
        print(f"   Raw keys: {list(result.keys())}")
        if not validate_summary_schema(result):
            all_passed = False
        print(f"   Today's featured: {result['title']}")
    except Exception as e:
        print(f"❌ featured failed: {e}")
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL WIKIPEDIA SCHEMA TESTS PASSED")
    else:
        print("❌ SOME WIKIPEDIA SCHEMA TESTS FAILED")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(test_all_schemas())
    sys.exit(0 if success else 1)
