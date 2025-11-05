#!/usr/bin/env python3
"""
Show all available competitions in Football-Data.org API
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
    
    print("=== All Available Competitions ===\n")
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        competitions = response.json()
        
        print(f"Total competitions: {len(competitions.get('competitions', []))}\n")
        
        for i, comp in enumerate(competitions.get('competitions', []), 1):
            print(f"{i}. {comp['name']}")
            print(f"   Code: {comp['code']}")
            print(f"   Area: {comp.get('area', {}).get('name', 'N/A')}")
            print(f"   Type: {comp.get('type', 'N/A')}")
            print(f"   Current Season: {comp.get('currentSeason', {}).get('startDate', 'N/A')} - {comp.get('currentSeason', {}).get('endDate', 'N/A')}")
            print()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

