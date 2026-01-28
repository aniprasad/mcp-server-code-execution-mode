#!/usr/bin/env python3
"""
Comprehensive test suite for sports.py MCP server.
Tests all sports, tools, and schema validation.
"""

import sys
sys.path.insert(0, 'servers')

import asyncio
import json
from schemas import GameInfo, StandingEntry, NewsArticle, SportInfo, RankingEntry

# Import the sports module
import sports


def validate_game_schema(game: dict) -> bool:
    """Validate game dict matches GameInfo schema."""
    required = ['home_team', 'away_team', 'home_score', 'away_score', 'status', 'sport']
    return all(k in game for k in required)


def validate_standing_schema(standing: dict) -> bool:
    """Validate standing dict matches StandingEntry schema."""
    required = ['rank', 'team', 'wins', 'losses', 'pct']
    return all(k in standing for k in required)


def validate_ranking_schema(ranking: dict) -> bool:
    """Validate ranking dict matches RankingEntry schema."""
    required = ['rank', 'team', 'abbreviation']
    return all(k in ranking for k in required)


async def test_list_sports():
    """Test list_sports returns all categories."""
    print("\n--- TEST: list_sports() ---")
    r = await sports.list_sports()
    
    categories = list(r['sports'].keys())
    expected_categories = ['Football', 'Basketball', 'Baseball & Hockey', 'Soccer', 'Tennis', 'Golf', 'Motorsport']
    
    total = sum(len(v) for v in r['sports'].values())
    
    print(f"  Categories: {len(categories)} -> {categories}")
    print(f"  Total sports: {total}")
    
    # Validate each sport has code and name
    all_valid = True
    for cat, sport_list in r['sports'].items():
        for sport in sport_list:
            if 'code' not in sport or 'name' not in sport:
                print(f"  ❌ Invalid sport entry in {cat}: {sport}")
                all_valid = False
    
    if all_valid and total >= 23:
        print("  ✅ list_sports PASSED")
        return True
    else:
        print("  ❌ list_sports FAILED")
        return False


async def test_scoreboards():
    """Test scoreboard for all sports."""
    print("\n--- TEST: scoreboard (all sports) ---")
    
    all_sports = [
        'nfl', 'nba', 'wnba', 'mlb', 'nhl', 'ncaaf', 'ncaab', 'wncaab',
        'collegebaseball', 'cfl', 'xfl', 'mls', 'epl', 'laliga', 'bundesliga',
        'seriea', 'ligue1', 'ucl', 'atp', 'wta', 'pga', 'lpga', 'f1'
    ]
    
    passed = 0
    failed = 0
    
    for sport in all_sports:
        try:
            r = await sports.get_scoreboard(sport)
            games_count = r.get('games_count', 0)
            
            # Validate schema if there are games
            schema_valid = True
            if games_count > 0 and 'games' in r:
                schema_valid = validate_game_schema(r['games'][0])
            
            if schema_valid:
                print(f"  ✅ {sport:15} OK - {games_count} games")
                passed += 1
            else:
                print(f"  ⚠️  {sport:15} Schema mismatch")
                failed += 1
        except Exception as e:
            print(f"  ❌ {sport:15} FAIL - {e}")
            failed += 1
    
    print(f"\n  Scoreboard Results: {passed}/{len(all_sports)} passed")
    return failed == 0


async def test_standings():
    """Test standings for select sports."""
    print("\n--- TEST: standings ---")
    
    # Sports with standings support
    test_sports = ['nfl', 'nba', 'mlb', 'nhl', 'epl']
    
    passed = 0
    for sport in test_sports:
        try:
            r = await sports.get_standings(sport)
            teams = r.get('teams_count', 0)
            
            schema_valid = True
            if teams > 0 and 'standings' in r:
                schema_valid = validate_standing_schema(r['standings'][0])
            
            if schema_valid:
                print(f"  ✅ {sport:10} OK - {teams} teams")
                passed += 1
            else:
                print(f"  ⚠️  {sport:10} Schema mismatch")
        except Exception as e:
            print(f"  ❌ {sport:10} FAIL - {e}")
    
    print(f"\n  Standings Results: {passed}/{len(test_sports)} passed")
    return passed == len(test_sports)


