#!/usr/bin/env python3
"""
Test that MS Forms server returns data matching the documented schema.

Requirements:
  - MS_FORMS_TOKEN: The __RequestVerificationToken cookie value
  - MS_FORMS_COOKIES: The full cookie header from a Forms API request

To get these:
1. Open Microsoft Forms in browser
2. Open DevTools (F12) → Network tab
3. Open any form's responses page
4. Find any request to forms.office.com/formapi/...
5. Copy the `cookie` header value → MS_FORMS_COOKIES
6. Copy the `__RequestVerificationToken` cookie → MS_FORMS_TOKEN

Usage:
    # Load credentials from mcp-servers.json and test:
    python tests/test_msforms_schema.py <form_id>
    
    # Or with explicit env vars:
    $env:MS_FORMS_TOKEN="..."; $env:MS_FORMS_COOKIES="..."; python tests/test_msforms_schema.py <form_id>
"""

import json
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "servers"))

from servers.msforms import get_form_data, get_form_summary, decode_form_id


def load_credentials_from_config():
    """Load credentials from servers/mcp-servers.json if not in env."""
    config_path = Path(__file__).parent.parent / "servers" / "mcp-servers.json"
    
    if not config_path.exists():
        print(f"⚠ Config not found: {config_path}")
        return
    
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        msforms_env = config.get("mcpServers", {}).get("msforms", {}).get("env", {})
        
        if not os.environ.get("MS_FORMS_TOKEN") and msforms_env.get("MS_FORMS_TOKEN"):
            os.environ["MS_FORMS_TOKEN"] = msforms_env["MS_FORMS_TOKEN"]
            print("✓ Loaded MS_FORMS_TOKEN from mcp-servers.json")
        
        if not os.environ.get("MS_FORMS_BEARER") and msforms_env.get("MS_FORMS_BEARER"):
            os.environ["MS_FORMS_BEARER"] = msforms_env["MS_FORMS_BEARER"]
            print("✓ Loaded MS_FORMS_BEARER from mcp-servers.json")
        
        if not os.environ.get("MS_FORMS_COOKIES") and msforms_env.get("MS_FORMS_COOKIES"):
            os.environ["MS_FORMS_COOKIES"] = msforms_env["MS_FORMS_COOKIES"]
            print("✓ Loaded MS_FORMS_COOKIES from mcp-servers.json")
    except Exception as e:
        print(f"⚠ Could not load config: {e}")


def validate_decode_form(form_id: str) -> bool:
    """Test decode_form_id() function."""
    print("\n--- Test 1: decode_form_id() ---")
    
    try:
        decoded = decode_form_id(form_id)
        
        # Check required fields
        required = ["OrgId", "OwnerId", "TableId", "IsGroupOwner", "ContainerId"]
        missing = [f for f in required if f not in decoded]
        if missing:
            print(f"❌ Missing fields: {missing}")
            return False
        
        if decoded.get("error"):
            print(f"❌ Decode error: {decoded['error']}")
            return False
        
        print(f"✅ decode_form_id: Success")
        print(f"   OrgId (tenant):  {decoded['OrgId']}")
        print(f"   OwnerId (user):  {decoded['OwnerId']}")
        print(f"   TableId:         {decoded['TableId']}")
        print(f"   IsGroupOwner:    {decoded['IsGroupOwner']}")
        return True
        
    except Exception as e:
        print(f"❌ decode_form_id failed: {e}")
        return False


def validate_form_summary(form_id: str) -> bool:
    """Test get_form_summary() function."""
    print("\n--- Test 2: get_form_summary() ---")
    
    try:
        data = get_form_summary(form=form_id)
        
        # Check required fields
        required = ["title", "responseCount", "questions"]
        missing = [f for f in required if f not in data]
        if missing:
            print(f"❌ Missing fields: {missing}")
            return False
        
        print(f"✅ get_form_summary: Success")
        print(f"   Title:          {data['title']}")
        print(f"   Response count: {data['responseCount']}")
        print(f"   Questions:      {len(data['questions'])}")
        
        # Show first few questions
        for q_title, q_data in list(data['questions'].items())[:3]:
            q_type = q_data.get("type", "unknown")
            if q_type == "rating":
                print(f"   - {q_title[:40]}... (rating, avg: {q_data.get('average', 'N/A')})")
            elif q_type == "choice":
                print(f"   - {q_title[:40]}... (choice)")
            elif q_type == "text":
                print(f"   - {q_title[:40]}... (text, {q_data.get('count', 0)} responses)")
        
        return True
        
    except Exception as e:
        print(f"❌ get_form_summary failed: {e}")
        return False


