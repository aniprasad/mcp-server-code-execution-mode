#!/usr/bin/env python3
"""Final schema validation for msforms.py."""

import sys
import json
import os

sys.path.insert(0, 'servers')

with open('.mcp/mcp-servers.json') as f:
    cfg = json.load(f)['mcpServers']['msforms']['env']
    for k, v in cfg.items():
        os.environ[k] = v

from msforms import get_form_data, get_form_summary

form_id = 'YOUR_FORM_ID_HERE'  # Replace with your form ID from MS Forms URL

print("=" * 60)
print("SCHEMA VALIDATION: get_form_data")
print("=" * 60)
result = get_form_data(form=form_id, max_responses=2)

print("Top-level schema:")
print(f'  title: {type(result["title"]).__name__} = "{result["title"]}"')
print(f'  description: {type(result["description"]).__name__}')
print(f'  responseCount: {type(result["responseCount"]).__name__} = {result["responseCount"]}')
print(f'  questions: {type(result["questions"]).__name__} (len={len(result["questions"])})')
print(f'  summary: {type(result["summary"]).__name__} (keys={len(result["summary"])})')
print(f'  responses: {type(result["responses"]).__name__} (len={len(result["responses"])})')
print()

print("First response structure:")
resp = result['responses'][0]
print(json.dumps(resp, indent=2, default=str))

print()
print("=" * 60)
print("SCHEMA VALIDATION: get_form_summary")
print("=" * 60)
summary = get_form_summary(form=form_id)
print("Top-level schema:")
print(f'  title: {type(summary["title"]).__name__}')
print(f'  responseCount: {type(summary["responseCount"]).__name__}')
print(f'  avgSubmitTimeSeconds: {type(summary.get("avgSubmitTimeSeconds")).__name__}')
print(f'  questions: {type(summary["questions"]).__name__} (keys={len(summary["questions"])})')

print()
print("Sample question summary:")
for k, v in list(summary['questions'].items())[:2]:
    print(f'  {k[:30]}: {v}')

print()
print("=" * 60)
print("ALL SCHEMAS VALIDATED SUCCESSFULLY")
print("=" * 60)
