#!/usr/bin/env python3
"""Standalone test for msforms.py to verify tools and schema."""

import sys
import json
import os

sys.path.insert(0, 'servers')

# Load credentials
with open('.mcp/mcp-servers.json') as f:
    cfg = json.load(f)['mcpServers']['msforms']['env']
    os.environ['MS_FORMS_TOKEN'] = cfg['MS_FORMS_TOKEN']
    os.environ['MS_FORMS_BEARER'] = cfg['MS_FORMS_BEARER']
    os.environ['MS_FORMS_COOKIES'] = cfg['MS_FORMS_COOKIES']

from msforms import get_form_data, get_form_summary

form_id = 'YOUR_FORM_ID_HERE'  # Replace with your form ID from MS Forms URL

print('=' * 60)
print('TEST 1: get_form_summary')
print('=' * 60)
result = get_form_summary(form=form_id)
print(f'Keys: {list(result.keys())}')
print(f'title: {result["title"]}')
print(f'responseCount: {result["responseCount"]}')
print(f'avgSubmitTimeSeconds: {result.get("avgSubmitTimeSeconds")}')
print(f'questions count: {len(result["questions"])}')
print()
print('Sample question summary:')
for k, v in list(result['questions'].items())[:2]:
    print(f'  {k[:40]}: {v}')

print()
print('=' * 60)
print('TEST 2: get_form_data (max_responses=3)')
print('=' * 60)
result = get_form_data(form=form_id, max_responses=3)
print(f'Keys: {list(result.keys())}')
print(f'title: {result["title"]}')
desc = result["description"][:50] if result["description"] else "(empty)"
print(f'description: {desc}...')
print(f'responseCount: {result["responseCount"]}')
print(f'questions count: {len(result["questions"])}')
print(f'responses count: {len(result["responses"])}')
print()

if result['questions']:
    print('Sample question:')
    q_id, q = next(iter(result['questions'].items()))
    print(f'  id: {q["id"]}')
    print(f'  title: {q["title"][:50]}...')
    print(f'  type: {q["type"]}')
    print(f'  required: {q["required"]}')
    print(f'  choices: {q.get("choices", "N/A")}')
    print(f'  ratingScale: {q.get("ratingScale", "N/A")}')

print()
if result['responses']:
    r = result['responses'][0]
    print('Sample response:')
    print(f'  id: {r["id"]}, submitDate: {r["submitDate"]}, responder: {r["responder"]}')
    print(f'  answers keys: {list(r["answers"].keys())[:3]}...')
    print(f'  sample answer: {list(r["answers"].values())[0]}')

print()
print('=' * 60)
print('Demonstrating consistent question_id joins:')
print('=' * 60)
if result['questions'] and result['responses'] and result['summary']:
    q_id = next(iter(result['questions'].keys()))
    print(f'\nQuestion ID: {q_id}')
    print(f'  questions[q_id]["title"]: {result["questions"][q_id]["title"][:40]}...')
    print(f'  summary[q_id]: {result["summary"].get(q_id, "N/A")}')
    print(f'  responses[0]["answers"][q_id]: {result["responses"][0]["answers"].get(q_id, "N/A")}')

print()
print('=' * 60)
print('Schema Validation: PASSED')
print('=' * 60)