async def test_team_schedule():
    """Test team schedule lookup."""
    print("\n--- TEST: team_schedule ---")
    
    tests = [
        ('nba', 'lakers'),
        ('nfl', 'patriots'),
        ('epl', 'chelsea'),
    ]
    
    passed = 0
    for sport, team in tests:
        try:
            r = await sports.get_team_schedule(sport, team)
            if 'error' in r:
                print(f"  ⚠️  {sport}/{team}: {r['error']}")
            else:
                games = r.get('games_count', 0)
                print(f"  ✅ {sport}/{team}: {r.get('team')} - {games} games")
                passed += 1
        except Exception as e:
            print(f"  ❌ {sport}/{team}: FAIL - {e}")
    
    print(f"\n  Team Schedule Results: {passed}/{len(tests)} passed")
    return passed >= 2  # Allow 1 failure due to API variability


async def test_news():
    """Test news headlines."""
    print("\n--- TEST: news ---")
    
    test_sports = ['nba', 'nfl', 'epl']
    
    passed = 0
    for sport in test_sports:
        try:
            r = await sports.get_news(sport, limit=2)
            articles = r.get('articles_count', 0)
            
            if articles > 0:
                # Validate schema
                article = r['articles'][0]
                if 'headline' in article and 'link' in article:
                    print(f"  ✅ {sport:10} OK - {articles} articles")
                    passed += 1
                else:
                    print(f"  ⚠️  {sport:10} Schema mismatch")
            else:
                print(f"  ⚠️  {sport:10} No articles")
                passed += 1  # API may just have no news
        except Exception as e:
            print(f"  ❌ {sport:10} FAIL - {e}")
    
    print(f"\n  News Results: {passed}/{len(test_sports)} passed")
    return passed == len(test_sports)


async def test_rankings():
    """Test rankings for college sports."""
    print("\n--- TEST: rankings ---")
    
    tests = [
        ('ncaaf', 'ap'),
        ('ncaaf', 'coaches'),
        ('ncaab', None),
    ]
    
    passed = 0
    for sport, poll in tests:
        try:
            r = await sports.get_rankings(sport, poll=poll, limit=5)
            polls_count = r.get('polls_count', 0)
            
            if polls_count > 0:
                first_poll = r['polls'][0]
                teams = first_poll.get('teams_count', 0)
                
                # Validate schema
                if teams > 0 and validate_ranking_schema(first_poll['teams'][0]):
                    poll_name = poll or 'all'
                    print(f"  ✅ {sport}/{poll_name:10} OK - {polls_count} polls, {teams} teams")
                    passed += 1
                else:
                    print(f"  ⚠️  {sport}/{poll} Schema mismatch")
            else:
                print(f"  ⚠️  {sport}/{poll} No polls")
        except Exception as e:
            print(f"  ❌ {sport}/{poll} FAIL - {e}")
    
    # Test unsupported sport
    try:
        r = await sports.get_rankings('nba')
        if 'error' in r:
            print(f"  ✅ nba/rankings correctly rejected: {r['error'][:40]}...")
            passed += 1
    except Exception as e:
        print(f"  ❌ nba/rankings error handling FAIL")
    
    print(f"\n  Rankings Results: {passed}/{len(tests)+1} passed")
    return passed >= 3


async def main():
    print("=" * 60)
    print("SPORTS.PY COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    
    results = []
    
    results.append(("list_sports", await test_list_sports()))
    results.append(("scoreboards", await test_scoreboards()))
    results.append(("standings", await test_standings()))
    results.append(("team_schedule", await test_team_schedule()))
    results.append(("news", await test_news()))
    results.append(("rankings", await test_rankings()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name:20} {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
