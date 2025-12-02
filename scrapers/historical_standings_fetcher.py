#!/usr/bin/env python3
"""
Fetch historical World Cup qualifying standings from the ESPN public API and
generate a lookup table we can use to inform probability estimates.

By default we pull the previous two World Cup cycles (2022 and 2018), but
you can adjust the HISTORICAL_SEASONS list below or pass seasons via CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

# Add parent directory to path so script can be run from scrapers/ or project root
_SCRIPT_DIR = Path(__file__).parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd
import requests

from scrapers.confederation_scraper import (
    ConfederationStandingsCollector,
    EspnStandingsScraper,
    GroupStanding,
    StandingEntry,
    ESPN_LEAGUE_CODES,
)

logger = logging.getLogger("historical_standings_fetcher")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DEFAULT_START_SEASON = 1990
DEFAULT_END_SEASON = 2025
OUTPUT_JSON = Path("historical_standings.json")
OUTPUT_CSV = Path(os.getenv("HISTORICAL_STANDINGS_PATH", "historical_standings.csv"))


def rank_bucket(rank: Optional[int]) -> str:
    if rank is None:
        return "unknown"
    if rank == 1:
        return "1"
    if rank == 2:
        return "2"
    if rank in (3, 4):
        return "3-4"
    if rank == 5:
        return "5"
    return "6+"


def points_per_game(points: int, games_played: int) -> float:
    if games_played <= 0:
        return 0.0
    return points / games_played


def ppg_bucket(points: int, games_played: int) -> str:
    ppg = points_per_game(points, games_played)
    if ppg >= 2.0:
        return ">=2"
    if ppg >= 1.5:
        return "1.5-1.99"
    if ppg >= 1.0:
        return "1.0-1.49"
    return "<1.0"


def goal_diff_bucket(goal_diff: int) -> str:
    if goal_diff >= 10:
        return ">=10"
    if goal_diff >= 5:
        return "5-9"
    if goal_diff >= 0:
        return "0-4"
    if goal_diff >= -4:
        return "-4- -0"
    if goal_diff >= -9:
        return "-9- -5"
    return "<-9"


def normalize_entry(
    season: int,
    confed: str,
    group: GroupStanding,
    entry: StandingEntry,
) -> Dict[str, object]:
    note_text = (entry.note or "").lower()
    qualified = "qualifies" in note_text or "qualified" in note_text
    row = {
        "season": season,
        "confederation": confed,
        "stage": group.stage,
        "group_name": group.group_name,
        "team": entry.team_name,
        "rank": entry.rank,
        "points": entry.points,
        "games_played": entry.games_played,
        "wins": entry.wins,
        "draws": entry.draws,
        "losses": entry.losses,
        "goals_for": entry.goals_for,
        "goals_against": entry.goals_against,
        "goal_difference": entry.goal_difference,
        "qualified": qualified,
        "note": entry.note or "",
        "source_url": group.source_url,
    }
    row["rank_bucket"] = rank_bucket(entry.rank)
    row["points_per_game"] = points_per_game(entry.points, entry.games_played)
    row["ppg_bucket"] = ppg_bucket(entry.points, entry.games_played)
    row["goal_diff_bucket"] = goal_diff_bucket(entry.goal_difference)
    return row


def ensure_augmented_features(row: Dict[str, object]) -> Dict[str, object]:
    if "rank_bucket" not in row:
        row["rank_bucket"] = rank_bucket(row.get("rank"))
    if "points_per_game" not in row:
        points = int(row.get("points", 0))
        games = int(row.get("games_played", 0))
        row["points_per_game"] = points_per_game(points, games)
    if "ppg_bucket" not in row:
        points = int(row.get("points", 0))
        games = int(row.get("games_played", 0))
        row["ppg_bucket"] = ppg_bucket(points, games)
    if "goal_diff_bucket" not in row:
        row["goal_diff_bucket"] = goal_diff_bucket(int(row.get("goal_difference", 0)))
    return row


def fetch_for_season(
    season: int,
    session: Optional[requests.Session] = None,
) -> List[Dict[str, object]]:
    logger.info("Fetching standings for season %s", season)
    scrapers: List[EspnStandingsScraper] = [
        EspnStandingsScraper(confed, league_code, season=season, session=session)
        for confed, league_code in ESPN_LEAGUE_CODES.items()
    ]
    collector = ConfederationStandingsCollector(scrapers)
    data, errors = collector.collect()
    for confed, message in errors.items():
        logger.warning("  %s: %s", confed, message)

    rows: List[Dict[str, object]] = []
    for confed, groups in data.items():
        for group in groups:
            for entry in group.entries:
                rows.append(normalize_entry(season, confed, group, entry))
    logger.info("  Season %s -> %s rows", season, len(rows))
    return rows


def compute_probability_lookup(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    rank_lookup = (
        df.groupby(["confederation", "stage", "rank"], dropna=False)["qualified"]
        .mean()
        .reset_index()
    )
    rank_lookup["rank_bucket"] = rank_lookup["rank"].apply(rank_bucket)
    rank_lookup["ppg_bucket"] = "all"
    rank_lookup["lookup_level"] = "rank"

    bucket_lookup = (
        df.groupby(["confederation", "stage", "rank_bucket", "ppg_bucket"], dropna=False)[
            "qualified"
        ]
        .mean()
        .reset_index()
    )
    bucket_lookup["rank"] = None
    bucket_lookup["lookup_level"] = "bucket"

    lookup_df = pd.concat([rank_lookup, bucket_lookup], ignore_index=True)
    lookup_df.rename(columns={"qualified": "historical_qual_prob"}, inplace=True)
    return lookup_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch historical qualifier standings.")
    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        help="Explicit list of seasons to fetch (e.g., 2022 2018).",
    )
    parser.add_argument(
        "--start-season",
        type=int,
        default=DEFAULT_START_SEASON,
        help=f"Start of season range (default {DEFAULT_START_SEASON}).",
    )
    parser.add_argument(
        "--end-season",
        type=int,
        default=DEFAULT_END_SEASON,
        help=f"End of season range inclusive (default {DEFAULT_END_SEASON}).",
    )
    parser.add_argument(
        "--output-json",
        default=str(OUTPUT_JSON),
        help="Path for the raw standings JSON list.",
    )
    parser.add_argument(
        "--output-csv",
        default=str(OUTPUT_CSV),
        help="Path for the flattened CSV lookup table.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.seasons:
        seasons_to_fetch = sorted(set(args.seasons))
    else:
        start = min(args.start_season, args.end_season)
        end = max(args.start_season, args.end_season)
        seasons_to_fetch = list(range(start, end + 1))

    rows: List[Dict[str, object]] = []
    for season in seasons_to_fetch:
        rows.extend(fetch_for_season(season))

    output_json = Path(args.output_json)
    output_csv = Path(args.output_csv)

    if not rows:
        if output_json.exists():
            logger.warning(
                "No new data fetched; reusing existing historical dataset at %s",
                output_json,
            )
            rows = json.loads(output_json.read_text(encoding="utf-8"))
        else:
            logger.error("No historical data fetched. Exiting.")
            return

    rows = [ensure_augmented_features(dict(row)) for row in rows]

    output_json.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    logger.info("Wrote %s rows to %s", len(rows), output_json)

    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False)
    logger.info("Wrote CSV lookup to %s", output_csv)

    lookup = compute_probability_lookup(df)
    if not lookup.empty:
        lookup_path = output_csv.with_name("historical_probability_lookup.csv")
        lookup.to_csv(lookup_path, index=False)
        logger.info("Wrote probability lookup to %s", lookup_path)


if __name__ == "__main__":
    main()

