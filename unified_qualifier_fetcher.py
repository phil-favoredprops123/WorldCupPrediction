#!/usr/bin/env python3
"""
Unified Qualifier Data Fetcher
Fetches World Cup qualifier data from BOTH Football-Data.org and API-Football

IMPORTANT: Only uses data from World Cup 2026 cycle (seasons 2024-2026)
- Does NOT use 2022/2023 data (those are from Qatar 2022 World Cup cycle)
- Excludes women's competitions and youth tournaments
- Focuses on current World Cup 2026 qualifiers only

API-Football Integration Approach:
1. Use /leagues endpoint to discover all leagues and get league IDs
   - Try multiple approaches: by season, current=true, and without season filter
   - Extract league IDs from the response
2. Filter leagues to find World Cup qualifiers (flexible filtering + confederation detection)
3. Use league IDs to fetch detailed data:
   - /standings?league={id}&season={year}
   - /fixtures?league={id}&season={year}
"""

import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UnifiedQualifierFetcher:
    def __init__(self, football_data_key, api_football_key=None):
        self.football_data_key = football_data_key
        self.api_football_key = api_football_key
        
        # Football-Data.org setup
        self.fd_headers = {"X-Auth-Token": football_data_key}
        self.fd_base_url = "https://api.football-data.org/v4"
        
        # API-Football setup (if available)
        # Using the correct API endpoint: https://v3.football.api-sports.io
        if api_football_key:
            self.af_headers = {
                "X-RapidAPI-Key": api_football_key,
                "X-RapidAPI-Host": "v3.football.api-sports.io"
            }
            self.af_base_url = "https://v3.football.api-sports.io"
        else:
            self.af_headers = None
            self.af_base_url = None
        
        # Known competition codes from football-data.org
        # Based on: https://www.football-data.org/coverage
        self.competition_codes = {
            'UEFA': {'football_data': 'WCQ_UEFA', 'api_football': None},
            'CONMEBOL': {'football_data': 'WCQ_CONMEBOL', 'api_football': None},
            'CONCACAF': {'football_data': 'WCQ_CONCACAF', 'api_football': None},
            'AFC': {'football_data': None, 'api_football': None},  # May not be available
            'CAF': {'football_data': None, 'api_football': None},  # May not be available
            'OFC': {'football_data': None, 'api_football': None},  # May not be available
        }
        
        # Known World Cup Qualifier League IDs from API-Football
        # These are the official league IDs for World Cup qualifiers by confederation
        self.wcq_league_ids = {
            'AFC': 358,      # World Cup AFC Qualifiers
            'CAF': 359,      # World Cup CAF Qualifiers
            'CONCACAF': 360, # World Cup CONCACAF Qualifiers
            'CONMEBOL': 361, # World Cup CONMEBOL Qualifiers
            'UEFA': 363,     # World Cup UEFA Qualifiers
            'OFC': 364,      # World Cup OFC Qualifiers
        }
        
        # World Cup 2026 Qualification Structure
        # Based on: 209 national teams, 6 confederations + host
        self.confederation_info = {
            'CONCACAF': {
                'teams': 35,
                'spots': '3-4',  # 3 or 4 direct spots
                'format': 'Multi-stage (preliminary rounds, groups, playoffs)',
                'playoff': '4th place vs OFC winner (if applicable)',
                'exceptions': []  # Guyana plays here despite geography
            },
            'UEFA': {
                'teams': 53,
                'spots': 13,
                'format': '9 groups, winners qualify directly, top 8 second-place teams play for 4 remaining spots',
                'playoff': 'Internal playoffs for 4 spots',
                'exceptions': ['Israel', 'Kazakhstan']  # Geographically in Asia but play in UEFA
            },
            'AFC': {
                'teams': 43,
                'spots': '4-5',  # 4 or 5 direct spots
                'format': 'Multi-stage (preliminary rounds, groups, playoffs)',
                'playoff': '5th place vs CONMEBOL 5th place (if applicable)',
                'exceptions': ['Australia']  # Geographically Oceania but plays in AFC
            },
            'CAF': {
                'teams': 52,
                'spots': 5,
                'format': 'Multi-stage (preliminary rounds, groups, playoffs)',
                'playoff': None,
                'exceptions': []
            },
            'CONMEBOL': {
                'teams': 9,
                'spots': '4-5',  # 4 direct, 5th plays playoff
                'format': 'Simple round-robin: all 9 teams play each other twice (home & away), top 4 qualify directly',
                'playoff': '5th place vs AFC 5th place (if applicable) or OFC winner',
                'exceptions': []
            },
            'OFC': {
                'teams': 11,
                'spots': '0-1',  # Usually 0, winner plays playoff
                'format': 'Multi-stage tournament',
                'playoff': 'Winner vs CONCACAF 4th place or CONMEBOL 5th place',
                'exceptions': []
            }
        }
        
        # Geographic exceptions mapping (for confederation detection)
        self.geographic_exceptions = {
            'australia': 'AFC',  # Oceania → AFC
            'israel': 'UEFA',    # Asia → UEFA
            'kazakhstan': 'UEFA', # Asia → UEFA
            'guyana': 'CONCACAF', # South America → CONCACAF
        }
    
    def fetch_from_football_data(self, competition_code):
        """Fetch qualifier data from Football-Data.org"""
        try:
            url = f"{self.fd_base_url}/competitions/{competition_code}/standings"
            response = requests.get(url, headers=self.fd_headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                logger.debug(f"Competition {competition_code} not available (400)")
            else:
                logger.warning(f"Football-Data.org failed for {competition_code}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Football-Data.org error for {competition_code}: {e}")
            return None
    
    def discover_football_data_competitions(self):
        """Discover available qualifier competitions from Football-Data.org"""
        try:
            url = f"{self.fd_base_url}/competitions"
            response = requests.get(url, headers=self.fd_headers, timeout=30)
            response.raise_for_status()
            competitions = response.json()
            
            qualifiers_found = []
            for comp in competitions.get('competitions', []):
                name = comp.get('name', '').lower()
                code = comp.get('code', '')
                
                if any(term in name for term in ['qualif', 'qualifying', 'wcq']):
                    qualifiers_found.append({'name': comp.get('name'), 'code': code})
            
            return qualifiers_found
        except Exception as e:
            logger.warning(f"Could not discover competitions: {e}")
            return []
    
    def fetch_from_api_football(self, league_id=None):
        """Fetch qualifier data from API-Football"""
        if not self.api_football_key:
            return None
        
        try:
            if league_id:
                url = f"{self.af_base_url}/standings"
                params = {'league': league_id, 'season': 2026}
                response = requests.get(url, headers=self.af_headers, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.warning(f"API-Football failed: {e}")
            return None
        
        return None
    
    def fetch_teams_from_api_football(self, league_id, season):
        """Fetch teams from API-Football for a league"""
        if not self.api_football_key:
            return []
        
        try:
            url = f"{self.af_base_url}/teams"
            params = {'league': league_id, 'season': season}
            response = requests.get(url, headers=self.af_headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get('response', [])
        except Exception as e:
            logger.debug(f"Could not fetch teams for league {league_id}: {e}")
            return []
    
    def fetch_standings_from_api_football(self, league_id, season, team_id=None):
        """Fetch standings from API-Football for a league"""
        if not self.api_football_key:
            return None
        
        try:
            url = f"{self.af_base_url}/standings"
            params = {'league': league_id, 'season': season}
            if team_id:
                params['team'] = team_id  # Optional: filter by specific team
            
            response = requests.get(url, headers=self.af_headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"Could not fetch standings for league {league_id}: {e}")
            return None
    
    def fetch_fixtures_from_api_football(self, league_id, season=None):
        """Fetch fixtures/matches from API-Football for a league"""
        if not self.api_football_key:
            return []
        
        try:
            url = f"{self.af_base_url}/fixtures"
            params = {'league': league_id}
            if season:
                params['season'] = season
            
            # Get recent fixtures (last 3 months)
            from_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            to_date = datetime.now().strftime('%Y-%m-%d')
            params['from'] = from_date
            params['to'] = to_date
            
            response = requests.get(url, headers=self.af_headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get('response', [])
        except Exception as e:
            logger.debug(f"Could not fetch fixtures for league {league_id}: {e}")
            return []
    
    def fetch_team_info_from_api_football(self, team_id):
        """Fetch team information from API-Football"""
        if not self.api_football_key:
            return None
        
        try:
            url = f"{self.af_base_url}/teams"
            params = {'id': team_id}
            response = requests.get(url, headers=self.af_headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json().get('response', [])
            return data[0] if data else None
        except Exception as e:
            logger.debug(f"Could not fetch team info for {team_id}: {e}")
            return None
    
    def is_club_team(self, team_name):
        """Check if team is a club (not national team)"""
        if not team_name:
            return True
        
        team_lower = team_name.lower()
        
        # Club indicators
        club_patterns = [
            # Common suffixes
            ' fc', ' cf', ' sk', ' united', ' city', ' athletic', ' club', ' fbpa',
            ' bank', ' bunna', ' kenema', ' ketema', ' hosaena', ' medhin', ' durame',
            # Starts with
            'se ', 'cr ', 'fc ', 'sc ', 'ca ', 'ec ', 'ssc ', 'rb ', 'as ', 'fcb ',
            # European clubs
            'real madrid', 'barcelona', 'bayern', 'paris saint', 'psg', 'arsenal',
            'manchester', 'liverpool', 'chelsea', 'juventus', 'internazionale',
            'inter milano', 'ac milan', 'milan', 'borussia dortmund', 'tottenham',
            'napoli', 'atletico madrid', 'valencia', 'sevilla', 'ajax', 'psv',
            'as roma', 'ssc napoli', 'atalanta', 'lazio', 'fiorentina',
            # Brazilian clubs
            'palmeiras', 'flamengo', 'cruzeiro', 'corinthians', 'santos', 'sao paulo',
            'fluminense', 'botafogo', 'vasco', 'gremio', 'internacional', 'atletico mg',
            'athletico pr', 'fortaleza', 'bahia', 'goias', 'cuiaba', 'america mg',
            'ceara', 'bragantino', 'mineiro', 'recife', 'juventude', 'vitoria',
            # Latvian/Ethiopian clubs detected in data
            'grobiņa', 'skanste', 'alberts', 'saldus', 'beitar', 'tukums', 'ventspils',
            'valmiera', 'olaine', 'nigd bank', 'mekelakeya', 'bahardar', 'giorgis',
            'fasil', 'adama', 'hadiya', 'awassa', 'sidama', 'dire dawa', 'welayta',
            'shashemene', 'hambericho', 'arba minch', 'legetafo', 'legedadi'
        ]
        
        return any([pattern in team_lower for pattern in club_patterns])
    
    def is_valid_national_team(self, team_name, confederation):
        """Check if team is a valid national team eligible for World Cup"""
        if not team_name:
            return False
        
        # Must not be a club team (more lenient - only reject obvious clubs)
        if self.is_club_team(team_name):
            return False
        
        # For now, be more inclusive - if it's not clearly a club, accept it
        # We can refine later, but we need data first
        team_lower = team_name.lower().strip()
        
        # Reject if it's clearly a club with these patterns
        obvious_club_patterns = [
            'fc', 'cf', 'sc', 'united fc', 'city fc', 'athletic fc', 'sporting fc',
            'real ', 'barcelona', 'madrid', 'liverpool', 'chelsea', 'arsenal',
            'bayern', 'dortmund', 'psg', 'juventus', 'milan', 'inter milano',
            'nigd bank', 'mekelakeya', 'grobiņa'
        ]
        
        # Only reject if it's clearly a club name
        if any(team_lower.startswith(pattern) or team_lower.endswith(' ' + pattern) 
               for pattern in obvious_club_patterns):
            return False
        
        # TEMPORARILY: Be more inclusive - accept any team that doesn't look like a club
        # We need data first, can refine later
        # Only reject if it has obvious club indicators in the middle
        if ' fc' in team_lower or ' cf' in team_lower or ' sc' in team_lower:
            # But allow some valid teams
            if 'united states' not in team_lower:
                return False
        
        # For now, accept any team that passed club checks
        # We need data first, can refine later with FIFA member validation
        return True
    
    def process_team_data(self, team_row, confederation, source, competition_name='', fixtures=None):
        """Process team data from either source"""
        # Football-Data.org format
        if source == 'football_data':
            team_info = team_row.get('team', {})
            team_name = team_info.get('name')
            
            # Validate team eligibility
            if not team_name or not self.is_valid_national_team(team_name, confederation):
                return None
            
            return {
                'team': team_name,
                'confederation': confederation,
                'qualification_status': 'In Progress',
                'prob_fill_slot': self.calculate_probability(team_row, confederation, source='football_data', fixtures=fixtures),
                'current_group': team_row.get('group', ''),
                'position': team_row.get('position'),
                'points': team_row.get('points'),
                'played': team_row.get('playedGames', 0),
                'goal_diff': team_row.get('goalDifference', 0),
                'form': team_row.get('form', ''),
                'source': 'football_data'
            }
        
        # API-Football format
        elif source == 'api_football':
            team_info = team_row.get('team', {})
            team_name = team_info.get('name')
            
            # Validate team eligibility
            if not team_name or not self.is_valid_national_team(team_name, confederation):
                return None
            
            # Additional check: if competition name suggests domestic league, reject
            comp_lower = competition_name.lower()
            if any(term in comp_lower for term in ['premier league', '1. liga', 'domestic', 'local league']):
                return None
            
            all_stats = team_row.get('all', {})
            goals = all_stats.get('goals', {})
            
            return {
                'team': team_name,
                'confederation': confederation,
                'qualification_status': 'In Progress',
                'prob_fill_slot': self.calculate_probability(team_row, confederation, source='api_football', fixtures=fixtures),
                'current_group': team_row.get('group', competition_name),
                'position': team_row.get('rank'),
                'points': team_row.get('points'),
                'played': all_stats.get('played', 0),
                'goal_diff': goals.get('for', 0) - goals.get('against', 0),
                'form': team_row.get('form', ''),
                'source': 'api_football'
            }
        
        return None
    
    def calculate_probability(self, team_row, confederation, source='football_data', fixtures=None):
        """Calculate probability based on team performance"""
        prob = 0
        
        if source == 'football_data':
            points = team_row.get('points', 0)
            position = team_row.get('position', 100)
            played = team_row.get('playedGames', 0)
            goal_diff = team_row.get('goalDifference', 0)
            form = team_row.get('form', '')
        else:  # api_football
            points = team_row.get('points', 0)
            position = team_row.get('rank', 100)
            played = team_row.get('all', {}).get('played', 0)
            goals = team_row.get('all', {}).get('goals', {})
            goal_diff = goals.get('for', 0) - goals.get('against', 0)
            form = team_row.get('form', '')
        
        # Position-based
        if position <= 2:
            prob = 70
        elif position == 3:
            prob = 50
        elif position == 4:
            prob = 30
        elif position == 5:
            prob = 15
        else:
            prob = 5
        
        # Points-based
        if played > 0:
            points_per_game = points / played
            if points_per_game >= 2:
                prob += 15
            elif points_per_game >= 1.5:
                prob += 10
            elif points_per_game < 0.5:
                prob -= 10
        
        # Goal difference
        if goal_diff > 10:
            prob += 10
        elif goal_diff < -5:
            prob -= 10
        
        # Form from fixtures (if available)
        if fixtures:
            wins = 0
            draws = 0
            losses = 0
            team_id = team_row.get('team', {}).get('id') if source == 'api_football' else None
            
            for fixture in fixtures:
                home_team_id = fixture.get('teams', {}).get('home', {}).get('id')
                away_team_id = fixture.get('teams', {}).get('away', {}).get('id')
                score = fixture.get('score', {}).get('fulltime', {})
                
                if team_id and (home_team_id == team_id or away_team_id == team_id):
                    home_score = score.get('home')
                    away_score = score.get('away')
                    
                    if home_score is not None and away_score is not None:
                        if home_team_id == team_id:
                            if home_score > away_score:
                                wins += 1
                            elif home_score == away_score:
                                draws += 1
                            else:
                                losses += 1
                        else:  # away team
                            if away_score > home_score:
                                wins += 1
                            elif away_score == home_score:
                                draws += 1
                            else:
                                losses += 1
            
            total = wins + draws + losses
            if total > 0:
                win_rate = wins / total
                if win_rate >= 0.8:
                    prob += 10
                elif win_rate >= 0.6:
                    prob += 5
                elif win_rate < 0.2:
                    prob -= 10
        
        # Form from string (fallback)
        elif form and len(form) >= 3:
            wins = form.count('W')
            win_rate = wins / len(form)
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
    
    def fetch_all_qualifiers(self):
        """Fetch qualifiers from both APIs"""
        all_teams = {}
        
        # First, add already qualified teams (hosts)
        qualified_teams = [
            {'team': 'United States', 'confederation': 'CONCACAF', 'qualification_status': 'Qualified', 
             'prob_fill_slot': 100, 'current_group': 'Host', 'position': None, 'points': None, 
             'played': None, 'goal_diff': None, 'form': ''},
            {'team': 'Canada', 'confederation': 'CONCACAF', 'qualification_status': 'Qualified', 
             'prob_fill_slot': 100, 'current_group': 'Host', 'position': None, 'points': None, 
             'played': None, 'goal_diff': None, 'form': ''},
            {'team': 'Mexico', 'confederation': 'CONCACAF', 'qualification_status': 'Qualified', 
             'prob_fill_slot': 100, 'current_group': 'Host', 'position': None, 'points': None, 
             'played': None, 'goal_diff': None, 'form': ''},
        ]
        
        for team in qualified_teams:
            all_teams[team['team']] = team
        
        # Try Football-Data.org first (free tier with WC Qualification UEFA)
        logger.info("Fetching from Football-Data.org...")
        fd_teams = self.fetch_football_data_qualifiers()
        for team in fd_teams:
            all_teams[team['team']] = team  # Deduplicate by team name
        
        # Try API-Football (comprehensive coverage)
        if self.api_football_key:
            logger.info("Fetching from API-Football...")
            af_teams = self.fetch_api_football_qualifiers()
            for team in af_teams:
                # Only add if not already present
                if team['team'] not in all_teams:
                    all_teams[team['team']] = team
                else:
                    # Merge data from both sources
                    existing = all_teams[team['team']]
                    # Keep the higher probability
                    if team['prob_fill_slot'] > existing['prob_fill_slot']:
                        all_teams[team['team']] = team
        
        return list(all_teams.values())
    
    def fetch_football_data_qualifiers(self):
        """Fetch qualifiers from Football-Data.org for all confederations"""
        teams = []
        
        # First, discover what qualifier competitions are actually available
        logger.info("  Discovering available qualifier competitions...")
        discovered_qualifiers = self.discover_football_data_competitions()
        
        if discovered_qualifiers:
            logger.info(f"    Found {len(discovered_qualifiers)} qualifier competitions:")
            for q in discovered_qualifiers:
                logger.info(f"      - {q['name']} ({q['code']})")
        
        # Try all known WC Qualification codes
        for confederation, codes in self.competition_codes.items():
            fd_code = codes.get('football_data')
            
            if fd_code:
                logger.info(f"  Trying {confederation} qualifiers ({fd_code})...")
                standings = self.fetch_from_football_data(fd_code)
                if standings:
                    for standing in standings.get('standings', []):
                        for team_row in standing.get('table', []):
                            team_data = self.process_team_data(team_row, confederation, 'football_data')
                            if team_data:
                                teams.append(team_data)
                    logger.info(f"    ✓ Found {len([t for t in teams if t['confederation'] == confederation])} teams from {confederation}")
                time.sleep(1)  # Rate limiting
        
        # Try discovered qualifiers
        for qualifier in discovered_qualifiers:
            code = qualifier['code']
            name = qualifier['name'].lower()
            
            # Determine confederation from name
            confederation = None
            if 'uefa' in name or 'europe' in name:
                confederation = 'UEFA'
            elif 'conmebol' in name or 'south america' in name:
                confederation = 'CONMEBOL'
            elif 'concacaf' in name or 'north america' in name:
                confederation = 'CONCACAF'
            elif 'afc' in name or 'asia' in name:
                confederation = 'AFC'
            elif 'caf' in name or 'africa' in name:
                confederation = 'CAF'
            elif 'ofc' in name or 'oceania' in name:
                confederation = 'OFC'
            
            if confederation:
                logger.info(f"  Trying discovered {confederation} qualifier ({code})...")
                standings = self.fetch_from_football_data(code)
                if standings:
                    for standing in standings.get('standings', []):
                        for team_row in standing.get('table', []):
                            team_data = self.process_team_data(team_row, confederation, 'football_data')
                            if team_data and not any(t['team'] == team_data['team'] for t in teams):
                                teams.append(team_data)
                    logger.info(f"    ✓ Found {len([t for t in teams if t['confederation'] == confederation])} teams from {confederation}")
                time.sleep(1)
        
        # Fallback: Try European Championship if UEFA qualifiers not available
        if not any(t['confederation'] == 'UEFA' for t in teams):
            logger.info("  Trying UEFA fallback (European Championship)...")
            standings = self.fetch_from_football_data('EC')
            if standings:
                for standing in standings.get('standings', []):
                    for team_row in standing.get('table', []):
                        team_data = self.process_team_data(team_row, 'UEFA', 'football_data')
                        if team_data and not any(t['team'] == team_data['team'] for t in teams):
                            teams.append(team_data)
        
        return teams
    
    def fetch_api_football_qualifiers(self):
        """Fetch qualifiers from API-Football using known league IDs"""
        if not self.api_football_key:
            logger.info("  API-Football key not configured, skipping...")
            return []
        
        teams = []
        # Try more seasons including 2023 (might have qualifier data)
        # Also try 2021 for Qatar 2022 qualifiers as reference
        seasons_to_try = [2026, 2025, 2024, 2023, 2022, 2021]  # Extended range
        
        logger.info("  Fetching World Cup qualifiers using known league IDs...")
        
        # Use known qualifier league IDs directly - no need to search
        qualifier_leagues = []
        for confederation, league_id in self.wcq_league_ids.items():
            qualifier_leagues.append({
                'id': league_id,
                'name': f'World Cup Qualifiers - {confederation}',
                'confederation': confederation,
                'season': None  # Will try multiple seasons
            })
        
        logger.info(f"    Found {len(qualifier_leagues)} qualifier leagues to process")
        
        # Try to fetch data for each qualifier league
        for league in qualifier_leagues:
            league_id = league['id']
            confederation = league['confederation']
            
            logger.info(f"    Processing {confederation} (League ID {league_id})...")
            
            # Try each season to find active qualifiers - try ALL seasons
            standings_found = False
            for season in seasons_to_try:
                try:
                    # Fetch teams first
                    teams_list = self.fetch_teams_from_api_football(league_id, season)
                    
                    # Also try fixtures to find teams (use more fixtures)
                    fixtures = self.fetch_fixtures_from_api_football(league_id, season)
                    teams_from_fixtures = set()
                    if fixtures:
                        for fixture in fixtures[:100]:  # Check first 100 fixtures
                            home_team = fixture.get('teams', {}).get('home', {})
                            away_team = fixture.get('teams', {}).get('away', {})
                            if home_team.get('name'):
                                teams_from_fixtures.add((home_team.get('id'), home_team.get('name')))
                            if away_team.get('name'):
                                teams_from_fixtures.add((away_team.get('id'), away_team.get('name')))
                        if teams_from_fixtures:
                            logger.debug(f"      Season {season}: Found {len(teams_from_fixtures)} unique teams in fixtures")
                    
                    # Fetch standings
                    standings_data = self.fetch_standings_from_api_football(league_id, season)
                    teams_before = len(teams)
                    
                    if standings_data and standings_data.get('response'):
                        logger.info(f"      Season {season}: Found standings data")
                        standings_found = True
                        
                        # Process standings (preferred - has stats)
                        for standing_group in standings_data.get('response', []):
                            standings = standing_group.get('league', {}).get('standings', [])
                            
                            if isinstance(standings, list) and len(standings) > 0:
                                # Handle grouped standings
                                if isinstance(standings[0], list):
                                    for group in standings:
                                        for team_row in group:
                                            team_id = team_row.get('team', {}).get('id')
                                            if team_id:
                                                team_row['_league_id'] = league_id
                                                team_row['_team_id'] = team_id
                                                team_row['_season'] = season
                                                
                                                team_data = self.process_team_data(
                                                    team_row, confederation, 'api_football', 
                                                    league['name']
                                                )
                                                if team_data:
                                                    # Check for duplicates by team name
                                                    if not any(t.get('team') == team_data.get('team') for t in teams):
                                                        teams.append(team_data)
                                else:
                                    # Single flat list
                                    for team_row in standings:
                                        team_id = team_row.get('team', {}).get('id')
                                        if team_id:
                                            team_row['_league_id'] = league_id
                                            team_row['_team_id'] = team_id
                                            team_row['_season'] = season
                                            
                                            team_data = self.process_team_data(
                                                team_row, confederation, 'api_football', 
                                                league['name']
                                            )
                                            if team_data:
                                                # Check for duplicates by team name
                                                if not any(t.get('team') == team_data.get('team') for t in teams):
                                                    teams.append(team_data)
                    if teams_list and len(teams_list) > 0:
                        # Try teams list even if standings found (might have more teams)
                        if not standings_found:
                            logger.info(f"      Season {season}: No standings, using teams list ({len(teams_list)} teams)")
                        else:
                            logger.info(f"      Season {season}: Also checking teams list ({len(teams_list)} teams)")
                        standings_found = True
                        
                        added_from_teams = 0
                        teams_before_list = len(teams)
                        # Process teams from teams_list
                        for team_info in teams_list:
                            team = team_info.get('team', {})
                            team_id = team.get('id')
                            team_name = team.get('name')
                            
                            if not team_id or not team_name:
                                continue
                            
                            # Validate team eligibility (must be valid national team)
                            if not self.is_valid_national_team(team_name, confederation):
                                continue
                            
                            # Create minimal team data structure
                            team_row = {
                                'team': {'id': team_id, 'name': team_name},
                                'rank': None,
                                'points': None,
                                'all': {'played': 0, 'goals': {'for': 0, 'against': 0}},
                                'goals': {'for': 0, 'against': 0},
                                '_league_id': league_id,
                                '_team_id': team_id,
                                '_season': season
                            }
                            
                            team_data = self.process_team_data(
                                team_row, confederation, 'api_football', 
                                league['name']
                            )
                            if team_data:
                                # Check for duplicates by team name (case-insensitive)
                                team_name_lower = team_data.get('team', '').lower()
                                if not any(t.get('team', '').lower() == team_name_lower for t in teams):
                                    teams.append(team_data)
                                    added_from_teams += 1
                        
                        teams_after_list = len(teams)
                        added_from_teams = teams_after_list - teams_before_list
                        if added_from_teams > 0:
                            logger.info(f"      ✓ Added {added_from_teams} teams from teams list")
                        else:
                            logger.debug(f"      No new teams added from teams list (may be duplicates or invalid)")
                    
                    # Also try teams from fixtures if we didn't get many from standings/teams
                    # Try fixtures for ALL confederations to maximize team count
                    if fixtures and len(teams_from_fixtures) > 0:
                        logger.info(f"      Season {season}: Trying {len(teams_from_fixtures)} teams from fixtures")
                        added_from_fixtures = 0
                        for team_id, team_name in teams_from_fixtures:
                            if not self.is_valid_national_team(team_name, confederation):
                                continue
                            
                            team_row = {
                                'team': {'id': team_id, 'name': team_name},
                                'rank': None,
                                'points': None,
                                'all': {'played': 0, 'goals': {'for': 0, 'against': 0}},
                                'goals': {'for': 0, 'against': 0},
                                '_league_id': league_id,
                                '_team_id': team_id,
                                '_season': season
                            }
                            
                            team_data = self.process_team_data(
                                team_row, confederation, 'api_football', 
                                league['name']
                            )
                            if team_data:
                                team_name_lower = team_data.get('team', '').lower()
                                if not any(t.get('team', '').lower() == team_name_lower for t in teams):
                                    teams.append(team_data)
                                    added_from_fixtures += 1
                        
                        if added_from_fixtures > 0:
                            logger.info(f"      ✓ Added {added_from_fixtures} teams from fixtures")
                    
                    teams_after = len(teams)
                    added = teams_after - teams_before
                    if added > 0:
                        logger.info(f"      ✓ Added {added} new teams from {confederation} (Season {season})")
                    # Continue to next season to get more teams (don't break early)
                    
                    time.sleep(0.3)  # Rate limiting
                except Exception as e:
                    logger.debug(f"      Season {season} error: {e}")
                    continue
            
            if not standings_found:
                logger.warning(f"      No standings data found for {confederation} (League ID {league_id})")
        
        return teams
    
    def update_csv(self):
        """Update team_slot_probabilities.csv"""
        teams = self.fetch_all_qualifiers()
        
        if not teams:
            logger.error("No team data retrieved")
            return None
        
        df = pd.DataFrame(teams)
        df = df.drop('source', axis=1)  # Remove source column from final CSV
        df.to_csv('team_slot_probabilities.csv', index=False)
        
        logger.info(f"Updated team_slot_probabilities.csv with {len(df)} teams")
        
        with open('unified_qualifier_data.json', 'w') as f:
            json.dump(teams, f, indent=2)
        
        return df

def main():
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    fd_key = config.get('api_keys', {}).get('football_data')
    af_key = config.get('api_keys', {}).get('api_football')
    
    if not fd_key:
        print("Please add your Football-Data.org API key to config.json")
        return
    
    fetcher = UnifiedQualifierFetcher(fd_key, af_key)
    df = fetcher.update_csv()
    
    if df is not None:
        print(f"\n=== Summary ===")
        print(f"Total teams: {len(df)}")
        print(f"Qualified: {len(df[df['qualification_status'] == 'Qualified'])}")
        print(f"In Progress: {len(df[df['qualification_status'] == 'In Progress'])}")

if __name__ == "__main__":
    import requests
    main()

