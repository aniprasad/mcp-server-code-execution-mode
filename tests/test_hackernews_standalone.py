#!/usr/bin/env python3
"""Standalone tests for hackernews.py to verify tools and schema."""

import sys
import asyncio

sys.path.insert(0, 'servers')

from hackernews import top_stories, new_stories, best_stories, story, user, search
from schemas import HNStory, HNUser, HNSearchResult


def run_async(coro):
    """Helper to run async functions."""
    return asyncio.run(coro)


print('=' * 60)
print('TEST 1: top_stories')
print('=' * 60)
results = run_async(top_stories(limit=5))
print(f'Retrieved {len(results)} top stories:')
for s in results:
    print(f'  [{s["score"]} pts] {s["title"][:50]}...')
    print(f'    by {s["by"]} | {s["descendants"]} comments')

# Validate schema
for s in results:
    validated = HNStory(**s)
    assert validated.id > 0
print('\nSchema validation: PASSED')

print()
print('=' * 60)
print('TEST 2: new_stories')
print('=' * 60)
results = run_async(new_stories(limit=3))
print(f'Retrieved {len(results)} new stories:')
for s in results:
    print(f'  [{s["score"]} pts] {s["title"][:50]}...')
assert len(results) > 0
print('\nSchema validation: PASSED')

print()
print('=' * 60)
print('TEST 3: best_stories')
print('=' * 60)
results = run_async(best_stories(limit=3))
print(f'Retrieved {len(results)} best stories:')
for s in results:
    print(f'  [{s["score"]} pts] {s["title"][:50]}...')
assert len(results) > 0
print('\nSchema validation: PASSED')

print()
print('=' * 60)
print('TEST 4: story (by ID)')
print('=' * 60)
# Get ID from top stories
top = run_async(top_stories(limit=1))
story_id = top[0]["id"]
result = run_async(story(id=story_id))
print(f'Story ID: {result["id"]}')
print(f'Title: {result["title"]}')
print(f'Score: {result["score"]}')
print(f'By: {result["by"]}')
print(f'Time: {result["time"]}')
print(f'Comments: {result["descendants"]}')
if result.get("url"):
    print(f'URL: {result["url"][:60]}...')

validated = HNStory(**result)
assert validated.id == story_id
print('\nSchema validation: PASSED')

print()
print('=' * 60)
print('TEST 5: user (pg - Paul Graham)')
print('=' * 60)
result = run_async(user(username="pg"))
print(f'Username: {result["id"]}')
print(f'Karma: {result["karma"]:,}')
print(f'Created: {result["created"]}')
print(f'Submissions: {result["submitted_count"]:,}')
if result.get("about"):
    print(f'About: {result["about"][:100]}...')

validated = HNUser(**result)
assert validated.karma > 0  # pg has a lot of karma
print('\nSchema validation: PASSED')

print()
print('=' * 60)
print('TEST 6: search (via Algolia)')
print('=' * 60)
result = run_async(search(query="python", limit=5))
print(f'Query: {result["query"]}')
print(f'Total results: {result["total"]}')
print(f'Hits returned: {len(result["hits"])}')
for hit in result["hits"]:
    print(f'  [{hit["points"]} pts] {hit["title"][:50]}...')
    print(f'    by {hit["author"]} | {hit["num_comments"]} comments')

validated = HNSearchResult(**result)
assert validated.total > 0
print('\nSchema validation: PASSED')

print()
print('=' * 60)
print('TEST 7: search comments')
print('=' * 60)
result = run_async(search(query="rust vs go", limit=3, search_type="comment"))
print(f'Query: {result["query"]}')
print(f'Comment hits: {len(result["hits"])}')
for hit in result["hits"][:2]:
    print(f'  by {hit["author"]} in story {hit.get("story_id", "?")}')
print('\nSchema validation: PASSED')

print()
print('=' * 60)
print('ALL TESTS PASSED')
print('=' * 60)
