#!/usr/bin/env python3
"""
FIFA World Cup 2026 Team Slot Probability Updater

This script updates team probabilities based on:
1. Current match results
2. Historical performance data
3. FIFA rankings
4. Group standings
5. Remaining fixtures

Usage:
    python update_probabilities.py --match-day 1
    python update_probabilities.py --auto-update
"""

import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
import argparse
import logging
from typing import Dict, List, Tuple
import os
from data_source_manager import DataSourceManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WorldCupProbabilityUpdater:
    def __init__(self, team_data_path: str = "team_slot_probabilities.csv", 
                 match_data_path: str = "slot_to_city_mapping.csv",
                 config_path: str = "config.json"):
        self.team_data_path = team_data_path
        self.match_data_path = match_data_path
        self.config_path = config_path
        self.team_df = None
        self.match_df = None
        self.fifa_rankings = {}
        self.data_manager = DataSourceManager(config_path)
        
    def load_data(self):
        """Load current team and match data"""
        try:
            self.team_df = pd.read_csv(self.team_data_path)
            self.match_df = pd.read_csv(self.match_data_path)
            logger.info(f"Loaded {len(self.team_df)} teams and {len(self.match_df)} matches")
        except FileNotFoundError as e:
            logger.error(f"Data file not found: {e}")
            raise
    
    def get_fifa_rankings(self) -> Dict[str, int]:
        """Fetch current FIFA rankings from API or file"""
        return self.data_manager.get_fifa_rankings()
    
    def calculate_base_probability(self, team: str, confederation: str, 
                                 fifa_rank: int, qualification_status: str) -> float:
        """Calculate base probability based on team strength and confederation"""
        
        if qualification_status == "Qualified":
            return 100.0
        
        # Base probability from FIFA ranking (inverted - lower rank = higher probability)
        base_prob = max(5, 100 - (fifa_rank * 0.8))
        
        # Confederation multipliers (based on historical qualification rates)
        conf_multipliers = {
            'UEFA': 1.2,      # Strongest confederation
            'CONMEBOL': 1.1,   # Very strong
            'AFC': 0.9,        # Moderate
            'CAF': 0.8,        # Moderate
            'CONCACAF': 0.7,   # Weaker (excluding hosts)
            'OFC': 0.3         # Weakest
        }
        
        # Apply confederation multiplier
        adjusted_prob = base_prob * conf_multipliers.get(confederation, 1.0)
        
        # Cap probabilities
        return min(95, max(1, adjusted_prob))
    
    def update_from_match_results(self, match_results: List[Dict]) -> None:
        """Update probabilities based on recent match results"""
        for result in match_results:
            team1, team2 = result['team1'], result['team2']
            score1, score2 = result['score1'], result['score2']
            match_type = result['type']  # 'qualifier', 'group_stage', 'knockout'
            
            # Calculate performance impact
            if score1 > score2:
                winner, loser = team1, team2
                winner_impact = 5
                loser_impact = -3
            elif score1 < score2:
                winner, loser = team2, team1
                winner_impact = 5
                loser_impact = -3
            else:
                # Draw
                winner_impact = 1
                loser_impact = 1
            
            # Apply updates
            self.update_team_probability(team1, winner_impact if team1 == winner else loser_impact)
            self.update_team_probability(team2, winner_impact if team2 == winner else loser_impact)
    
    def update_team_probability(self, team: str, adjustment: float) -> None:
        """Update a team's probability by the given adjustment"""
        mask = self.team_df['team'] == team
        if mask.any():
            current_prob = self.team_df.loc[mask, 'prob_fill_slot'].iloc[0]
            new_prob = max(0, min(100, current_prob + adjustment))
            self.team_df.loc[mask, 'prob_fill_slot'] = new_prob
            logger.info(f"Updated {team}: {current_prob:.1f}% -> {new_prob:.1f}%")
    
    def update_from_group_standings(self, group_standings: Dict[str, List[Dict]]) -> None:
        """Update probabilities based on current group standings"""
        for group, teams in group_standings.items():
            # Sort by points, goal difference, etc.
            sorted_teams = sorted(teams, key=lambda x: (x['points'], x['goal_diff']), reverse=True)
            
            # Update probabilities based on position
            for i, team_data in enumerate(sorted_teams):
                team = team_data['team']
                position = i + 1
                
                # Position-based probability adjustment
                if position == 1:
                    adjustment = 10  # Group leader
                elif position == 2:
                    adjustment = 5   # Second place
                elif position == 3:
                    adjustment = -5  # Third place
                else:
                    adjustment = -10 # Fourth place or lower
                
                self.update_team_probability(team, adjustment)
    
    def update_from_remaining_fixtures(self, remaining_fixtures: List[Dict]) -> None:
        """Update probabilities based on remaining fixtures difficulty"""
        for fixture in remaining_fixtures:
            team = fixture['team']
            opponent_strength = fixture['opponent_strength']  # 1-10 scale
            home_advantage = fixture.get('home_advantage', 0)  # 0-1 scale
            
            # Calculate difficulty adjustment
            difficulty = opponent_strength / 10
            adjustment = (difficulty - 0.5) * 5 + home_advantage * 2
            
            self.update_team_probability(team, adjustment)
    
    def save_updated_data(self, backup: bool = True) -> None:
        """Save updated team data"""
        if backup:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"team_slot_probabilities_backup_{timestamp}.csv"
            self.team_df.to_csv(backup_path, index=False)
            logger.info(f"Created backup: {backup_path}")
        
        self.team_df.to_csv(self.team_data_path, index=False)
        logger.info(f"Updated {self.team_data_path}")
    
    def run_update(self, match_day: int = None, auto_update: bool = False):
        """Main update process"""
        logger.info("Starting probability update process")
        
        # Load data
        self.load_data()
        
        # Update probabilities using data from all sources
        self.team_df = self.data_manager.update_team_probabilities_from_sources(self.team_df)
        
        # Get FIFA rankings
        self.fifa_rankings = self.get_fifa_rankings()
        
        # Recalculate base probabilities with updated data
        for idx, row in self.team_df.iterrows():
            team = row['team']
            confederation = row['confederation']
            fifa_rank = self.fifa_rankings.get(team, 50)
            qualification_status = row['qualification_status']
            
            base_prob = self.calculate_base_probability(team, confederation, fifa_rank, qualification_status)
            self.team_df.at[idx, 'prob_fill_slot'] = base_prob
        
        # Get recent match results and update accordingly
        date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        date_to = datetime.now().strftime('%Y-%m-%d')
        
        for conf in ['UEFA', 'CAF', 'CONCACAF', 'AFC', 'CONMEBOL', 'OFC']:
            matches = self.data_manager.get_match_results(conf, date_from, date_to)
            self.update_from_match_results(matches)
        
        # Get group standings and update accordingly
        for conf in ['UEFA', 'CAF', 'CONCACAF', 'AFC', 'CONMEBOL', 'OFC']:
            standings = self.data_manager.get_group_standings(conf)
            self.update_from_group_standings(standings)
        
        # Save updated data
        self.save_updated_data()
        
        logger.info("Probability update completed")

def main():
    parser = argparse.ArgumentParser(description='Update World Cup team probabilities')
    parser.add_argument('--match-day', type=int, help='Specific match day to process')
    parser.add_argument('--auto-update', action='store_true', help='Run automatic update')
    parser.add_argument('--team-data', default='team_slot_probabilities.csv', help='Team data file path')
    parser.add_argument('--match-data', default='slot_to_city_mapping.csv', help='Match data file path')
    
    args = parser.parse_args()
    
    updater = WorldCupProbabilityUpdater(args.team_data, args.match_data)
    
    if args.match_day:
        updater.run_update(match_day=args.match_day)
    elif args.auto_update:
        updater.run_update(auto_update=True)
    else:
        updater.run_update()

if __name__ == "__main__":
    main()
