#!/usr/bin/env python3
"""Test msforms with the updated $expand parameter."""
import sys
import json
import os

sys.path.insert(0, 'servers')

# Load credentials
with open('.mcp/mcp-servers.json') as f:
    cfg = json.load(f)['mcpServers']['msforms']['env']
    for k, v in cfg.items():
        os.environ[k] = v

from msforms import get_form_data

FORM_ID = "YOUR_FORM_ID_HERE"  # Replace with your form ID from MS Forms URL

print("=" * 60)
print("Testing get_form_data with $expand=questions")
print("=" * 60)
result = get_form_data(FORM_ID, max_responses=1)

print(f"\nForm: {result.get('title', 'N/A')}")
print(f"Response Count: {result.get('responseCount', 'N/A')}")

questions = result.get('questions', [])
print(f"\nQuestions ({len(questions)}):")
for i, q in enumerate(questions, 1):
    title = q.get('title', 'N/A')
    title_preview = title[:60] + '...' if len(title) > 60 else title
    print(f"  {i}. [{q.get('type', 'N/A')}] {title_preview}")
    if q.get('choices'):
        choices_preview = q['choices'][:3]
        suffix = '...' if len(q.get('choices', [])) > 3 else ''
        print(f"      Choices: {choices_preview}{suffix}")
    if q.get('ratingScale'):
        print(f"      Rating Scale: 1-{q['ratingScale']}")

print("\n" + "=" * 60)
if len(questions) > 0:
    print("✅ SUCCESS - Questions are now populated!")
else:
    print("❌ FAILURE - Questions still empty")
print("=" * 60)
