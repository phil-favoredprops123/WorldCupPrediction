# Quick Setup Guide: Streamlit Team Collector

## Step 1: Install Streamlit

```bash
pip install streamlit
```

Or install all requirements:
```bash
pip install -r requirements_streamlit.txt
```

## Step 2: Run the App

```bash
streamlit run streamlit_collector.py
```

This will:
- Start the Streamlit server
- Open your browser automatically at `http://localhost:8501`
- Show the team collection dashboard

## Step 3: Use the Dashboard

1. **Check API Key**: The sidebar should show "✅ API Key Loaded"
2. **View Current Teams**: See all collected teams in the main area
3. **Run Collection**: Click "🚀 Run Collection Now" button
4. **Monitor Progress**: Watch the progress bar and metrics update

## Step 4: Keep It Running

### Simple: Keep Terminal Open
Just keep the terminal window open where you ran `streamlit run`. The app stays active.

### Background: Use nohup (Mac/Linux)
```bash
nohup streamlit run streamlit_collector.py > streamlit.log 2>&1 &
```

Then access at `http://localhost:8501`

### Background: Use Screen (Mac/Linux)
```bash
# Start screen session
screen -S streamlit

# Run streamlit
streamlit run streamlit_collector.py

# Detach: Press Ctrl+A, then D
# Reattach: screen -r streamlit
```

### Stop the App
- If running in terminal: Press `Ctrl+C`
- If running in background: Find the process and kill it
  ```bash
  ps aux | grep streamlit
  kill <PID>
  ```

## Features

✅ **Real-time Dashboard**: See all collected teams  
✅ **Progress Tracking**: Monitor API request usage (100/day limit)  
✅ **Manual Collection**: Run collection on-demand  
✅ **Team Filters**: Filter by confederation and status  
✅ **Export Data**: Download CSV of current teams  

## Troubleshooting

**Port already in use?**
```bash
streamlit run streamlit_collector.py --server.port 8502
```

**API Key not found?**
- Check that `config.json` exists
- Verify `api_football` key is set in `config.json`

**No teams showing?**
- Click "Run Collection Now" to start collecting
- Check `intelligent_collector.log` for errors

**Want to see logs?**
```bash
tail -f intelligent_collector.log
```

