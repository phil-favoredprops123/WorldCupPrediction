#!/usr/bin/env python3
"""
Example of integrating with real data sources for World Cup probabilities

This shows how to connect to actual APIs and data sources to get:
- FIFA rankings
- Match results
- Group standings
- Team form data
"""

import requests
import pandas as pd
import json
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class DataIntegrationExample:
    """Example class showing how to integrate with real data sources"""
    
    def __init__(self):
        self.api_key = None  # You'd get this from FIFA or other providers
        self.base_url = "https://api.fifa.com"
    
    def get_fifa_rankings(self) -> Dict[str, int]:
        """
        Get current FIFA rankings from API
        In practice, you'd use FIFA's official API or a reliable third-party source
        """
        try:
            # Example API call (replace with actual FIFA API)
            url = f"{self.base_url}/ranking/fifa"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            rankings = {}
            
            for team in data.get('rankings', []):
                rankings[team['team_name']] = team['rank']
            
            return rankings
            
        except Exception as e:
            logger.error(f"Error fetching FIFA rankings: {e}")
            return self.get_fallback_rankings()
    
    def get_fallback_rankings(self) -> Dict[str, int]:
        """Fallback rankings if API fails"""
        return {
            'Argentina': 1, 'France': 2, 'Brazil': 3, 'England': 4, 'Belgium': 5,
            'Netherlands': 6, 'Portugal': 7, 'Spain': 8, 'Italy': 9, 'Croatia': 10
        }
    
    def get_match_results(self, date_from: str, date_to: str) -> List[Dict]:
        """
        Get match results for a date range
        """
        try:
            url = f"{self.base_url}/matches"
            params = {
                'date_from': date_from,
                'date_to': date_to,
                'competition': 'FIFA_WORLD_CUP_2026'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            matches = []
            
            for match in data.get('matches', []):
                matches.append({
                    'team1': match['home_team'],
                    'team2': match['away_team'],
                    'score1': match['home_score'],
                    'score2': match['away_score'],
                    'date': match['date'],
                    'type': match['competition_stage']
                })
            
            return matches
            
        except Exception as e:
            logger.error(f"Error fetching match results: {e}")
            return []
    
    def get_group_standings(self, group: str) -> List[Dict]:
        """
        Get current group standings
        """
        try:
            url = f"{self.base_url}/standings/{group}"
            response = requests.get(url)
            response.raise_for_status()
            
            data = response.json()
            standings = []
            
            for team in data.get('teams', []):
                standings.append({
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
            
            return standings
            
        except Exception as e:
            logger.error(f"Error fetching group standings: {e}")
            return []
    
    def get_team_form_data(self, team: str, matches_back: int = 5) -> Dict:
        """
        Get recent form data for a team
        """
        try:
            url = f"{self.base_url}/teams/{team}/form"
            params = {'matches_back': matches_back}
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'team': team,
                'form': data.get('form', []),  # Last 5 results
                'goals_scored': data.get('goals_scored', 0),
                'goals_conceded': data.get('goals_conceded', 0),
                'clean_sheets': data.get('clean_sheets', 0),
                'wins': data.get('wins', 0),
                'draws': data.get('draws', 0),
                'losses': data.get('losses', 0)
            }
            
        except Exception as e:
            logger.error(f"Error fetching form data for {team}: {e}")
            return {'team': team, 'form': [], 'goals_scored': 0, 'goals_conceded': 0}
    
    def calculate_advanced_probability(self, team: str, confederation: str, 
                                     fifa_rank: int, form_data: Dict, 
                                     group_standings: List[Dict]) -> float:
        """
        Calculate advanced probability using multiple factors
        """
        # Base probability from FIFA ranking
        base_prob = max(5, 100 - (fifa_rank * 0.8))
        
        # Form factor (last 5 matches)
        form_score = 0
        if form_data['form']:
            for result in form_data['form']:
                if result == 'W':
                    form_score += 2
                elif result == 'D':
                    form_score += 0.5
                else:  # L
                    form_score -= 1
        
        form_factor = 1 + (form_score / 10)  # -1 to +1 range
        
        # Group position factor
        position_factor = 1.0
        for i, team_data in enumerate(group_standings):
            if team_data['team'] == team:
                position = i + 1
                if position == 1:
                    position_factor = 1.2
                elif position == 2:
                    position_factor = 1.1
                elif position == 3:
                    position_factor = 0.9
                else:
                    position_factor = 0.7
                break
        
        # Confederation strength
        conf_multipliers = {
            'UEFA': 1.2, 'CONMEBOL': 1.1, 'AFC': 0.9,
            'CAF': 0.8, 'CONCACAF': 0.7, 'OFC': 0.3
        }
        conf_factor = conf_multipliers.get(confederation, 1.0)
        
        # Calculate final probability
        final_prob = base_prob * form_factor * position_factor * conf_factor
        
        return min(95, max(1, final_prob))

# Example usage
if __name__ == "__main__":
    integrator = DataIntegrationExample()
    
    # Get FIFA rankings
    rankings = integrator.get_fifa_rankings()
    print("FIFA Rankings:", rankings)
    
    # Get recent match results
    matches = integrator.get_match_results("2024-01-01", "2024-12-31")
    print(f"Found {len(matches)} matches")
    
    # Get group standings
    group_a_standings = integrator.get_group_standings("A")
    print("Group A Standings:", group_a_standings)
    
    # Get team form
    argentina_form = integrator.get_team_form_data("Argentina")
    print("Argentina Form:", argentina_form)
