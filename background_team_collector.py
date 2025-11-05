#!/usr/bin/env python3
"""
Background team collector that runs over 21 hours to fetch teams from API-Football
using a limited number of requests (100/day) efficiently.

This script will:
- Make API calls at strategic intervals (~12-15 min apart)
- Focus on confederations with few/no teams
- Update team_slot_probabilities.csv incrementally
- Log progress for monitoring
"""

import time
import json
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('background_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BackgroundTeamCollector:
    def __init__(self, api_key, duration_hours=21, max_requests=100):
        self.api_key = api_key
        self.duration_hours = duration_hours
        self.max_requests = max_requests
        self.requests_made = 0
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(hours=duration_hours)
        self.interval_seconds = (duration_hours * 3600) / max_requests  # Spread requests evenly
        
        self.af_base_url = "https://v3.football.api-sports.io"
        self.af_headers = {
            'X-RapidAPI-Key': api_key,
            'X-RapidAPI-Host': 'v3.football.api-sports.io'
        }
        
        # Known World Cup Qualifier League IDs
        self.wcq_league_ids = {
            'AFC': 358,
            'CAF': 359,
            'CONCACAF': 360,
            'CONMEBOL': 361,
            'UEFA': 363,
            'OFC': 364,
        }
        
        # Load existing teams to avoid duplicates
        self.existing_teams = self.load_existing_teams()
        self.progress_file = Path('collection_progress.json')
        self.load_progress()
        
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
        """Load progress from previous runs"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    progress = json.load(f)
                    self.requests_made = progress.get('requests_made', 0)
                    self.completed_seasons = progress.get('completed_seasons', set())
                    self.completed_leagues = progress.get('completed_leagues', set())
                    logger.info(f"Loaded progress: {self.requests_made} requests made")
            except:
                self.completed_seasons = set()
                self.completed_leagues = set()
        else:
            self.completed_seasons = set()
            self.completed_leagues = set()
    
    def save_progress(self):
        """Save current progress"""
        progress = {
            'requests_made': self.requests_made,
            'completed_seasons': list(self.completed_seasons),
            'completed_leagues': list(self.completed_leagues),
            'last_update': datetime.now().isoformat()
        }
        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)
    
    def is_valid_national_team(self, team_name):
        """Quick check if team is valid (simplified version)"""
        if not team_name:
            return False
        
        # Common club indicators
        club_indicators = ['fc', 'united', 'city', 'athletic', 'sporting', 'club', 'cf', 'sc', 
                          'real', 'barcelona', 'madrid', 'liverpool', 'chelsea', 'arsenal',
                          'bayern', 'dortmund', 'psg', 'juventus', 'milan', 'inter', 'ac ',
                          'nigd bank', 'mekelakeya', 'grobiņa']
        
        team_lower = team_name.lower()
        if any(indicator in team_lower for indicator in club_indicators):
            # But allow some valid national teams with these words
            valid_exceptions = ['united states', 'united arab emirates']
            if not any(exc in team_lower for exc in valid_exceptions):
                return False
        
        # Must be a reasonable length (not too short, not too long)
        if len(team_name) < 3 or len(team_name) > 50:
            return False
        
        return True
    
    def fetch_standings(self, league_id, season):
        """Fetch standings for a league/season"""
        if self.requests_made >= self.max_requests:
            logger.warning("Max requests reached!")
            return None
        
        try:
            url = f"{self.af_base_url}/standings"
            params = {'league': league_id, 'season': season}
            response = requests.get(url, headers=self.af_headers, params=params, timeout=30)
            self.requests_made += 1
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("Rate limit hit, waiting longer...")
                time.sleep(60)
                return None
            else:
                logger.debug(f"Status {response.status_code} for league {league_id}, season {season}")
                return None
        except Exception as e:
            logger.debug(f"Error fetching standings: {e}")
            return None
    
    def fetch_teams(self, league_id, season):
        """Fetch teams list for a league/season"""
        if self.requests_made >= self.max_requests:
            return None
        
        try:
            url = f"{self.af_base_url}/teams"
            params = {'league': league_id, 'season': season}
            response = requests.get(url, headers=self.af_headers, params=params, timeout=30)
            self.requests_made += 1
            
            if response.status_code == 200:
                data = response.json()
                return data.get('response', [])
            elif response.status_code == 429:
                logger.warning("Rate limit hit, waiting longer...")
                time.sleep(60)
                return None
            else:
                return None
        except Exception as e:
            logger.debug(f"Error fetching teams: {e}")
            return None
    
    def fetch_fixtures(self, league_id, season, limit=50):
        """Fetch fixtures for a league/season"""
        if self.requests_made >= self.max_requests:
            return None
        
        try:
            url = f"{self.af_base_url}/fixtures"
            params = {'league': league_id, 'season': season}
            response = requests.get(url, headers=self.af_headers, params=params, timeout=30)
            self.requests_made += 1
            
            if response.status_code == 200:
                data = response.json()
                fixtures = data.get('response', [])[:limit]
                return fixtures
            elif response.status_code == 429:
                logger.warning("Rate limit hit, waiting longer...")
                time.sleep(60)
                return None
            else:
                return None
        except Exception as e:
            logger.debug(f"Error fetching fixtures: {e}")
            return None
    
    def process_team(self, team_info, confederation):
        """Process a single team and add to CSV if valid"""
        team_name = team_info.get('name', '')
        if not team_name or not self.is_valid_national_team(team_name):
            return None
        
        # Check if already exists
        if team_name.lower() in self.existing_teams:
            return None
        
        # Create team entry
        team_data = {
            'team': team_name,
            'confederation': confederation,
            'qualification_status': 'In Progress',
            'prob_fill_slot': 50.0,  # Default probability
            'current_group': '',
            'position': None,
            'points': None,
            'played': 0,
            'goal_diff': 0,
            'form': ''
        }
        
        return team_data
    
    def update_csv(self, new_teams):
        """Add new teams to CSV"""
        if not new_teams:
            return
        
        csv_path = Path('team_slot_probabilities.csv')
        try:
            # Read existing
            if csv_path.exists():
                df = pd.read_csv(csv_path)
            else:
                df = pd.DataFrame(columns=['team', 'confederation', 'qualification_status', 
                                          'prob_fill_slot', 'current_group', 'position', 
                                          'points', 'played', 'goal_diff', 'form'])
            
            # Add new teams
            new_df = pd.DataFrame(new_teams)
            df = pd.concat([df, new_df], ignore_index=True)
            
            # Remove duplicates
            df = df.drop_duplicates(subset=['team'], keep='first')
            
            # Save
            df.to_csv(csv_path, index=False)
            
            # Update existing teams set
            for team in new_teams:
                self.existing_teams.add(team['team'].lower())
            
            logger.info(f"✓ Added {len(new_teams)} new teams to CSV (Total: {len(df)})")
            return len(new_teams)
        except Exception as e:
            logger.error(f"Error updating CSV: {e}")
            return 0
    
    def collect_from_standings(self, confederation, league_id, season):
        """Collect teams from standings"""
        season_key = f"{league_id}_{season}"
        if season_key in self.completed_seasons:
            return []
        
        logger.info(f"  Trying {confederation} standings (League {league_id}, Season {season})...")
        standings_data = self.fetch_standings(league_id, season)
        
        if not standings_data or not standings_data.get('response'):
            return []
        
        new_teams = []
        for standing_group in standings_data.get('response', []):
            standings = standing_group.get('league', {}).get('standings', [])
            
            if isinstance(standings, list) and len(standings) > 0:
                # Handle grouped or flat standings
                teams_to_process = []
                if isinstance(standings[0], list):
                    for group in standings:
                        teams_to_process.extend(group)
                else:
                    teams_to_process = standings
                
                for team_row in teams_to_process:
                    team_info = team_row.get('team', {})
                    team_data = self.process_team(team_info, confederation)
                    if team_data:
                        new_teams.append(team_data)
        
        if new_teams:
            self.completed_seasons.add(season_key)
            logger.info(f"    Found {len(new_teams)} teams from standings")
        
        return new_teams
    
    def collect_from_teams_list(self, confederation, league_id, season):
        """Collect teams from teams list endpoint"""
        season_key = f"{league_id}_{season}_teams"
        if season_key in self.completed_seasons:
            return []
        
        logger.info(f"  Trying {confederation} teams list (League {league_id}, Season {season})...")
        teams_list = self.fetch_teams(league_id, season)
        
        if not teams_list:
            return []
        
        new_teams = []
        for team_info in teams_list:
            team = team_info.get('team', {})
            team_data = self.process_team(team, confederation)
            if team_data:
                new_teams.append(team_data)
        
        if new_teams:
            self.completed_seasons.add(season_key)
            logger.info(f"    Found {len(new_teams)} teams from teams list")
        
        return new_teams
    
    def collect_from_fixtures(self, confederation, league_id, season):
        """Collect teams from fixtures"""
        season_key = f"{league_id}_{season}_fixtures"
        if season_key in self.completed_seasons:
            return []
        
        logger.info(f"  Trying {confederation} fixtures (League {league_id}, Season {season})...")
        fixtures = self.fetch_fixtures(league_id, season, limit=100)
        
        if not fixtures:
            return []
        
        teams_seen = set()
        new_teams = []
        
        for fixture in fixtures:
            for side in ['home', 'away']:
                team_info = fixture.get('teams', {}).get(side, {})
                team_name = team_info.get('name', '')
                
                if team_name and team_name not in teams_seen:
                    teams_seen.add(team_name)
                    team_data = self.process_team({'name': team_name}, confederation)
                    if team_data:
                        new_teams.append(team_data)
        
        if new_teams:
            self.completed_seasons.add(season_key)
            logger.info(f"    Found {len(new_teams)} teams from fixtures")
        
        return new_teams
    
    def run_collection_cycle(self):
        """Run one collection cycle"""
        logger.info(f"\n=== Collection Cycle ({self.requests_made}/{self.max_requests} requests used) ===")
        
        # Prioritize confederations with few/no teams
        # Get current counts
        csv_path = Path('team_slot_probabilities.csv')
        conf_counts = {}
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                for conf in self.wcq_league_ids.keys():
                    conf_counts[conf] = len(df[df['confederation'] == conf])
            except:
                pass
        
        # Sort by count (fewest first)
        confederations = sorted(self.wcq_league_ids.items(), 
                               key=lambda x: conf_counts.get(x[0], 0))
        
        # Try different seasons (2021-2026)
        seasons = [2021, 2022, 2023, 2024, 2025, 2026]
        
        all_new_teams = []
        
        for confederation, league_id in confederations:
            if self.requests_made >= self.max_requests:
                break
            
            current_count = conf_counts.get(confederation, 0)
            logger.info(f"\nProcessing {confederation} (currently {current_count} teams)...")
            
            # Try multiple seasons
            for season in seasons:
                if self.requests_made >= self.max_requests:
                    break
                
                # Try standings first (most complete data)
                new_teams = self.collect_from_standings(confederation, league_id, season)
                if new_teams:
                    all_new_teams.extend(new_teams)
                    self.update_csv(new_teams)
                    self.save_progress()
                
                # If no standings, try teams list
                if not new_teams and self.requests_made < self.max_requests:
                    new_teams = self.collect_from_teams_list(confederation, league_id, season)
                    if new_teams:
                        all_new_teams.extend(new_teams)
                        self.update_csv(new_teams)
                        self.save_progress()
                
                # Also try fixtures (can find teams not in standings)
                if self.requests_made < self.max_requests:
                    new_teams = self.collect_from_fixtures(confederation, league_id, season)
                    if new_teams:
                        all_new_teams.extend(new_teams)
                        self.update_csv(new_teams)
                        self.save_progress()
        
        return all_new_teams
    
    def run(self):
        """Main run loop"""
        logger.info(f"Starting background collection for {self.duration_hours} hours")
        logger.info(f"Max requests: {self.max_requests}, Interval: {self.interval_seconds:.1f} seconds")
        logger.info(f"Will finish at: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        cycles = 0
        total_teams_added = 0
        
        while datetime.now() < self.end_time and self.requests_made < self.max_requests:
            cycles += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"Cycle {cycles} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*60}")
            
            new_teams = self.run_collection_cycle()
            total_teams_added += len(new_teams)
            
            # Calculate time until next cycle
            time_remaining = (self.end_time - datetime.now()).total_seconds()
            requests_remaining = self.max_requests - self.requests_made
            
            if requests_remaining > 0 and time_remaining > 0:
                # Space out remaining requests
                next_interval = min(self.interval_seconds, time_remaining / requests_remaining)
                logger.info(f"\nWaiting {next_interval/60:.1f} minutes until next cycle...")
                logger.info(f"Progress: {self.requests_made}/{self.max_requests} requests, "
                          f"{total_teams_added} teams added so far")
                time.sleep(next_interval)
            else:
                logger.info("Time or requests exhausted, stopping...")
                break
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Collection complete!")
        logger.info(f"Total cycles: {cycles}")
        logger.info(f"Total requests: {self.requests_made}/{self.max_requests}")
        logger.info(f"Total teams added: {total_teams_added}")
        logger.info(f"{'='*60}")


def main():
    """Main entry point"""
    import sys
    
    # Get API key from config or environment
    api_key = None
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            # Try different possible locations for API key
            api_keys = config.get('api_keys', {})
            api_key = (api_keys.get('api_football') or 
                      api_keys.get('api_football', {}).get('key') if isinstance(api_keys.get('api_football'), dict) else None)
    except Exception as e:
        logger.debug(f"Error reading config: {e}")
        pass
    
    if not api_key:
        # Try environment variable
        import os
        api_key = os.getenv('API_FOOTBALL_KEY')
    
    if not api_key:
        logger.error("API key not found! Please set in config.json or API_FOOTBALL_KEY env var")
        sys.exit(1)
    
    # Create collector
    collector = BackgroundTeamCollector(api_key, duration_hours=21, max_requests=100)
    
    # Run
    try:
        collector.run()
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user, saving progress...")
        collector.save_progress()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        collector.save_progress()


if __name__ == '__main__':
    main()