def validate_form_data(form_id: str, max_responses: int = 5) -> bool:
    """Test get_form_data() function."""
    print(f"\n--- Test 3: get_form_data(max_responses={max_responses}) ---")
    
    try:
        data = get_form_data(form=form_id, max_responses=max_responses)
        
        # Check required fields
        required = ["title", "description", "responseCount", "questions", "summary", "responses"]
        missing = [f for f in required if f not in data]
        if missing:
            print(f"❌ Missing fields: {missing}")
            return False
        
        print(f"✅ get_form_data: Success")
        print(f"   Title:           {data['title']}")
        print(f"   Response count:  {data['responseCount']}")
        print(f"   Questions:       {len(data['questions'])}")
        print(f"   Responses fetched: {len(data['responses'])}")
        
        # Validate questions structure
        if data['questions']:
            q = data['questions'][0]
            q_fields = ["id", "title", "type"]
            for field in q_fields:
                if field not in q:
                    print(f"❌ Question missing field: {field}")
                    return False
            print(f"   First question: {q['title'][:50]}... (type: {q['type']})")
        
        # Validate responses structure
        if data['responses']:
            r = data['responses'][0]
            if "id" not in r:
                print("❌ Response missing 'id'")
                return False
            if "submitDate" not in r:
                print("❌ Response missing 'submitDate'")
                return False
            
            # Count answer fields
            answer_keys = [k for k in r.keys() if k not in ("id", "submitDate", "responder")]
            print(f"   First response: {len(answer_keys)} answer fields")
        
        return True
        
    except Exception as e:
        print(f"❌ get_form_data failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_parsing_offline():
    """Test parsing logic without network calls."""
    from servers.msforms import _parse_answers, _parse_question_info
    
    print("\n--- Test 0: Offline parsing tests ---")
    
    # Test double-encoded answers
    answers_json = '[{"answer1":"Yes","questionId":"q1"},{"answer1":"[\\"A\\",\\"B\\"]","questionId":"q2"}]'
    parsed = _parse_answers(answers_json)
    
    assert len(parsed) == 2, f"Expected 2 answers, got {len(parsed)}"
    assert parsed[0]["answer"] == "Yes", f"Expected 'Yes', got {parsed[0]['answer']}"
    assert parsed[1]["answer"] == ["A", "B"], f"Expected ['A','B'], got {parsed[1]['answer']}"
    
    print("✅ Answer parsing: correct")
    
    # Test question info parsing
    q_info_json = '{"Choices":[{"DisplayText":"Option A"},{"DisplayText":"Option B"}]}'
    q_info = _parse_question_info(q_info_json)
    
    assert "Choices" in q_info, "Expected Choices in parsed question info"
    assert len(q_info["Choices"]) == 2, f"Expected 2 choices"
    
    print("✅ Question info parsing: correct")
    
    return True


def main():
    print("\n" + "=" * 60)
    print("MS Forms MCP Server Test Suite")
    print("=" * 60)
    
    # Load credentials from config file
    load_credentials_from_config()
    
    # Always run offline tests
    test_parsing_offline()
    
    # Check for form_id
    if len(sys.argv) > 1:
        form_id = sys.argv[1]
    else:
        # Default test form
        form_id = os.environ.get("MS_FORMS_FORM_ID", "")
    
    if not form_id:
        print("\n⚠️  No form_id provided. Skipping live API tests.")
        print("\nUsage: python tests/test_msforms_schema.py <form_id>")
        print("\nExample:")
        print("  python tests/test_msforms_schema.py v4j5cvGGr0GRqy180BHbR...")
        return 0
    
    # Check for credentials
    token = os.environ.get("MS_FORMS_TOKEN", "")
    cookies = os.environ.get("MS_FORMS_COOKIES", "")
    
    if not token:
        print("\n⚠️  MS_FORMS_TOKEN not set. Skipping live API tests.")
        return 0
    
    if not cookies:
        print("\n⚠️  MS_FORMS_COOKIES not set. API calls may fail with 401.")
    
    print(f"\nForm ID: {form_id[:30]}...")
    
    # Run all tests
    results = []
    
    results.append(("decode_form_id", validate_decode_form(form_id)))
    results.append(("get_form_summary", validate_form_summary(form_id)))
    results.append(("get_form_data", validate_form_data(form_id, max_responses=5)))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Results:")
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    print("=" * 60)
    
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
