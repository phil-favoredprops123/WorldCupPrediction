#!/bin/bash
# Start background team collector in background
# This will run for 21 hours, using up to 100 API requests

cd "$(dirname "$0")"

# Run in background and log to file
nohup python3 background_team_collector.py > background_collector.log 2>&1 &

# Save PID
echo $! > background_collector.pid

echo "Background collector started (PID: $(cat background_collector.pid))"
echo "Monitor progress with: tail -f background_collector.log"
echo "Stop with: kill $(cat background_collector.pid)"

