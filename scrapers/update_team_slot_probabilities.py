#!/usr/bin/env python3
"""
Refresh team_slot_probabilities.csv using the ESPN-based confederation scraper.

This replaces the Football-Data.org pipeline with one lightweight request per
confederation and reuses the same probability heuristics that were previously
inside QualifierDataFetcher.calculate_team_probability().
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory to path so script can be run from scrapers/ or project root
_SCRIPT_DIR = Path(__file__).parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd

from scrapers.confederation_scraper import (
    ConfederationStandingsCollector,
    StandingEntry,
    build_default_scrapers,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Output paths - can be overridden via environment variables for Lambda
OUTPUT_CSV = Path(os.getenv("OUTPUT_CSV_PATH", "team_slot_probabilities.csv"))
OUTPUT_JSON = Path(os.getenv("OUTPUT_JSON_PATH", "qualifier_data.json"))
OUTPUT_COLUMNS = [
    "team",
    "confederation",
    "qualification_status",
    "prob_fill_slot",
    "current_group",
    "position",
    "points",
    "played",
    "goal_diff",
    "form",
]

HOST_ROWS = [
    {
        "team": "United States",
        "confederation": "CONCACAF",
        "qualification_status": "Qualified",
        "prob_fill_slot": 100.0,
        "current_group": "Host",
        "position": "",
        "points": "",
        "played": "",
        "goal_diff": "",
        "form": "",
    },
    {
        "team": "Canada",
        "confederation": "CONCACAF",
        "qualification_status": "Qualified",
        "prob_fill_slot": 100.0,
        "current_group": "Host",
        "position": "",
        "points": "",
        "played": "",
        "goal_diff": "",
        "form": "",
    },
    {
        "team": "Mexico",
        "confederation": "CONCACAF",
        "qualification_status": "Qualified",
        "prob_fill_slot": 100.0,
        "current_group": "Host",
        "position": "",
        "points": "",
        "played": "",
        "goal_diff": "",
        "form": "",
    },
]

CONFED_MULTIPLIERS = {
    "UEFA": 1.0,
    "CONMEBOL": 1.0,
    "AFC": 0.95,
    "CAF": 0.95,
    "CONCACAF": 0.9,
    "OFC": 0.7,
}

# Lazy-loaded cache of historical qualification probabilities
_HISTORICAL_PROBS: Optional[
    Tuple[Dict[Tuple[str, str, int], float], Dict[Tuple[str, str, str, str], float]]
] = None


def load_historical_probs() -> Tuple[
    Dict[Tuple[str, str, int], float], Dict[Tuple[str, str, str, str], float]
]:
    global _HISTORICAL_PROBS
    if _HISTORICAL_PROBS is not None:
        return _HISTORICAL_PROBS
    lookup_path = Path(os.getenv("HISTORICAL_LOOKUP_PATH", "historical_probability_lookup.csv"))
    if not lookup_path.exists():
        logger.warning("Historical probability lookup not found at %s", lookup_path)
        _HISTORICAL_PROBS = ({}, {})
        return _HISTORICAL_PROBS
    df = pd.read_csv(lookup_path)
    rank_lookup: Dict[Tuple[str, str, int], float] = {}
    bucket_lookup: Dict[Tuple[str, str, str, str], float] = {}
    for _, row in df.iterrows():
        confed = str(row.get("confederation"))
        stage = str(row.get("stage"))
        prob = float(row.get("historical_qual_prob", 0.0))
        level = str(row.get("lookup_level", "rank")).lower()
        rank_value = row.get("rank")
        rank_bucket_value = str(row.get("rank_bucket", "unknown"))
        ppg_bucket_value = str(row.get("ppg_bucket", "all"))
        if level == "bucket" or pd.isna(rank_value):
            bucket_lookup[(confed, stage, rank_bucket_value, ppg_bucket_value)] = prob
        else:
            try:
                rank_key = int(rank_value)
                rank_lookup[(confed, stage, rank_key)] = prob
            except (TypeError, ValueError):
                continue
    _HISTORICAL_PROBS = (rank_lookup, bucket_lookup)
    logger.info(
        "Loaded %s rank-level and %s bucket-level historical probabilities.",
        len(rank_lookup),
        len(bucket_lookup),
    )
    return _HISTORICAL_PROBS


def get_rank_bucket(rank: int) -> str:
    if rank == 1:
        return "1"
    if rank == 2:
        return "2"
    if rank in (3, 4):
        return "3-4"
    if rank == 5:
        return "5"
    return "6+"


def get_ppg(points: int, games_played: int) -> float:
    if games_played <= 0:
        return 0.0
    return points / games_played


def get_ppg_bucket(points: int, games_played: int) -> str:
    ppg = get_ppg(points, games_played)
    if ppg >= 2.0:
        return ">=2"
    if ppg >= 1.5:
        return "1.5-1.99"
    if ppg >= 1.0:
        return "1.0-1.49"
    return "<1.0"


def lookup_historical_prob(
    confederation: str,
    stage: str,
    rank: int,
    points: int,
    games_played: int,
) -> Optional[float]:
    rank_lookup, bucket_lookup = load_historical_probs()
    key = (confederation, stage, rank)
    if key in rank_lookup:
        return rank_lookup[key]
    simplified_key = (confederation, stage.split(" - ")[0], rank)
    if simplified_key in rank_lookup:
        return rank_lookup[simplified_key]

    bucket_key = (
        confederation,
        stage,
        get_rank_bucket(rank),
        get_ppg_bucket(points, games_played),
    )
    if bucket_key in bucket_lookup:
        return bucket_lookup[bucket_key]
    simplified_bucket_key = (
        confederation,
        stage.split(" - ")[0],
        bucket_key[2],
        bucket_key[3],
    )
    return bucket_lookup.get(simplified_bucket_key)


def calculate_team_probability(
    entry: StandingEntry,
    confederation: str,
    stage: str,
) -> float:
    """Lifted from the old QualifierDataFetcher heuristics."""
    prob = 0.0
    position = entry.rank or 100

    if position <= 2:
        prob += 70
    elif position == 3:
        prob += 50
    elif position == 4:
        prob += 30
    elif position == 5:
        prob += 15
    else:
        prob += 5

    if entry.games_played > 0:
        points_per_game = entry.points / entry.games_played
        if points_per_game >= 2:
            prob += 15
        elif points_per_game >= 1.5:
            prob += 10
        elif points_per_game >= 1:
            prob += 5
        elif points_per_game < 0.5:
            prob -= 10

    if entry.goal_difference > 10:
        prob += 10
    elif entry.goal_difference > 5:
        prob += 5
    elif entry.goal_difference < -5:
        prob -= 10

    prob *= CONFED_MULTIPLIERS.get(confederation, 1.0)

    # Blend in historical priors if we have them
    hist_prob = lookup_historical_prob(
        confederation, stage, entry.rank, entry.points, entry.games_played
    )
    if hist_prob is not None:
        hist_score = hist_prob * 100.0
        if hist_score > 0:
            prob = 0.6 * prob + 0.4 * hist_score

    return max(1.0, min(prob, 95.0))


def determine_status(entry: StandingEntry) -> str:
    note = (entry.note or "").lower()
    if "qualifies" in note or "qualified" in note:
        return "Qualified"
    return "In Progress"


def build_team_row(group_confederation: str, group_name: str, entry: StandingEntry) -> Dict[str, object]:
    status = determine_status(entry)
    prob = (
        100.0
        if status == "Qualified"
        else calculate_team_probability(entry, group_confederation, group_name)
    )
    return {
        "team": entry.team_name,
        "confederation": group_confederation,
        "qualification_status": status,
        "prob_fill_slot": round(prob, 1),
        "current_group": group_name,
        "position": entry.rank,
        "points": entry.points,
        "played": entry.games_played,
        "goal_diff": entry.goal_difference,
        "form": "",  # ESPN standings payload does not expose form streaks yet.
    }


def update_team_slot_probabilities() -> pd.DataFrame:
    collector = ConfederationStandingsCollector(build_default_scrapers())
    data, errors = collector.collect()

    if errors:
        for confed, message in errors.items():
            logger.warning("Failed to collect %s standings: %s", confed, message)

    # Start with host teams
    rows: List[Dict[str, object]] = []

    for confed, groups in data.items():
        for group in groups:
            for entry in group.entries:
                rows.append(build_team_row(confed, group.group_name, entry))


    if not rows:
        raise RuntimeError("No standings rows were collected; aborting CSV update.")
    rows = HOST_ROWS + rows

    df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    df.to_csv(OUTPUT_CSV, index=False)
    with OUTPUT_JSON.open("w") as json_file:
        json.dump(rows, json_file, indent=2)

    logger.info("Updated %s with %s teams (hosts included).", OUTPUT_CSV, len(df))
    logger.info("Saved detailed standings snapshot to %s.", OUTPUT_JSON)
    return df


def main() -> None:
    update_team_slot_probabilities()


if __name__ == "__main__":
    main()

