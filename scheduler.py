#!/usr/bin/env python3
"""
Automated Scheduler for World Cup Probability Updates

This script runs the probability updater at scheduled intervals:
- During qualifiers: Daily
- During group stage: After each matchday
- During knockout stage: After each match
"""

import schedule
import time
import logging
from datetime import datetime, timedelta
from update_probabilities import WorldCupProbabilityUpdater
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WorldCupScheduler:
    def __init__(self, config_path: str = "config.json"):
        self.config = self.load_config(config_path)
        self.updater = WorldCupProbabilityUpdater()
        self.tournament_phase = self.determine_tournament_phase()
        
    def load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            return {}
    
    def determine_tournament_phase(self) -> str:
        """Determine current tournament phase based on date"""
        now = datetime.now()
        
        # Define tournament phases (adjust dates as needed)
        phases = {
            'qualifiers': (datetime(2024, 1, 1), datetime(2026, 5, 31)),
            'group_stage': (datetime(2026, 6, 11), datetime(2026, 6, 30)),
            'knockout_stage': (datetime(2026, 7, 1), datetime(2026, 7, 19))
        }
        
        for phase, (start, end) in phases.items():
            if start <= now <= end:
                return phase
        
        return 'pre_tournament'
    
    def run_qualifier_update(self):
        """Run update during qualifiers phase"""
        logger.info("Running qualifier update")
        try:
            self.updater.run_update()
            logger.info("Qualifier update completed successfully")
        except Exception as e:
            logger.error(f"Qualifier update failed: {e}")
    
    def run_group_stage_update(self):
        """Run update after group stage matchday"""
        logger.info("Running group stage update")
        try:
            # Get current matchday from match data
            matchday = self.get_current_matchday()
            self.updater.run_update(match_day=matchday)
            logger.info(f"Group stage update completed for matchday {matchday}")
        except Exception as e:
            logger.error(f"Group stage update failed: {e}")
    
    def run_knockout_update(self):
        """Run update after knockout stage match"""
        logger.info("Running knockout stage update")
        try:
            self.updater.run_update()
            logger.info("Knockout stage update completed")
        except Exception as e:
            logger.error(f"Knockout stage update failed: {e}")
    
    def get_current_matchday(self) -> int:
        """Get current matchday from match data"""
        try:
            match_df = self.updater.match_df
            if match_df is not None and not match_df.empty:
                # Find the latest matchday based on completed matches
                # This is a simplified approach - you'd implement more sophisticated logic
                return 1  # Placeholder
            return 1
        except Exception as e:
            logger.error(f"Error getting current matchday: {e}")
            return 1
    
    def setup_schedule(self):
        """Setup the update schedule based on tournament phase"""
        logger.info(f"Setting up schedule for {self.tournament_phase} phase")
        
        if self.tournament_phase == 'qualifiers':
            # Daily updates during qualifiers
            schedule.every().day.at("06:00").do(self.run_qualifier_update)
            schedule.every().day.at("18:00").do(self.run_qualifier_update)
            
        elif self.tournament_phase == 'group_stage':
            # After each matchday (typically every 2-3 days)
            schedule.every().day.at("23:00").do(self.run_group_stage_update)
            
        elif self.tournament_phase == 'knockout_stage':
            # After each match (more frequent)
            schedule.every().day.at("23:30").do(self.run_knockout_update)
            
        else:
            # Pre-tournament: weekly updates
            schedule.every().monday.at("09:00").do(self.run_qualifier_update)
    
    def run(self):
        """Main scheduler loop"""
        logger.info("Starting World Cup Probability Scheduler")
        self.setup_schedule()
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                logger.info("Scheduler stopped by user")
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying

def main():
    scheduler = WorldCupScheduler()
    scheduler.run()

if __name__ == "__main__":
    main()
