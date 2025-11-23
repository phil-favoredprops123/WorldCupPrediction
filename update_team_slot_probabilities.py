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
from pathlib import Path
from typing import Dict, List

import pandas as pd

from confederation_scraper import (
    ConfederationStandingsCollector,
    StandingEntry,
    build_default_scrapers,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

OUTPUT_CSV = Path("team_slot_probabilities.csv")
OUTPUT_JSON = Path("qualifier_data.json")
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


def calculate_team_probability(entry: StandingEntry, confederation: str) -> float:
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
    return max(1.0, min(prob, 95.0))


def determine_status(entry: StandingEntry) -> str:
    note = (entry.note or "").lower()
    if "qualifies" in note or "qualified" in note:
        return "Qualified"
    return "In Progress"


def build_team_row(group_confederation: str, group_name: str, entry: StandingEntry) -> Dict[str, object]:
    status = determine_status(entry)
    prob = 100.0 if status == "Qualified" else calculate_team_probability(entry, group_confederation)
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

