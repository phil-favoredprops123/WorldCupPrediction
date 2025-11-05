#!/usr/bin/env python3
"""
Fetch World Cup qualifier data from API-Football via RapidAPI
and update team probabilities accordingly

API-Football covers +1,100 leagues and cups including World Cup qualifiers
More comprehensive than Football-Data.org
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class APIFootballFetcher:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }
        self.base_url = "https://api-football-v1.p.rapidapi.com/v3"
        
        # World Cup qualifier league IDs (update based on API response)
        self.qualifier_league_ids = {
            'UEFA': None,      # Will be discovered
            'CONMEBOL': None,
            'CONCACAF': None,
            'AFC': None,
            'CAF': None,
            'OFC': None
        }
    
    def get_leagues(self, country=None, season=None):
        """Get all available leagues"""
        url = f"{self.base_url}/leagues"
        params = {}
        if country:
            params['country'] = country
        if season:
            params['season'] = season
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get('response', [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching leagues: {e}")
            return []
    
    def find_world_cup_qualifiers(self):
        """Find World Cup qualifier leagues"""
        logger.info("Searching for World Cup qualifier leagues...")
        
        # Search for qualifier leagues
        qualifiers = {
            'UEFA': [],
            'CONMEBOL': [],
            'CONCACAF': [],
            'AFC': [],
            'CAF': [],
            'OFC': []
        }
        
        # Search with different terms
        search_terms = ['World Cup Qualifying', 'WC Qualification', 'World Cup Qualifiers']
        
        for term in search_terms:
            leagues = self.get_leagues()
            
            for league in leagues:
                league_data = league.get('league', {})
                league_name = league_data.get('name', '').lower()
                country = league.get('country', {})
                country_name = country.get('name', '').lower()
                
                # Check if it's a qualifier
                if any([term.lower() in league_name for term in search_terms]):
                    # Categorize by region
                    if 'uefa' in league_name or 'europe' in league_name or country_name in ['europe', 'world']:
                        qualifiers['UEFA'].append({
                            'name': league_data.get('name'),
                            'id': league_data.get('id'),
                            'country': country.get('name'),
                            'type': league_data.get('type')
                        })
                    elif 'conmebol' in league_name or 'south america' in league_name:
                        qualifiers['CONMEBOL'].append({
                            'name': league_data.get('name'),
                            'id': league_data.get('id'),
                            'country': country.get('name')
                        })
                    elif 'concacaf' in league_name or 'north america' in league_name or 'central america' in league_name:
                        qualifiers['CONCACAF'].append({
                            'name': league_data.get('name'),
                            'id': league_data.get('id'),
                            'country': country.get('name')
                        })
                    elif 'afc' in league_name or 'asia' in league_name:
                        qualifiers['AFC'].append({
                            'name': league_data.get('name'),
                            'id': league_data.get('id'),
                            'country': country.get('name')
                        })
                    elif 'caf' in league_name or 'africa' in league_name:
                        qualifiers['CAF'].append({
                            'name': league_data.get('name'),
                            'id': league_data.get('id'),
                            'country': country.get('name')
                        })
                    elif 'ofc' in league_name or 'oceania' in league_name:
                        qualifiers['OFC'].append({
                            'name': league_data.get('name'),
                            'id': league_data.get('id'),
                            'country': country.get('name')
                        })
        
        return qualifiers
    
    def get_standings(self, league_id, season=2026):
        """Get current standings for a league"""
        url = f"{self.base_url}/standings"
        params = {'season': season, 'league': league_id}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get('response', [])
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error fetching standings for league {league_id}: {e}")
            return []
    
    def get_fixtures(self, league_id, season=2026, from_date=None, to_date=None):
        """Get fixtures/matches for a league"""
        url = f"{self.base_url}/fixtures"
        params = {'season': season, 'league': league_id}
        
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get('response', [])
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error fetching fixtures for league {league_id}: {e}")
            return []
    
    def calculate_team_probability(self, team_data, confederation):
        """Calculate probability for a team based on qualifier data"""
        prob = 0
        
        # Get team stats
        points = team_data.get('points', 0)
        position = team_data.get('rank', 100)
        played = team_data.get('all', {}).get('played', 0)
        goals_for = team_data.get('all', {}).get('goals', {}).get('for', 0)
        goals_against = team_data.get('all', {}).get('goals', {}).get('against', 0)
        goal_diff = goals_for - goals_against
        
        # Position-based probability
        if position <= 2:
            prob += 70
        elif position == 3:
            prob += 50
        elif position == 4:
            prob += 30
        elif position == 5:
            prob += 15
        else:
            prob += 5
        
        # Points-based adjustment
        if played > 0:
            points_per_game = points / played
            if points_per_game >= 2:
                prob += 15
            elif points_per_game >= 1.5:
                prob += 10
            elif points_per_game >= 1:
                prob += 5
            elif points_per_game < 0.5:
                prob -= 10
        
        # Goal difference adjustment
        if goal_diff > 10:
            prob += 10
        elif goal_diff > 5:
            prob += 5
        elif goal_diff < -5:
            prob -= 10
        
        # Form adjustment (API-Football provides form string)
        form = team_data.get('form', '')
        if form and len(form) >= 5:
            wins = form.count('W')
            win_rate = wins / 5
            if win_rate >= 0.8:
                prob += 10
            elif win_rate >= 0.6:
                prob += 5
            elif win_rate < 0.2:
                prob -= 10
        
        # Confederation strength multiplier
        conf_multipliers = {
            'UEFA': 1.0,
            'CONMEBOL': 1.0,
            'AFC': 0.95,
            'CAF': 0.95,
            'CONCACAF': 0.9,
            'OFC': 0.7
        }
        
        prob *= conf_multipliers.get(confederation, 1.0)
        
        return min(prob, 95)
    
    def fetch_and_process_all_qualifiers(self):
        """Fetch data for all confederations and process"""
        logger.info("Fetching qualifier data from API-Football...")
        
        # Find qualifier leagues
        qualifiers = self.find_world_cup_qualifiers()
        
        all_team_data = []
        date_from = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        date_to = datetime.now().strftime('%Y-%m-%d')
        
        for confederation, leagues in qualifiers.items():
            logger.info(f"Processing {confederation} qualifiers...")
            
            if not leagues:
                logger.warning(f"No qualifier leagues found for {confederation}")
                continue
            
            # Process each qualifier league
            for league in leagues:
                league_id = league['id']
                logger.info(f"  Fetching {league['name']} (ID: {league_id})...")
                
                # Get standings
                standings_response = self.get_standings(league_id)
                
                if not standings_response:
                    continue
                
                # Process standings
                for standings_group in standings_response:
                    standings_data = standings_group.get('league', {}).get('standings', [])
                    
                    # Handle different standings formats
                    if isinstance(standings_data, list) and len(standings_data) > 0:
                        # If list of lists (by group)
                        if isinstance(standings_data[0], list):
                            for group in standings_data:
                                for team_row in group:
                                    team_data = self.process_team_data(team_row, confederation, league['name'])
                                    if team_data:
                                        all_team_data.append(team_data)
                        else:
                            # Single flat list
                            for team_row in standings_data:
                                team_data = self.process_team_data(team_row, confederation, league['name'])
                                if team_data:
                                    all_team_data.append(team_data)
        
        return all_team_data
    
    def process_team_data(self, team_row, confederation, league_name):
        """Process individual team data"""
        team_info = team_row.get('team', {})
        team_name = team_info.get('name')
        
        if not team_name:
            return None
        
        # Check if it's a national team (not club)
        if self.is_club_team(team_name):
            return None
        
        # Calculate probability
        prob = self.calculate_team_probability(team_row, confederation)
        
        # Get group (if available)
        group = team_row.get('group', 'Overall')
        
        # Determine qualification status
        status = 'In Progress'
        if team_row.get('description') and 'Promotion' in team_row.get('description', ''):
            status = 'Qualified'
            prob = 100
        
        return {
            'team': team_name,
            'confederation': confederation,
            'qualification_status': status,
            'prob_fill_slot': round(prob, 1),
            'current_group': group,
            'position': team_row.get('rank'),
            'points': team_row.get('points'),
            'played': team_row.get('all', {}).get('played', 0),
            'goal_diff': team_row.get('all', {}).get('goals', {}).get('for', 0) - team_row.get('all', {}).get('goals', {}).get('against', 0),
            'form': team_row.get('form', '')
        }
    
    def is_club_team(self, team_name):
        """Check if team is a club (not national team)"""
        team_lower = team_name.lower()
        club_indicators = [
            ' fc', ' cf', ' sk', ' united', ' city', ' athletic', ' club',
            'real madrid', 'barcelona', 'bayern', 'paris saint', 'arsenal',
            'manchester', 'liverpool', 'chelsea', 'juventus', 'inter',
            'milan', 'dortmund', 'tottenham', 'napoli', 'atletico',
            'ajax', 'psv', 'psg', 'benfica', 'porto'
        ]
        return any([indicator in team_lower for indicator in club_indicators])
    
    def update_team_probabilities_csv(self):
        """Update team_slot_probabilities.csv with real qualifier data"""
        team_data = self.fetch_and_process_all_qualifiers()
        
        if not team_data:
            df = pd.DataFrame(team_data)
            df.to_csv('team_slot_probabilities.csv', index=False)
            logger.info(f"Updated team_slot_probabilities.csv with {len(df)} teams")
            
            with open('api_football_qualifier_data.json', 'w') as f:
                json.dump(team_data, f, indent=2)
            logger.info("Saved detailed data to api_football_qualifier_data.json")
            
            return df
        else:
            logger.error("No team data retrieved")
            return None

def main():
    # Load API key from config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Try API-Football key (RapidAPI)
    api_key = config.get('api_keys', {}).get('api_football')
    
    if not api_key or api_key == 'YOUR_API_FOOTBALL_KEY':
        print("Please add your API-Football (RapidAPI) key to config.json")
        print("Add it as: 'api_football': 'your-rapidapi-key'")
        return
    
    # Create fetcher and process
    fetcher = APIFootballFetcher(api_key)
    df = fetcher.update_team_probabilities_csv()
    
    if df is not None:
        print("\n=== Summary ===")
        print(f"Total teams: {len(df)}")
        print(f"Qualified: {len(df[df['qualification_status'] == 'Qualified'])}")
        print(f"In Progress: {len(df[df['qualification_status'] == 'In Progress'])}")
        
        print("\n=== Top Teams by Probability ===")
        top_teams = df.nlargest(20, 'prob_fill_slot')[['team', 'confederation', 'prob_fill_slot', 'qualification_status']]
        print(top_teams.to_string(index=False))

if __name__ == "__main__":
    import requests
    main()

