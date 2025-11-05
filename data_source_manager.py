#!/usr/bin/env python3
"""
Data Source Manager for FIFA World Cup 2026

This module manages data collection from all confederations and third-party APIs
based on the configuration in config.json.
"""

import json
import requests
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import time
import os

logger = logging.getLogger(__name__)

class DataSourceManager:
    def __init__(self, config_path: str = "config.json"):
        self.config = self.load_config(config_path)
        self.session = requests.Session()
        self.cache = {}
        self.rate_limits = {}
        
    def load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            return {}
    
    def get_api_key(self, source: str) -> Optional[str]:
        """Get API key for a specific source"""
        api_keys = self.config.get('api_keys', {})
        return api_keys.get(source)
    
    def check_rate_limit(self, source: str) -> bool:
        """Check if we can make a request without hitting rate limits"""
        if source not in self.rate_limits:
            self.rate_limits[source] = {'requests': 0, 'reset_time': datetime.now()}
        
        rate_info = self.rate_limits[source]
        if datetime.now() > rate_info['reset_time']:
            rate_info['requests'] = 0
            rate_info['reset_time'] = datetime.now() + timedelta(hours=1)
        
        # Get rate limit from config
        confederations = self.config.get('data_sources', {}).get('confederations', {})
        for conf in confederations.values():
            if conf.get('primary_api') == source or conf.get('backup_api') == source:
                limit = int(conf.get('rate_limit', '1000/hour').split('/')[0])
                return rate_info['requests'] < limit
        
        return True
    
    def make_request(self, url: str, headers: Dict = None, params: Dict = None, 
                    source: str = None) -> Optional[Dict]:
        """Make API request with rate limiting and error handling"""
        if source and not self.check_rate_limit(source):
            logger.warning(f"Rate limit exceeded for {source}")
            return None
        
        try:
            response = self.session.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            if source:
                self.rate_limits[source]['requests'] += 1
            
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None
    
    def get_fifa_rankings(self) -> Dict[str, int]:
        """Get FIFA rankings from official API or fallback"""
        api_key = self.get_api_key('fifa')
        url = self.config['data_sources']['fifa_rankings']['api_url']
        
        headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
        data = self.make_request(url, headers=headers, source='fifa')
        
        if data:
            rankings = {}
            for team in data.get('rankings', []):
                rankings[team['team_name']] = team['rank']
            return rankings
        
        # Fallback to cached data
        return self.load_cached_data('fifa_rankings')
    
    def get_confederation_data(self, confederation: str, data_type: str) -> Dict:
        """Get data from specific confederation"""
        conf_data = self.config['data_sources']['confederations'].get(confederation)
        if not conf_data:
            logger.error(f"Configuration not found for {confederation}")
            return {}
        
        # Try primary API first
        primary_url = conf_data['primary_api']
        api_key = self.get_api_key(confederation.lower())
        
        if api_key and self.check_rate_limit(primary_url):
            headers = {'Authorization': f'Bearer {api_key}'}
            data = self.make_request(f"{primary_url}/{data_type}", headers=headers, source=primary_url)
            if data:
                return data
        
        # Try backup API
        backup_url = conf_data['backup_api']
        backup_key = self.get_api_key('football_data')  # Most common backup
        
        if backup_key and self.check_rate_limit(backup_url):
            headers = {'X-Auth-Token': backup_key}
            data = self.make_request(f"{backup_url}/{data_type}", headers=headers, source=backup_url)
            if data:
                return data
        
        # Fallback to free source (would need web scraping implementation)
        logger.warning(f"All APIs failed for {confederation}, using cached data")
        return self.load_cached_data(f"{confederation}_{data_type}")
    
    def get_uefa_data(self, data_type: str) -> Dict:
        """Get UEFA-specific data"""
        return self.get_confederation_data('UEFA', data_type)
    
    def get_caf_data(self, data_type: str) -> Dict:
        """Get CAF-specific data"""
        return self.get_confederation_data('CAF', data_type)
    
    def get_concacaf_data(self, data_type: str) -> Dict:
        """Get CONCACAF-specific data"""
        return self.get_confederation_data('CONCACAF', data_type)
    
    def get_afc_data(self, data_type: str) -> Dict:
        """Get AFC-specific data"""
        return self.get_confederation_data('AFC', data_type)
    
    def get_conmebol_data(self, data_type: str) -> Dict:
        """Get CONMEBOL-specific data"""
        return self.get_confederation_data('CONMEBOL', data_type)
    
    def get_ofc_data(self, data_type: str) -> Dict:
        """Get OFC-specific data"""
        return self.get_confederation_data('OFC', data_type)
    
    def get_match_results(self, confederation: str, date_from: str, date_to: str) -> List[Dict]:
        """Get match results for a specific confederation and date range"""
        data = self.get_confederation_data(confederation, 'matches')
        
        if not data:
            return []
        
        matches = []
        for match in data.get('matches', []):
            match_date = datetime.fromisoformat(match['date'].replace('Z', '+00:00'))
            if date_from <= match_date.strftime('%Y-%m-%d') <= date_to:
                matches.append({
                    'team1': match['home_team'],
                    'team2': match['away_team'],
                    'score1': match['home_score'],
                    'score2': match['away_score'],
                    'date': match['date'],
                    'type': match.get('competition_stage', 'qualifier'),
                    'confederation': confederation
                })
        
        return matches
    
    def get_group_standings(self, confederation: str, group: str = None) -> Dict[str, List[Dict]]:
        """Get group standings for a confederation"""
        data = self.get_confederation_data(confederation, 'standings')
        
        if not data:
            return {}
        
        standings = {}
        for group_data in data.get('groups', []):
            group_name = group_data['name']
            if group and group_name != group:
                continue
            
            teams = []
            for team in group_data.get('teams', []):
                teams.append({
                    'team': team['name'],
                    'points': team['points'],
                    'played': team['played'],
                    'won': team['won'],
                    'drawn': team['drawn'],
                    'lost': team['lost'],
                    'goal_diff': team['goal_difference'],
                    'goals_for': team['goals_for'],
                    'goals_against': team['goals_against']
                })
            
            standings[group_name] = teams
        
        return standings
    
    def get_team_form(self, team: str, confederation: str, matches_back: int = 5) -> Dict:
        """Get recent form data for a team"""
        data = self.get_confederation_data(confederation, f'teams/{team}/form')
        
        if not data:
            return {'team': team, 'form': [], 'goals_scored': 0, 'goals_conceded': 0}
        
        return {
            'team': team,
            'form': data.get('form', [])[:matches_back],
            'goals_scored': data.get('goals_scored', 0),
            'goals_conceded': data.get('goals_conceded', 0),
            'clean_sheets': data.get('clean_sheets', 0),
            'wins': data.get('wins', 0),
            'draws': data.get('draws', 0),
            'losses': data.get('losses', 0)
        }
    
    def load_cached_data(self, data_type: str) -> Dict:
        """Load cached data from file"""
        cache_file = f"cache/{data_type}.json"
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"No cached data found for {data_type}")
            return {}
    
    def save_cached_data(self, data_type: str, data: Dict) -> None:
        """Save data to cache"""
        os.makedirs('cache', exist_ok=True)
        cache_file = f"cache/{data_type}.json"
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_all_confederation_data(self, data_type: str) -> Dict[str, Dict]:
        """Get data from all confederations"""
        confederations = ['UEFA', 'CAF', 'CONCACAF', 'AFC', 'CONMEBOL', 'OFC']
        all_data = {}
        
        for conf in confederations:
            logger.info(f"Fetching {data_type} data for {conf}")
            data = self.get_confederation_data(conf, data_type)
            if data:
                all_data[conf] = data
                # Cache the data
                self.save_cached_data(f"{conf}_{data_type}", data)
            time.sleep(1)  # Rate limiting between confederations
        
        return all_data
    
    def update_team_probabilities_from_sources(self, team_df: pd.DataFrame) -> pd.DataFrame:
        """Update team probabilities using data from all sources"""
        logger.info("Updating team probabilities from all data sources")
        
        # Get FIFA rankings
        fifa_rankings = self.get_fifa_rankings()
        
        # Get recent match results for all confederations
        date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        date_to = datetime.now().strftime('%Y-%m-%d')
        
        all_matches = []
        for conf in ['UEFA', 'CAF', 'CONCACAF', 'AFC', 'CONMEBOL', 'OFC']:
            matches = self.get_match_results(conf, date_from, date_to)
            all_matches.extend(matches)
        
        # Get group standings for all confederations
        all_standings = {}
        for conf in ['UEFA', 'CAF', 'CONCACAF', 'AFC', 'CONMEBOL', 'OFC']:
            standings = self.get_group_standings(conf)
            all_standings.update(standings)
        
        # Update probabilities based on new data
        for idx, row in team_df.iterrows():
            team = row['team']
            confederation = row['confederation']
            
            # Update based on FIFA ranking
            if team in fifa_rankings:
                fifa_rank = fifa_rankings[team]
                base_prob = max(5, 100 - (fifa_rank * 0.8))
                team_df.at[idx, 'prob_fill_slot'] = base_prob
            
            # Update based on recent form
            form_data = self.get_team_form(team, confederation)
            if form_data['form']:
                form_score = sum(2 if r == 'W' else 0.5 if r == 'D' else -1 for r in form_data['form'])
                form_adjustment = form_score * 2  # Scale adjustment
                current_prob = team_df.at[idx, 'prob_fill_slot']
                new_prob = max(1, min(95, current_prob + form_adjustment))
                team_df.at[idx, 'prob_fill_slot'] = new_prob
        
        return team_df

# Example usage
if __name__ == "__main__":
    manager = DataSourceManager()
    
    # Get FIFA rankings
    rankings = manager.get_fifa_rankings()
    print(f"FIFA Rankings: {len(rankings)} teams")
    
    # Get UEFA data
    uefa_matches = manager.get_uefa_data('matches')
    print(f"UEFA matches: {len(uefa_matches.get('matches', []))}")
    
    # Get all confederation data
    all_data = manager.get_all_confederation_data('standings')
    print(f"Data from {len(all_data)} confederations")
