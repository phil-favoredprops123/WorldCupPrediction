# 🚀 Quick Start: Streamlit Team Collector

## Install & Run (3 commands)

```bash
# 1. Install Streamlit
pip install streamlit

# 2. Run the app
streamlit run streamlit_collector.py

# 3. That's it! Browser opens automatically
```

## What You'll See

- **Dashboard** with current teams
- **Progress tracker** showing API requests used
- **Run button** to collect more teams
- **Team table** with filters and export

## Keep It Running

**Option 1: Keep terminal open** (simplest)
- Just leave the terminal window open

**Option 2: Background mode**
```bash
nohup streamlit run streamlit_collector.py &
```

**Option 3: Screen session**
```bash
screen -S streamlit
streamlit run streamlit_collector.py
# Press Ctrl+A then D to detach
```

## Daily Usage

1. Open browser to `http://localhost:8501`
2. Click "🚀 Run Collection Now" 
3. Wait for collection to complete (~5-10 minutes)
4. View updated teams in the dashboard
5. Repeat daily (100 requests/day limit)

That's it! 🎉
