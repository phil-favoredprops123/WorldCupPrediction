#!/usr/bin/env python3
"""
Fetch data from Football-Data.org API for World Cup qualifiers
"""

import requests
import json
from datetime import datetime, timedelta
import json

class FootballDataFetcher:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {"X-Auth-Token": api_key}
        self.base_url = "https://api.football-data.org/v4"
    
    def get_competitions(self):
        """Get all available competitions"""
        url = f"{self.base_url}/competitions"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def find_world_cup_qualifiers(self):
        """Find World Cup qualifying competitions"""
        competitions = self.get_competitions()
        
        wc_qualifiers = []
        for comp in competitions.get('competitions', []):
            name = comp.get('name', '').lower()
            if 'world cup' in name or 'wc' in name or 'qual' in name:
                wc_qualifiers.append(comp)
        
        return wc_qualifiers
    
    def get_matches(self, competition_code, date_from=None, date_to=None):
        """Get matches for a competition"""
        url = f"{self.base_url}/competitions/{competition_code}/matches"
        params = {}
        
        if date_from:
            params['dateFrom'] = date_from
        if date_to:
            params['dateTo'] = date_to
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_standings(self, competition_code):
        """Get current standings for a competition"""
        url = f"{self.base_url}/competitions/{competition_code}/standings"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_team_matches(self, team_id, status='FINISHED'):
        """Get matches for a specific team"""
        url = f"{self.base_url}/teams/{team_id}/matches"
        params = {'status': status}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_recent_form(self, team_id, limit=5):
        """Get recent form for a team"""
        matches = self.get_team_matches(team_id, status='FINISHED')
        
        form = []
        for match in matches.get('matches', [])[:limit]:
            result = match.get('score', {}).get('winner')
            if result:
                form.append(result)
        
        return form

def main():
    # Load API key from config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    api_key = config.get('api_keys', {}).get('football_data')
    
    if not api_key or api_key == 'YOUR_FOOTBALL_DATA_API_KEY':
        print("Please add your Football-Data.org API key to config.json")
        return
    
    # Create fetcher
    fetcher = FootballDataFetcher(api_key)
    
    print("=== Fetching World Cup Qualifying Data ===\n")
    
    # Find qualifier competitions
    print("1. Finding World Cup qualifying competitions...")
    qualifiers = fetcher.find_world_cup_qualifiers()
    
    if qualifiers:
        print(f"   Found {len(qualifiers)} qualifying competitions:")
        for comp in qualifiers:
            print(f"   - {comp['name']} ({comp['code']})")
        
        # Get standings for first qualifier
        if qualifiers:
            comp_code = qualifiers[0]['code']
            print(f"\n2. Getting standings for {qualifiers[0]['name']}...")
            
            try:
                standings = fetcher.get_standings(comp_code)
                print(f"   Successfully retrieved standings")
                
                # Save to file
                with open('football_data_standings.json', 'w') as f:
                    json.dump(standings, f, indent=2)
                print(f"   Saved to football_data_standings.json")
                
            except Exception as e:
                print(f"   Error: {e}")
            
            # Get recent matches
            print(f"\n3. Getting recent matches...")
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            date_to = datetime.now().strftime('%Y-%m-%d')
            
            try:
                matches = fetcher.get_matches(comp_code, date_from, date_to)
                print(f"   Found {len(matches.get('matches', []))} matches in last 30 days")
                
                # Save to file
                with open('football_data_matches.json', 'w') as f:
                    json.dump(matches, f, indent=2)
                print(f"   Saved to football_data_matches.json")
                
            except Exception as e:
                print(f"   Error: {e}")
    else:
        print("   No qualifying competitions found")
        print("\n   Getting all available competitions...")
        all_competitions = fetcher.get_competitions()
        print(f"   Found {len(all_competitions.get('competitions', []))} total competitions")
        
        # Show some examples
        print("\n   Sample competitions:")
        for comp in all_competitions.get('competitions', [])[:10]:
            print(f"   - {comp['name']} ({comp['code']})")
    
    print("\n=== Done ===")

if __name__ == "__main__":
    import requests
    main()

