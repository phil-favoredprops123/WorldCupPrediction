# Streamlit Team Collector

This Streamlit app allows you to run and monitor the intelligent team collector for World Cup 2026 qualifiers.

## Setup Steps

### 1. Install Streamlit (if not already installed)

```bash
pip install streamlit pandas requests
```

Or install from requirements file:

```bash
pip install -r requirements_streamlit.txt
```

### 2. Run the Streamlit App

```bash
streamlit run streamlit_collector.py
```

The app will open in your browser at `http://localhost:8501`

## Features

### Dashboard
- **Current Teams**: View all collected teams with filters
- **By Confederation**: See team counts per confederation
- **Progress Tracking**: Monitor API requests used (100/day limit)
- **Real-time Updates**: Auto-refresh option

### Controls
- **Run Collection Now**: Manually trigger a collection run
- **Progress Metrics**: See how many requests have been used
- **Team Filters**: Filter by confederation and qualification status
- **Download CSV**: Export current team data

## How It Works

1. Click "Run Collection Now" to start collecting teams
2. The collector will use up to 100 API requests (your daily limit)
3. Progress is saved automatically
4. Teams are added to `team_slot_probabilities.csv`
5. Refresh the page to see updated results

## Tips

- **Check Progress**: Use the sidebar to see how many requests remain
- **Run Strategically**: Since you have 100 requests/day, run once per day when needed
- **Monitor Logs**: Check `intelligent_collector.log` for detailed collection logs
- **Auto-refresh**: Enable auto-refresh to see updates without manual refresh

## Keeping It Running

### Option 1: Keep Streamlit Running
- Keep the terminal window open
- The app will stay running as long as the terminal is active

### Option 2: Run in Background (Linux/Mac)
```bash
nohup streamlit run streamlit_collector.py > streamlit.log 2>&1 &
```

### Option 3: Use Screen/Tmux
```bash
# Using screen
screen -S streamlit
streamlit run streamlit_collector.py
# Press Ctrl+A then D to detach

# Using tmux
tmux new -s streamlit
streamlit run streamlit_collector.py
# Press Ctrl+B then D to detach
```

### Option 4: Run as a Service (Linux)
Create a systemd service file for automatic startup on boot.

## Troubleshooting

- **API Key Not Found**: Make sure `config.json` has the `api_football` key
- **No Teams Found**: Check `intelligent_collector.log` for errors
- **Port Already in Use**: Streamlit uses port 8501 by default. Change it with:
  ```bash
  streamlit run streamlit_collector.py --server.port 8502
  ```

