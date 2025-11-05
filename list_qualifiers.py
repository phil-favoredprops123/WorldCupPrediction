#!/usr/bin/env python3
"""
List all World Cup qualifier competitions available in Football-Data.org
"""

import requests
import json

def main():
    # Load API key from config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    api_key = config.get('api_keys', {}).get('football_data')
    
    if not api_key or api_key == 'YOUR_FOOTBALL_DATA_API_KEY':
        print("Please add your Football-Data.org API key to config.json")
        return
    
    headers = {"X-Auth-Token": api_key}
    url = "https://api.football-data.org/v4/competitions"
    
    print("=== Fetching Competitions ===\n")
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        competitions = response.json()
        
        print(f"Total competitions available: {len(competitions.get('competitions', []))}\n")
        
        # Categorize competitions
        qualifiers = {
            'UEFA': [],
            'CONMEBOL': [],
            'CONCACAF': [],
            'AFC': [],
            'CAF': [],
            'OFC': [],
            'Other': []
        }
        
        for comp in competitions.get('competitions', []):
            name = comp.get('name', '').lower()
            code = comp.get('code', '')
            area = comp.get('area', {}).get('name', '')
            
            # Check if it's a qualifier
            is_qualifier = 'qualif' in name or 'qualifying' in name or 'wcq' in code.lower()
            
            if is_qualifier or 'world cup' in name:
                if 'europe' in area.lower() or 'uefa' in area.lower():
                    qualifiers['UEFA'].append(comp)
                elif 'america' in area.lower():
                    if 'south' in area.lower() or 'conmebol' in area.lower():
                        qualifiers['CONMEBOL'].append(comp)
                    else:
                        qualifiers['CONCACAF'].append(comp)
                elif 'asia' in area.lower() or 'afc' in area.lower():
                    qualifiers['AFC'].append(comp)
                elif 'africa' in area.lower() or 'caf' in area.lower():
                    qualifiers['CAF'].append(comp)
                elif 'oceania' in area.lower() or 'ofc' in area.lower():
                    qualifiers['OFC'].append(comp)
                else:
                    qualifiers['Other'].append(comp)
        
        # Print findings
        for conf, comps in qualifiers.items():
            if comps:
                print(f"\n=== {conf} ===")
                for comp in comps:
                    print(f"  {comp['name']}")
                    print(f"    Code: {comp['code']}")
                    print(f"    Area: {comp.get('area', {}).get('name', 'N/A')}")
                    print(f"    Current Season: {comp.get('currentSeason', {}).get('startDate', 'N/A')} - {comp.get('currentSeason', {}).get('endDate', 'N/A')}")
                    print()
        
        # Save to file
        with open('qualifier_competitions.json', 'w') as f:
            json.dump(qualifiers, f, indent=2, default=str)
        
        print("=== Saved to qualifier_competitions.json ===\n")
        
        # Provide next steps
        print("=== Next Steps ===")
        print("1. Review the competitions above")
        print("2. Update qualifier_data_fetcher.py with correct competition codes")
        print("3. Run: python qualifier_data_fetcher.py")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

