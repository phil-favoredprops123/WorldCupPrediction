#!/usr/bin/env python3
"""
API Key Setup Script for FIFA World Cup 2026 Data Sources

This script helps you configure API keys for all data sources.
"""

import json
import os
from typing import Dict

def load_config(config_path: str = "config.json") -> Dict:
    """Load configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        return {}

def save_config(config: Dict, config_path: str = "config.json") -> None:
    """Save configuration to JSON file"""
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

def setup_api_keys():
    """Interactive setup of API keys"""
    config = load_config()
    
    print("=== FIFA World Cup 2026 Data Source API Key Setup ===\n")
    print("This script will help you configure API keys for all data sources.")
    print("You can skip any API key by pressing Enter.\n")
    
    # Get API keys from user
    api_keys = config.get('api_keys', {})
    
    # FIFA Official API
    print("1. FIFA Official API")
    print("   - Get your API key from: https://www.fifa.com/fifaplus/en/tournaments/mens/worldcup/canadamexicousa2026")
    print("   - This provides official rankings and match data")
    fifa_key = input("   Enter FIFA API key (or press Enter to skip): ").strip()
    if fifa_key:
        api_keys['fifa'] = fifa_key
    
    # UEFA API
    print("\n2. UEFA API")
    print("   - Get your API key from: https://www.uefa.com/insideuefa/about-uefa/administration/marketing/")
    print("   - This provides European football data")
    uefa_key = input("   Enter UEFA API key (or press Enter to skip): ").strip()
    if uefa_key:
        api_keys['uefa'] = uefa_key
    
    # Football-Data.org (Backup for UEFA/CONMEBOL)
    print("\n3. Football-Data.org API")
    print("   - Get your API key from: https://www.football-data.org/client/register")
    print("   - Free tier: 10 requests/minute")
    print("   - Covers: UEFA, CONMEBOL, CONCACAF, AFC")
    football_data_key = input("   Enter Football-Data API key (or press Enter to skip): ").strip()
    if football_data_key:
        api_keys['football_data'] = football_data_key
    
    # API-Football (Comprehensive coverage)
    print("\n4. API-Football")
    print("   - Get your API key from: https://rapidapi.com/api-sports/api/api-football")
    print("   - Free tier: 100 requests/day")
    print("   - Covers: All confederations")
    api_football_key = input("   Enter API-Football key (or press Enter to skip): ").strip()
    if api_football_key:
        api_keys['api_football'] = api_football_key
    
    # SofaScore API
    print("\n5. SofaScore API")
    print("   - Get your API key from: https://www.sofascore.com/api")
    print("   - Covers: All confederations with detailed statistics")
    sofascore_key = input("   Enter SofaScore API key (or press Enter to skip): ").strip()
    if sofascore_key:
        api_keys['sofascore'] = sofascore_key
    
    # FlashScore API
    print("\n6. FlashScore API")
    print("   - Get your API key from: https://www.flashscore.com/api")
    print("   - Covers: All confederations")
    flashscore_key = input("   Enter FlashScore API key (or press Enter to skip): ").strip()
    if flashscore_key:
        api_keys['flashscore'] = flashscore_key
    
    # ESPN API
    print("\n7. ESPN API")
    print("   - Get your API key from: https://developer.espn.com/")
    print("   - Covers: All confederations")
    espn_key = input("   Enter ESPN API key (or press Enter to skip): ").strip()
    if espn_key:
        api_keys['espn'] = espn_key
    
    # Update config with new API keys
    config['api_keys'] = api_keys
    save_config(config)
    
    print(f"\n=== Configuration Complete ===")
    print(f"API keys configured: {len([k for k in api_keys.values() if k])}")
    print(f"Config saved to: config.json")
    
    # Show next steps
    print(f"\n=== Next Steps ===")
    print("1. Test your API keys:")
    print("   python -c \"from data_source_manager import DataSourceManager; dm = DataSourceManager(); print('FIFA Rankings:', len(dm.get_fifa_rankings()))\"")
    print("\n2. Run a test update:")
    print("   python update_probabilities.py --match-day 1")
    print("\n3. Set up automated updates:")
    print("   python scheduler.py")

def test_api_keys():
    """Test configured API keys"""
    import requests
    from data_source_manager import DataSourceManager
    
    print("=== Testing API Keys ===\n")
    
    # Test Football-Data.org API directly
    print("1. Testing Football-Data.org API...")
    config = load_config()
    football_data_key = config.get('api_keys', {}).get('football_data', '')
    
    if football_data_key and football_data_key != 'YOUR_FOOTBALL_DATA_API_KEY':
        try:
            headers = {"X-Auth-Token": football_data_key}
            response = requests.get("https://api.football-data.org/v4/competitions", headers=headers, timeout=10)
            response.raise_for_status()
            competitions = response.json()
            print(f"   ✓ Football-Data.org API: {len(competitions.get('competitions', []))} competitions found")
            
            # Test getting UEFA competitions
            uefa_comp = [c for c in competitions.get('competitions', []) if 'UEFA' in c.get('area', {}).get('name', '')]
            if uefa_comp:
                print(f"   ✓ UEFA competitions available: {len(uefa_comp)}")
            
        except requests.exceptions.RequestException as e:
            print(f"   ✗ Football-Data.org API failed: {e}")
        except Exception as e:
            print(f"   ✗ Football-Data.org API error: {e}")
    else:
        print(f"   ⚠ Football-Data.org API key not configured")
    
    manager = DataSourceManager()
    
    # Test FIFA rankings
    print("\n2. Testing FIFA Rankings...")
    try:
        rankings = manager.get_fifa_rankings()
        print(f"   ✓ FIFA Rankings: {len(rankings)} teams found")
    except Exception as e:
        print(f"   ✗ FIFA Rankings failed: {e}")
    
    # Test UEFA data
    print("\n3. Testing UEFA Data...")
    try:
        uefa_data = manager.get_uefa_data('matches')
        print(f"   ✓ UEFA Data: {len(uefa_data.get('matches', []))} matches found")
    except Exception as e:
        print(f"   ✗ UEFA Data failed: {e}")
    
    # Test other confederations
    print("\n4. Testing Other Confederations...")
    for conf in ['CAF', 'CONCACAF', 'AFC', 'CONMEBOL', 'OFC']:
        try:
            data = manager.get_confederation_data(conf, 'matches')
            print(f"   ✓ {conf} Data: {len(data.get('matches', []))} matches found")
        except Exception as e:
            print(f"   ✗ {conf} Data failed: {e}")

def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test_api_keys()
    else:
        setup_api_keys()

if __name__ == "__main__":
    main()
