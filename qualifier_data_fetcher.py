#!/usr/bin/env python3
"""
Fetch qualifier data from Football-Data.org for all confederations
and update team probabilities accordingly

NOTE: Football-Data.org API has limited competition coverage.
We use UEFA European Championship qualifiers as a proxy for UEFA World Cup qualifiers
since the API doesn't provide separate World Cup qualifying data.
For other confederations, we may need to supplement with other data sources.
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QualifierDataFetcher:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {"X-Auth-Token": api_key}
        self.base_url = "https://api.football-data.org/v4"
        
        # Competition codes for World Cup qualifiers (football-data.org format)
        # Based on: https://www.football-data.org/coverage
        self.qualifier_codes = {
            'UEFA': 'WCQ_UEFA',  # WC Qualification UEFA - exists!
            'CONMEBOL': 'WCQ_CONMEBOL', 
            'CONCACAF': 'WCQ_CONCACAF',
            'AFC': 'WCQ_AFC',
            'CAF': 'WCQ_CAF',
            'OFC': 'WCQ_OFC'
        }
    
    def get_all_competitions(self):
        """Get all available competitions to find qualifier codes"""
        url = f"{self.base_url}/competitions"
        response = requests.get(url, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def find_qualifier_competitions(self):
        """Find World Cup qualifying competitions"""
        all_competitions = self.get_all_competitions()
        
        qualifiers = {
            'UEFA': [],
            'CONMEBOL': [],
            'CONCACAF': [],
            'AFC': [],
            'CAF': [],
            'OFC': []
        }
        
        # First, try to find direct WCQ competitions
        for comp in all_competitions.get('competitions', []):
            code = comp.get('code', '').upper()
            
            # Direct match to known WCQ codes
            if 'WCQ_UEFA' in code:
                qualifiers['UEFA'].append({'name': comp['name'], 'code': comp['code'], 'full': comp})
            elif 'WCQ_CONMEBOL' in code or 'SA' in code:
                qualifiers['CONMEBOL'].append({'name': comp['name'], 'code': comp['code'], 'full': comp})
            elif 'WCQ_CONCACAF' in code or 'NA' in code:
                qualifiers['CONCACAF'].append({'name': comp['name'], 'code': comp['code'], 'full': comp})
            elif 'WCQ_AFC' in code or 'AS' in code:
                qualifiers['AFC'].append({'name': comp['name'], 'code': comp['code'], 'full': comp})
            elif 'WCQ_CAF' in code or 'AF' in code:
                qualifiers['CAF'].append({'name': comp['name'], 'code': comp['code'], 'full': comp})
            elif 'WCQ_OFC' in code or 'OC' in code:
                qualifiers['OFC'].append({'name': comp['name'], 'code': comp['code'], 'full': comp})
        
        # If no direct WCQ found, use auto-discovery (fallback to Euros, etc.)
        
        for comp in all_competitions.get('competitions', []):
            name = comp.get('name', '').lower()
            code = comp.get('code', '')
            area = comp.get('area', {}).get('name', '').lower()
            
            # Only include national team competitions (exclude club competitions)
            is_club_competition = any([
                'champions league' in name,
                'europa league' in name,
                'conference league' in name,
                'club world cup' in name,
                'super cup' in name
            ])
            
            if is_club_competition:
                continue
            
            # Try to match to confederations based on name, code, or area
            if any(['uefa' in name, 'europe' in area, code.startswith('EU')]) and any(['nation' in name, 'euro' in name, 'qualif' in name]):
                qualifiers['UEFA'].append({'name': comp['name'], 'code': code, 'full': comp})
            elif any(['conmebol' in name, 'south america' in area]) and any(['qualif' in name, 'nation' in name]):
                qualifiers['CONMEBOL'].append({'name': comp['name'], 'code': code, 'full': comp})
            elif any(['concacaf' in name, 'north america' in area, 'central america' in area]) and any(['qualif' in name, 'nation' in name, 'gold cup' in name]):
                qualifiers['CONCACAF'].append({'name': comp['name'], 'code': code, 'full': comp})
            elif any(['afc' in name, 'asia' in area]) and any(['qualif' in name, 'nation' in name, 'asian cup' in name]):
                qualifiers['AFC'].append({'name': comp['name'], 'code': code, 'full': comp})
            elif any(['caf' in name, 'africa' in area]) and any(['qualif' in name, 'nation' in name, 'cup of nations' in name]):
                qualifiers['CAF'].append({'name': comp['name'], 'code': code, 'full': comp})
            elif any(['ofc' in name, 'oceania' in area]) and any(['qualif' in name, 'nation' in name]):
                qualifiers['OFC'].append({'name': comp['name'], 'code': code, 'full': comp})
        
        return qualifiers
    
    def get_standings_for_confederation(self, competition_code):
        """Get standings for a specific qualifier competition"""
        try:
            url = f"{self.base_url}/competitions/{competition_code}/standings"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.warning(f"Could not get standings for {competition_code}: {e}")
            return None
    
    def get_matches_for_confederation(self, competition_code, date_from=None, date_to=None):
        """Get matches for a specific qualifier competition"""
        try:
            url = f"{self.base_url}/competitions/{competition_code}/matches"
            params = {}
            if date_from:
                params['dateFrom'] = date_from
            if date_to:
                params['dateTo'] = date_to
            
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.warning(f"Could not get matches for {competition_code}: {e}")
            return None
    
    def calculate_team_probability(self, team_data, confederation):
        """Calculate probability for a team based on qualifier data"""
        # Base probability calculation
        prob = 0
        
        # Factors from qualifier performance
        points = team_data.get('points', 0)
        position = team_data.get('position', 100)
        played = team_data.get('playedGames', 0)
        goal_diff = team_data.get('goalDifference', 0)
        form = team_data.get('form', '')
        
        # Position-based probability (being in qualifying spots)
        if position <= 2:
            prob += 70  # Top 2 = almost qualified
        elif position == 3:
            prob += 50  # Playoff spot
        elif position == 4:
            prob += 30  # Still in contention
        elif position == 5:
            prob += 15  # Long shot
        else:
            prob += 5   # Very unlikely
        
        # Points-based adjustment
        if played > 0:
            points_per_game = points / played
            if points_per_game >= 2:
                prob += 15  # Excellent form
            elif points_per_game >= 1.5:
                prob += 10  # Good form
            elif points_per_game >= 1:
                prob += 5   # Decent form
            elif points_per_game < 0.5:
                prob -= 10  # Poor form
        
        # Goal difference adjustment
        if goal_diff > 10:
            prob += 10
        elif goal_diff > 5:
            prob += 5
        elif goal_diff < -5:
            prob -= 10
        
        # Recent form (last 5 matches)
        if form:
            wins = form.count('W')
            draws = form.count('D')
            losses = form.count('L')
            
            win_rate = wins / 5 if (wins + draws + losses) > 0 else 0
            if win_rate >= 0.8:
                prob += 10  # Excellent recent form
            elif win_rate >= 0.6:
                prob += 5
            elif win_rate < 0.2:
                prob -= 10  # Poor recent form
        
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
        
        # Cap at 95% (unless actually qualified)
        qualified = team_data.get('status', '').upper() in ['QUALIFIED', 'AUTOMATIC_QUALIFIED']
        
        return min(prob, 95) if not qualified else 100
    
    def fetch_and_process_all_qualifiers(self):
        """Fetch data for all confederations and process"""
        logger.info("Fetching qualifier data for all confederations...")
        
        # First, find all qualifier competitions
        qualifiers = self.find_qualifier_competitions()
        
        all_team_data = []
        date_from = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        date_to = datetime.now().strftime('%Y-%m-%d')
        
        for confederation, comps in qualifiers.items():
            logger.info(f"Processing {confederation} qualifiers...")
            
            if not comps:
                logger.warning(f"No qualifier competitions found for {confederation}")
                continue
            
            # Process each qualifier competition
            for comp in comps:
                code = comp['code']
                logger.info(f"  Fetching {comp['name']} ({code})...")
                
                # Get standings
                standings = self.get_standings_for_confederation(code)
                if not standings:
                    continue
                
                # Get matches
                matches = self.get_matches_for_confederation(code, date_from, date_to)
                
                # Process each group
                for standing in standings.get('standings', []):
                    if standing.get('type') != 'TOTAL':
                        continue
                    
                    group_name = standing.get('group', '')
                    
                    # Process each team in the group
                    for team_row in standing.get('table', []):
                        team_info = team_row.get('team', {})
                        team_name = team_info.get('name')
                        
                        if not team_name:
                            continue
                        
                        # FILTER: Only include national teams (exclude club teams)
                        team_lower = team_name.lower()
                        
                        # Brazilian clubs
                        brazilian_clubs = ['palmeiras', 'flamengo', 'cruzeiro', 'corinthians', 'santos', 'sao paulo',
                                          'fluminense', 'botafogo', 'vasco', 'gremio', 'internacional', 'atletico mg',
                                          'athletico pr', 'fortaleza', 'bahia', 'goias', 'cuiaba', 'america mg', 'ceara',
                                          'brusque', 'chapecoense', 'ponte preta', 'abc', 'figueirense', 'boavista',
                                          'bragantino', 'mineiro', 'recife', 'juventude', 'vitoria']
                        
                        # Brazilian club suffixes
                        brazilian_suffixes = ['fbpa', 'ec', 'ca', 'sc', 'fc', 'cf', 'ap', 'mg', 'ac', 'ec vitória',
                                            'ec juventude', 'sc recife', 'ca mineiro', 'rb bragantino', 'ceará sc']
                        
                        is_club_team = any([
                            # Common club suffixes
                            team_lower.endswith(' fc'), team_lower.endswith(' cf'), team_lower.endswith(' sk'),
                            team_lower.endswith(' united'), team_lower.endswith(' city'), 
                            team_lower.endswith(' athletic'), team_lower.endswith(' club'),
                            team_lower.startswith('se '), team_lower.startswith('cr '), team_lower.startswith('fc '),
                            # Contains team designators
                            ' fc' in team_lower, ' cf' in team_lower, ' sk' in team_lower,
                            # European clubs
                            'real madrid' in team_lower, 'barcelona' in team_lower, 'bayern' in team_lower,
                            'paris saint' in team_lower, 'psg' in team_lower, 'arsenal' in team_lower,
                            'manchester' in team_lower, 'liverpool' in team_lower, 'chelsea' in team_lower,
                            'juventus' in team_lower, 'internazionale' in team_lower, 'inter milano' in team_lower,
                            'ac milan' in team_lower, 'milan' in team_lower and 'ac' in team_lower,
                            'borussia dortmund' in team_lower, 'tottenham' in team_lower, 'napoli' in team_lower,
                            'atletico madrid' in team_lower, 'valencia' in team_lower, 'sevilla' in team_lower,
                            'ajax' in team_lower, 'psv' in team_lower,
                            # Brazilian clubs and suffixes
                            any([club in team_lower for club in brazilian_clubs]),
                            any([suffix in team_lower for suffix in brazilian_suffixes]),
                            team_lower.endswith('fbpa'), team_lower.endswith(' ec'),
                            # Other clubs
                            'as roma' in team_lower, 'ssc napoli' in team_lower, 'atalanta' in team_lower,
                            'lazio' in team_lower, 'fiorentina' in team_lower, 'sampdoria' in team_lower,
                        ])
                        
                        if is_club_team:
                            logger.debug(f"Skipping club team: {team_name}")
                            continue
                        
                        # Calculate probability
                        prob = self.calculate_team_probability(team_row, confederation)
                        
                        # Determine qualification status
                        status = 'In Progress'
                        if team_row.get('status', '').upper() in ['QUALIFIED', 'AUTOMATIC_QUALIFIED']:
                            status = 'Qualified'
                            prob = 100
                        
                        all_team_data.append({
                            'team': team_name,
                            'confederation': confederation,
                            'qualification_status': status,
                            'prob_fill_slot': round(prob, 1),
                            'current_group': group_name,
                            'position': team_row.get('position'),
                            'points': team_row.get('points'),
                            'played': team_row.get('playedGames'),
                            'goal_diff': team_row.get('goalDifference'),
                            'form': team_row.get('form', '')
                        })
        
        return all_team_data
    
    def update_team_probabilities_csv(self):
        """Update team_slot_probabilities.csv with real qualifier data"""
        team_data = self.fetch_and_process_all_qualifiers()
        
        if not team_data:
            logger.error("No team data retrieved")
            return
        
        # Create DataFrame
        df = pd.DataFrame(team_data)
        
        # Save to CSV
        df.to_csv('team_slot_probabilities.csv', index=False)
        logger.info(f"Updated team_slot_probabilities.csv with {len(df)} teams")
        
        # Also save detailed data
        with open('qualifier_data.json', 'w') as f:
            json.dump(team_data, f, indent=2)
        logger.info("Saved detailed data to qualifier_data.json")
        
        return df

def main():
    # Load API key from config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    api_key = config.get('api_keys', {}).get('football_data')
    
    if not api_key or api_key == 'YOUR_FOOTBALL_DATA_API_KEY':
        print("Please add your Football-Data.org API key to config.json")
        return
    
    # Create fetcher and process
    fetcher = QualifierDataFetcher(api_key)
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
    main()

