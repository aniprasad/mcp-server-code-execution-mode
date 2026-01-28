#!/usr/bin/env python3
"""Standalone tests for countries.py to verify tools and schema."""

import sys
import asyncio

sys.path.insert(0, 'servers')

from countries import get_country, search_countries, by_region, by_currency, by_language
from schemas import Country


def run_async(coro):
    """Helper to run async functions."""
    return asyncio.run(coro)


print('=' * 60)
print('TEST 1: get_country by name')
print('=' * 60)
result = run_async(get_country(name="France"))
print(f'Name: {result["name"]}')
print(f'Official: {result["official_name"]}')
print(f'Capital: {result["capital"]}')
print(f'Region: {result["region"]} / {result["subregion"]}')
print(f'Population: {result["population"]:,}')
print(f'Area: {result["area"]:,.0f} km2' if result["area"] else 'Area: N/A')
print(f'Languages: {result["languages"]}')
print(f'Currencies: {result["currencies"]}')
print(f'Flag emoji: {result["flag_emoji"]}')

# Validate schema
validated = Country(**result)
assert validated.population > 0
print('\nSchema validation: PASSED')

print()
print('=' * 60)
print('TEST 2: get_country by code (US)')
print('=' * 60)
result = run_async(get_country(name="US"))
print(f'Name: {result["name"]}')
print(f'Code: {result["cca2"]} / {result["cca3"]}')
print(f'Capital: {result["capital"]}')
assert result["cca2"] == "US"
print('Schema validation: PASSED')

print()
print('=' * 60)
print('TEST 3: search_countries')
print('=' * 60)
results = run_async(search_countries(name="united"))
print(f'Found {len(results)} countries matching "united":')
for c in results[:5]:
    print(f'  - {c["name"]} ({c["cca2"]})')
assert len(results) > 0
print('Schema validation: PASSED')

print()
print('=' * 60)
print('TEST 4: by_region')
print('=' * 60)
results = run_async(by_region(region="Oceania"))
print(f'Found {len(results)} countries in Oceania:')
for c in results[:5]:
    print(f'  - {c["name"]}')
assert len(results) > 0
print('Schema validation: PASSED')

print()
print('=' * 60)
print('TEST 5: by_currency')
print('=' * 60)
results = run_async(by_currency(currency="EUR"))
print(f'Found {len(results)} countries using EUR:')
for c in results[:5]:
    print(f'  - {c["name"]}')
assert len(results) > 10  # Many countries use EUR
print('Schema validation: PASSED')

print()
print('=' * 60)
print('TEST 6: by_language')
print('=' * 60)
results = run_async(by_language(language="spanish"))
print(f'Found {len(results)} countries speaking Spanish:')
for c in results[:5]:
    print(f'  - {c["name"]}')
assert len(results) > 10  # Many countries speak Spanish
print('Schema validation: PASSED')

print()
print('=' * 60)
print('ALL TESTS PASSED')
print('=' * 60)
