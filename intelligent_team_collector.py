#!/usr/bin/env python3
"""
Intelligent background team collector that iteratively tries different strategies
to find World Cup qualifier teams from API-Football.

This will:
1. Try known league IDs with different seasons
2. Search for qualifier competitions using /leagues
3. Extract teams from fixtures even without standings
4. Try alternative league IDs
5. Be very inclusive with validation (collect first, refine later)
"""

import time
import json
import logging
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('intelligent_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class IntelligentTeamCollector:
    def __init__(self, api_key, max_requests=100):
        self.api_key = api_key
        self.max_requests = max_requests
        self.requests_made = 0
        
        self.af_base_url = "https://v3.football.api-sports.io"
        self.af_headers = {
            'X-RapidAPI-Key': api_key,
            'X-RapidAPI-Host': 'v3.football.api-sports.io'
        }
        
        # Known league IDs
        self.known_league_ids = {
            'AFC': 358,
            'CAF': 359,
            'CONCACAF': 360,
            'CONMEBOL': 361,
            'UEFA': 363,
            'OFC': 364,
        }
        
        # Load existing teams
        self.existing_teams = self.load_existing_teams()
        self.progress_file = Path('intelligent_progress.json')
        self.load_progress()
        
        # All teams found
        self.all_teams = []
        
    def load_existing_teams(self):
        """Load teams already in CSV"""
        csv_path = Path('team_slot_probabilities.csv')
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                return set(df['team'].str.lower().tolist())
            except:
                return set()
        return set()
    
    def load_progress(self):
        """Load progress"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    progress = json.load(f)
                    self.requests_made = progress.get('requests_made', 0)
                    self.tried_combinations = set(progress.get('tried_combinations', []))
                    logger.info(f"Loaded progress: {self.requests_made} requests")
            except:
                self.tried_combinations = set()
        else:
            self.tried_combinations = set()
    
    def save_progress(self):
        """Save progress"""
        progress = {
            'requests_made': self.requests_made,
            'tried_combinations': list(self.tried_combinations),
            'last_update': datetime.now().isoformat(),
            'total_teams_found': len(self.all_teams)
        }
        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)
    
    def make_request(self, url, params=None):
        """Make API request with rate limiting"""
        if self.requests_made >= self.max_requests:
            return None
        
        try:
            response = requests.get(url, headers=self.af_headers, params=params, timeout=30)
            self.requests_made += 1
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("Rate limit - waiting 60s")
                time.sleep(60)
                return None
            else:
                return None
        except Exception as e:
            logger.debug(f"Request error: {e}")
            return None
    
    def is_valid_team(self, team_name):
        """Very lenient validation - only reject obvious clubs"""
        if not team_name or len(team_name) < 3:
            return False
        
        team_lower = team_name.lower()
        
        # Reject obvious clubs
        club_patterns = [
            'fc ', 'cf ', 'sc ', ' fc', ' cf', ' sc',
            'real madrid', 'barcelona', 'bayern', 'psg', 'arsenal',
            'liverpool', 'chelsea', 'juventus', 'milan', 'inter milano',
            'nigd bank', 'mekelakeya', 'grobiņa', 'palmeiras', 'flamengo'
        ]
        
        if any(pattern in team_lower for pattern in club_patterns):
            return False
        
        # Accept everything else for now
        return True
    
    def extract_teams_from_fixtures(self, fixtures):
        """Extract unique teams from fixtures"""
        teams = set()
        for fixture in fixtures:
            home = fixture.get('teams', {}).get('home', {}).get('name', '')
            away = fixture.get('teams', {}).get('away', {}).get('name', '')
            if home and self.is_valid_team(home):
                teams.add(home)
            if away and self.is_valid_team(away):
                teams.add(away)
        return teams
    
    def try_league_standings(self, league_id, season, confederation):
        """Try to get teams from standings"""
        key = f"standings_{league_id}_{season}"
        if key in self.tried_combinations:
            return []
        
        url = f"{self.af_base_url}/standings"
        params = {'league': league_id, 'season': season}
        data = self.make_request(url, params)
        
        self.tried_combinations.add(key)
        
        if not data or not data.get('response'):
            return []
        
        teams = []
        for standing_group in data.get('response', []):
            standings = standing_group.get('league', {}).get('standings', [])
            
            if isinstance(standings, list) and len(standings) > 0:
                if isinstance(standings[0], list):
                    for group in standings:
                        for team_row in group:
                            team_name = team_row.get('team', {}).get('name', '')
                            if team_name and self.is_valid_team(team_name):
                                teams.append({
                                    'team': team_name,
                                    'confederation': confederation,
                                    'source': f'standings_{season}'
                                })
                else:
                    for team_row in standings:
                        team_name = team_row.get('team', {}).get('name', '')
                        if team_name and self.is_valid_team(team_name):
                            teams.append({
                                'team': team_name,
                                'confederation': confederation,
                                'source': f'standings_{season}'
                            })
        
        return teams
    
    def try_league_fixtures(self, league_id, season, confederation):
        """Try to get teams from fixtures"""
        key = f"fixtures_{league_id}_{season}"
        if key in self.tried_combinations:
            return []
        
        url = f"{self.af_base_url}/fixtures"
        params = {'league': league_id, 'season': season, 'last': 100}  # Get last 100 fixtures
        data = self.make_request(url, params)
        
        self.tried_combinations.add(key)
        
        if not data or not data.get('response'):
            return []
        
        fixtures = data.get('response', [])
        team_names = self.extract_teams_from_fixtures(fixtures)
        
        teams = []
        for team_name in team_names:
            if team_name.lower() not in self.existing_teams:
                teams.append({
                    'team': team_name,
                    'confederation': confederation,
                    'source': f'fixtures_{season}'
                })
        
        return teams
    
    def try_league_teams(self, league_id, season, confederation):
        """Try to get teams from teams endpoint"""
        key = f"teams_{league_id}_{season}"
        if key in self.tried_combinations:
            return []
        
        url = f"{self.af_base_url}/teams"
        params = {'league': league_id, 'season': season}
        data = self.make_request(url, params)
        
        self.tried_combinations.add(key)
        
        if not data or not data.get('response'):
            return []
        
        teams = []
        for team_info in data.get('response', []):
            team_name = team_info.get('team', {}).get('name', '')
            if team_name and self.is_valid_team(team_name):
                if team_name.lower() not in self.existing_teams:
                    teams.append({
                        'team': team_name,
                        'confederation': confederation,
                        'source': f'teams_{season}'
                    })
        
        return teams
    
    def search_qualifier_leagues(self):
        """Search for qualifier leagues"""
        # Try getting all leagues and filtering
        url = f"{self.af_base_url}/leagues"
        
        # Try different approaches
        search_terms = ['qualif', 'world cup', 'wcq', 'qualification']
        
        for term in search_terms:
            if self.requests_made >= self.max_requests:
                break
            
            # Note: API-Football might not support search, but try anyway
            params = {'search': term}
            data = self.make_request(url, params)
            
            if data and data.get('response'):
                leagues = data.get('response', [])
                logger.info(f"Found {len(leagues)} leagues matching '{term}'")
                
                # Process found leagues
                for league_info in leagues[:20]:  # Limit to first 20
                    league = league_info.get('league', {})
                    league_id = league.get('id')
                    league_name = league.get('name', '').lower()
                    
                    # Check if it's a qualifier
                    if any(qterm in league_name for qterm in ['qualif', 'wcq', 'world cup']):
                        # Detect confederation
                        conf = self.detect_confederation(league_name, league_info.get('country', {}))
                        if conf:
                            # Try to get teams from this league
                            for season in [2024, 2023, 2022, 2021]:
                                if self.requests_made >= self.max_requests:
                                    break
                                teams = self.try_league_fixtures(league_id, season, conf)
                                if teams:
                                    self.all_teams.extend(teams)
                                    logger.info(f"  Found {len(teams)} teams from {league_name} (season {season})")
    
    def detect_confederation(self, league_name, country_info):
        """Detect confederation from league name or country"""
        name_lower = league_name.lower()
        country_name = country_info.get('name', '').lower()
        
        # AFC
        if any(term in name_lower for term in ['afc', 'asian', 'asia']):
            return 'AFC'
        # CAF
        if any(term in name_lower for term in ['caf', 'africa', 'african']):
            return 'CAF'
        # CONCACAF
        if any(term in name_lower for term in ['concacaf', 'north america', 'central america']):
            return 'CONCACAF'
        # CONMEBOL
        if any(term in name_lower for term in ['conmebol', 'south america']):
            return 'CONMEBOL'
        # UEFA
        if any(term in name_lower for term in ['uefa', 'europe', 'european']):
            return 'UEFA'
        # OFC
        if any(term in name_lower for term in ['ofc', 'oceania']):
            return 'OFC'
        
        return None
    
    def update_csv(self):
        """Update CSV with new teams"""
        if not self.all_teams:
            return
        
        csv_path = Path('team_slot_probabilities.csv')
        
        # Read existing
        if csv_path.exists():
            df = pd.read_csv(csv_path)
        else:
            df = pd.DataFrame(columns=['team', 'confederation', 'qualification_status',
                                      'prob_fill_slot', 'current_group', 'position',
                                      'points', 'played', 'goal_diff', 'form'])
        
        # Add new teams
        new_teams_data = []
        for team_info in self.all_teams:
            team_name = team_info['team']
            if team_name.lower() not in self.existing_teams:
                new_teams_data.append({
                    'team': team_name,
                    'confederation': team_info['confederation'],
                    'qualification_status': 'In Progress',
                    'prob_fill_slot': 50.0,
                    'current_group': '',
                    'position': None,
                    'points': None,
                    'played': 0,
                    'goal_diff': 0,
                    'form': ''
                })
                self.existing_teams.add(team_name.lower())
        
        if new_teams_data:
            new_df = pd.DataFrame(new_teams_data)
            df = pd.concat([df, new_df], ignore_index=True)
            df = df.drop_duplicates(subset=['team'], keep='first')
            df.to_csv(csv_path, index=False)
            logger.info(f"✓ Added {len(new_teams_data)} new teams to CSV (Total: {len(df)})")
            return len(new_teams_data)
        
        return 0
    
    def run(self):
        """Main collection loop"""
        logger.info("Starting intelligent team collection")
        logger.info(f"Max requests: {self.max_requests}, Current: {self.requests_made}")
        
        seasons = [2024, 2023, 2022, 2021]
        
        # Strategy 1: Try known league IDs with all methods
        logger.info("\n=== Strategy 1: Known League IDs ===")
        for conf, league_id in self.known_league_ids.items():
            if self.requests_made >= self.max_requests:
                break
            
            logger.info(f"\nTrying {conf} (League {league_id})...")
            
            for season in seasons:
                if self.requests_made >= self.max_requests:
                    break
                
                # Try standings
                teams = self.try_league_standings(league_id, season, conf)
                if teams:
                    self.all_teams.extend(teams)
                    logger.info(f"  Season {season}: Found {len(teams)} teams from standings")
                
                # Try fixtures
                if self.requests_made < self.max_requests:
                    teams = self.try_league_fixtures(league_id, season, conf)
                    if teams:
                        self.all_teams.extend(teams)
                        logger.info(f"  Season {season}: Found {len(teams)} teams from fixtures")
                
                # Try teams endpoint
                if self.requests_made < self.max_requests:
                    teams = self.try_league_teams(league_id, season, conf)
                    if teams:
                        self.all_teams.extend(teams)
                        logger.info(f"  Season {season}: Found {len(teams)} teams from teams endpoint")
                
                time.sleep(0.3)  # Rate limiting
        
        # Strategy 2: Search for qualifier leagues
        logger.info("\n=== Strategy 2: Search for Qualifier Leagues ===")
        if self.requests_made < self.max_requests:
            self.search_qualifier_leagues()
        
        # Update CSV
        logger.info("\n=== Updating CSV ===")
        added = self.update_csv()
        
        # Save progress
        self.save_progress()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Collection complete!")
        logger.info(f"Requests used: {self.requests_made}/{self.max_requests}")
        logger.info(f"Total teams found: {len(self.all_teams)}")
        logger.info(f"New teams added: {added}")
        logger.info(f"{'='*60}")


def main():
    import sys
    
    # Get API key
    api_key = None
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            api_key = config.get('api_keys', {}).get('api_football')
    except:
        pass
    
    if not api_key:
        import os
        api_key = os.getenv('API_FOOTBALL_KEY')
    
    if not api_key:
        logger.error("API key not found!")
        sys.exit(1)
    
    collector = IntelligentTeamCollector(api_key, max_requests=100)
    
    try:
        collector.run()
    except KeyboardInterrupt:
        logger.info("\nInterrupted, saving progress...")
        collector.save_progress()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        collector.save_progress()


if __name__ == '__main__':
    main()

