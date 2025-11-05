#!/usr/bin/env python3
"""
Streamlit app for running and monitoring the intelligent team collector
"""

import streamlit as st
import pandas as pd
import json
import time
from pathlib import Path
from datetime import datetime
import subprocess
import threading
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="World Cup Team Collector",
    page_icon="⚽",
    layout="wide"
)

def load_config():
    """Load API key from config"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            return config.get('api_keys', {}).get('api_football')
    except:
        return None

def get_team_stats():
    """Get current team statistics"""
    csv_path = Path('team_slot_probabilities.csv')
    if not csv_path.exists():
        return None, None
    
    try:
        df = pd.read_csv(csv_path)
        
        stats = {
            'total': len(df),
            'qualified': len(df[df['qualification_status'] == 'Qualified']),
            'in_progress': len(df[df['qualification_status'] == 'In Progress']),
            'by_confederation': df.groupby('confederation').size().to_dict()
        }
        
        return df, stats
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, None

def get_progress():
    """Get collection progress"""
    progress_file = Path('intelligent_progress.json')
    if progress_file.exists():
        try:
            with open(progress_file, 'r') as f:
                return json.load(f)
        except:
            return None
    return None

def run_collector_once():
    """Run collector directly (blocking)"""
    try:
        from intelligent_team_collector import IntelligentTeamCollector
        api_key = load_config()
        if api_key:
            collector = IntelligentTeamCollector(api_key, max_requests=100)
            collector.run()
            return True
    except Exception as e:
        st.error(f"Collection error: {e}")
        return False
    return False

# Main app
st.title("⚽ World Cup 2026 Team Collector")
st.markdown("---")

# Sidebar controls
with st.sidebar:
    st.header("Controls")
    
    api_key = load_config()
    if api_key:
        st.success(f"✅ API Key Loaded ({len(api_key)} chars)")
    else:
        st.error("❌ API Key Not Found")
        st.stop()
    
    st.markdown("---")
    
    # Manual run button
    if st.button("🚀 Run Collection Now", type="primary", use_container_width=True):
        with st.spinner("Running collection... This may take a few minutes."):
            success = run_collector_once()
            if success:
                st.success("Collection complete!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Collection failed. Check logs for details.")
    
    # Progress info
    progress = get_progress()
    if progress:
        st.markdown("---")
        st.subheader("Progress")
        st.metric("Requests Used", f"{progress.get('requests_made', 0)}/100")
        st.metric("Teams Found", progress.get('total_teams_found', 0))
        
        last_update = progress.get('last_update')
        if last_update:
            try:
                dt = datetime.fromisoformat(last_update)
                st.caption(f"Last update: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            except:
                pass

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.header("Current Teams")
    
    df, stats = get_team_stats()
    
    if df is not None and stats is not None:
        # Summary metrics
        metric_cols = st.columns(4)
        with metric_cols[0]:
            st.metric("Total Teams", stats['total'])
        with metric_cols[1]:
            st.metric("Qualified", stats['qualified'])
        with metric_cols[2]:
            st.metric("In Progress", stats['in_progress'])
        with metric_cols[3]:
            remaining = 48 - stats['qualified']
            st.metric("Spots Remaining", remaining)
        
        st.markdown("---")
        
        # By confederation
        st.subheader("By Confederation")
        conf_df = pd.DataFrame({
            'Confederation': list(stats['by_confederation'].keys()),
            'Teams': list(stats['by_confederation'].values())
        })
        st.dataframe(conf_df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Full team table
        st.subheader("All Teams")
        
        # Filters
        filter_cols = st.columns(3)
        with filter_cols[0]:
            conf_filter = st.multiselect(
                "Filter by Confederation",
                options=df['confederation'].unique(),
                default=df['confederation'].unique()
            )
        with filter_cols[1]:
            status_filter = st.multiselect(
                "Filter by Status",
                options=df['qualification_status'].unique(),
                default=df['qualification_status'].unique()
            )
        with filter_cols[2]:
            sort_by = st.selectbox(
                "Sort by",
                options=['team', 'confederation', 'prob_fill_slot', 'points'],
                index=2
            )
        
        # Filter dataframe
        filtered_df = df[
            (df['confederation'].isin(conf_filter)) &
            (df['qualification_status'].isin(status_filter))
        ].sort_values(by=sort_by, ascending=False)
        
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            height=400
        )
        
        # Download button
        csv_data = filtered_df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name=f"team_slot_probabilities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.warning("No team data found. Run collection to start gathering teams.")

with col2:
    st.header("Collection Status")
    
    progress = get_progress()
    
    if progress:
        requests_made = progress.get('requests_made', 0)
        requests_remaining = 100 - requests_made
        
        # Progress bar
        st.progress(requests_made / 100)
        st.caption(f"{requests_made}/100 requests used ({requests_remaining} remaining)")
        
        # Stats
        st.metric("Total Teams Found", progress.get('total_teams_found', 0))
        st.metric("Combinations Tried", len(progress.get('tried_combinations', [])))
        
        # Recent activity
        st.markdown("---")
        st.subheader("Recent Activity")
        tried = progress.get('tried_combinations', [])
        if tried:
            st.caption(f"Last {min(10, len(tried))} attempts:")
            for combo in list(tried)[-10:]:
                st.text(f"• {combo}")
    else:
        st.info("No collection progress yet. Click 'Run Collection Now' to start.")
    
    st.markdown("---")
    
    # Auto-refresh
    if st.checkbox("Auto-refresh (30s)", value=False):
        time.sleep(30)
        st.rerun()

# Footer
st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

