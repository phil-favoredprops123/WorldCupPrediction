#!/usr/bin/env python3
"""
Diagnostic script to understand why qualifier leagues aren't being found
"""

import requests
import json
import time

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

api_key = config.get('api_keys', {}).get('api_football', '')
if not api_key:
    print("ERROR: API-Football key not found in config.json")
    exit(1)

headers = {'x-rapidapi-key': api_key, 'x-rapidapi-host': 'api-football-v1.p.rapidapi.com'}
base_url = 'https://api-football-v1.p.rapidapi.com/v3'

print("=" * 80)
print("DIAGNOSING QUALIFIER LEAGUE DETECTION ISSUES")
print("=" * 80)

# Test 1: Check what seasons have data
print("\n1. Testing available seasons:")
for season in [2026, 2025, 2024, 2023, 2022]:
    try:
        url = f'{base_url}/leagues'
        params = {'season': season}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            count = len(data.get('response', []))
            print(f"  Season {season}: {count} leagues available")
        elif response.status_code == 429:
            print(f"  Season {season}: Rate limited (429)")
        elif response.status_code == 403:
            print(f"  Season {season}: Forbidden (403) - check API key")
        else:
            print(f"  Season {season}: HTTP {response.status_code}")
        time.sleep(0.5)
    except Exception as e:
        print(f"  Season {season}: Error - {e}")

# Test 2: Search for qualifier-related leagues in a season that works
print("\n2. Searching for qualifier-related leagues in season 2023:")
try:
    url = f'{base_url}/leagues'
    params = {'season': 2023}
    response = requests.get(url, headers=headers, params=params, timeout=10)
    if response.status_code == 200:
        data = response.json()
        leagues = data.get('response', [])
        
        # Find all leagues with qualifier-related terms
        qualifier_keywords = ['qualif', 'world cup', 'wcq', 'wc qualification']
        found_qualifiers = []
        
        for league_info in leagues:
            league = league_info.get('league', {})
            name = league.get('name', '').lower()
            country = league_info.get('country', {}).get('name', '')
            
            # Check if it contains any qualifier keyword
            if any(keyword in name for keyword in qualifier_keywords):
                found_qualifiers.append({
                    'id': league.get('id'),
                    'name': league.get('name'),
                    'country': country,
                    'type': league.get('type', '')
                })
        
        print(f"  Found {len(found_qualifiers)} leagues with qualifier keywords:")
        for q in found_qualifiers[:20]:  # Show first 20
            print(f"    - {q['name']} ({q['country']}) [ID: {q['id']}, Type: {q['type']}]")
        
        # Group by confederation
        print("\n  By confederation:")
        confederations = {}
        for q in found_qualifiers:
            name_lower = q['name'].lower()
            conf = 'Unknown'
            if 'uefa' in name_lower or 'europe' in name_lower:
                conf = 'UEFA'
            elif 'conmebol' in name_lower or 'south america' in name_lower:
                conf = 'CONMEBOL'
            elif 'concacaf' in name_lower or 'north america' in name_lower:
                conf = 'CONCACAF'
            elif 'afc' in name_lower or 'asia' in name_lower:
                conf = 'AFC'
            elif 'caf' in name_lower or 'africa' in name_lower:
                conf = 'CAF'
            elif 'ofc' in name_lower or 'oceania' in name_lower:
                conf = 'OFC'
            
            if conf not in confederations:
                confederations[conf] = []
            confederations[conf].append(q['name'])
        
        for conf, leagues_list in confederations.items():
            print(f"    {conf}: {len(leagues_list)} leagues")
            for league_name in leagues_list[:5]:  # Show first 5 per confederation
                print(f"      - {league_name}")
        
    elif response.status_code == 429:
        print("  Rate limited - cannot search")
    else:
        print(f"  HTTP {response.status_code}")
except Exception as e:
    print(f"  Error: {e}")

# Test 3: Check the actual filtering logic
print("\n3. Testing filtering logic:")
print("  Current filter requires:")
print("    - 'world cup' AND 'qualif' in name, OR")
print("    - 'wc qualification' or 'wcq' pattern, OR")
print("    - 'qualification' + confederation keyword")
print("\n  This might be TOO STRICT for some API naming conventions")
print("\n  Suggestion: Relax the filter to also include leagues that:")
print("    - Have 'qualification' in name AND are from a confederation country")
print("    - Are named 'WCQ' or similar abbreviations")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("The issue is likely:")
print("1. API-Football may not have qualifiers in 2024-2026 seasons yet")
print("2. The filtering logic is too strict (requires specific keywords)")
print("3. Confederation detection depends on keywords in league name")
print("4. Rate limiting may prevent data collection")
print("\nRecommendation: Test with season 2023 to see what's available,")
print("then adjust the filter logic to be more flexible.")

