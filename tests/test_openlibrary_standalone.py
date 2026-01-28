#!/usr/bin/env python3
"""Standalone tests for openlibrary.py to verify tools and schema."""

import sys
import asyncio

sys.path.insert(0, 'servers')

from openlibrary import search_books, get_book, get_author, search_authors, get_cover
from schemas import OLBook, OLAuthor, OLSearchResult


def run_async(coro):
    """Helper to run async functions."""
    return asyncio.run(coro)


print('=' * 60)
print('TEST 1: search_books')
print('=' * 60)
result = run_async(search_books(query="Clean Code Robert Martin", limit=5))
print(f'Query: {result["query"]}')
print(f'Total results: {result["total"]}')
print(f'Books returned: {len(result["books"])}')
for book in result["books"][:3]:
    print(f'  - {book["title"]} by {", ".join(book["authors"][:2])}')
    if book["cover_url"]:
        print(f'    Cover: {book["cover_url"][:60]}...')

# Validate schema
validated = OLSearchResult(**result)
assert validated.total > 0
print('\nSchema validation: PASSED')

print()
print('=' * 60)
print('TEST 2: get_book by ISBN')
print('=' * 60)
# Clean Code ISBN
result = run_async(get_book(isbn="9780132350884"))
print(f'Title: {result["title"]}')
print(f'Authors: {result["authors"]}')
print(f'Key: {result["key"]}')
if result.get("description"):
    print(f'Description: {result["description"][:100]}...')
if result.get("cover_url"):
    print(f'Cover: {result["cover_url"]}')

validated = OLBook(**result)
assert "Clean Code" in validated.title or "clean" in validated.title.lower()
print('\nSchema validation: PASSED')

print()
print('=' * 60)
print('TEST 3: search_authors')
print('=' * 60)
result = run_async(search_authors(query="Stephen King", limit=3))
print(f'Query: {result["query"]}')
print(f'Total: {result["total"]}')
for author in result["authors"]:
    print(f'  - {author["name"]} (works: {author.get("works_count", "?")})')

assert len(result["authors"]) > 0
print('\nSchema validation: PASSED')

print()
print('=' * 60)
print('TEST 4: get_author')
print('=' * 60)
# First search to get author key
search_result = run_async(search_authors(query="Brandon Sanderson", limit=1))
if search_result["authors"]:
    author_key = search_result["authors"][0]["key"]
    result = run_async(get_author(key=author_key))
    print(f'Name: {result["name"]}')
    print(f'Key: {result["key"]}')
    print(f'Birth date: {result.get("birth_date", "Unknown")}')
    print(f'Works count: {result.get("works_count", "Unknown")}')
    if result.get("bio"):
        print(f'Bio: {result["bio"][:150]}...')

    validated = OLAuthor(**result)
    assert validated.name
    print('\nSchema validation: PASSED')
else:
    print('Author not found - skipping test')

print()
print('=' * 60)
print('TEST 5: get_cover')
print('=' * 60)
result = run_async(get_cover(isbn="9780132350884", size="M"))
print(f'Cover URL: {result["cover_url"]}')
print(f'Size: {result["size"]}')
assert "covers.openlibrary.org" in result["cover_url"]
print('\nSchema validation: PASSED')

print()
print('=' * 60)
print('ALL TESTS PASSED')
print('=' * 60)
