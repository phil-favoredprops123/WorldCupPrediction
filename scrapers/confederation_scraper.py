#!/usr/bin/env python3
"""
Confederation standings scrapers.

This module standardizes how we collect FIFA World Cup qualifying standings
across every confederation while staying within tight API limits. It currently
relies on ESPN's public JSON endpoints (one lightweight GET per confed) and
exposes orchestration utilities so that downstream jobs can refresh all
standings, feed them into the probability model, and eventually persist them
to PostgreSQL without rewriting scraper logic for each zone.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import certifi
import requests
import urllib3

try:  # Optional dependency for future persistence.
    import psycopg2  # type: ignore
except ImportError:  # pragma: no cover - psycopg2 is optional for now.
    psycopg2 = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class StandingEntry:
    """Normalized standing for a single team."""

    rank: int
    team_id: str
    team_code: str
    team_name: str
    games_played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    record_summary: Optional[str] = None
    note: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GroupStanding:
    """Container for a whole confederation group/league table."""

    confederation: str
    group_name: str
    stage: str
    entries: List[StandingEntry]
    source_url: str
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    checksum: str = ""

    def as_records(self) -> List[Dict[str, Any]]:
        """Flatten entries for persistence."""
        records: List[Dict[str, Any]] = []
        for entry in self.entries:
            records.append(
                {
                    "confederation": self.confederation,
                    "stage": self.stage,
                    "group_name": self.group_name,
                    "team_id": entry.team_id,
                    "team_code": entry.team_code,
                    "team_name": entry.team_name,
                    "rank": entry.rank,
                    "games_played": entry.games_played,
                    "wins": entry.wins,
                    "draws": entry.draws,
                    "losses": entry.losses,
                    "goals_for": entry.goals_for,
                    "goals_against": entry.goals_against,
                    "goal_difference": entry.goal_difference,
                    "points": entry.points,
                    "record_summary": entry.record_summary,
                    "note": entry.note,
                    "source_url": self.source_url,
                    "fetched_at": self.fetched_at.isoformat(),
                    "checksum": self.checksum,
                }
            )
        return records


# ---------------------------------------------------------------------------
# Base scraper
# ---------------------------------------------------------------------------


class ConfederationScraper:
    """Abstract scraper for a confederation standings source."""

    def __init__(
        self,
        confederation: str,
        source_url: str,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.confederation = confederation
        self.source_url = source_url
        self.session = session or requests.Session()
        if session is None:
            verify_env = os.environ.get("CONFED_SCRAPER_VERIFY_SSL", "0").lower()
            if verify_env in {"1", "true", "yes"}:
                self.session.verify = certifi.where()
            else:
                self.session.verify = False
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Public API -------------------------------------------------------------
    def run(self) -> List[GroupStanding]:
        raw = self.fetch_raw()
        groups = self.parse(raw)
        checksum = hashlib.sha1(json.dumps(raw, sort_keys=True).encode("utf-8")).hexdigest()
        for group in groups:
            group.checksum = checksum
        logger.info(
            "Fetched %s groups for %s from %s",
            len(groups),
            self.confederation,
            self.source_url,
        )
        return groups

    # Hooks for subclasses ---------------------------------------------------
    def fetch_raw(self) -> Dict[str, Any]:  # pragma: no cover - abstract
        raise NotImplementedError

    def parse(self, payload: Dict[str, Any]) -> List[GroupStanding]:  # pragma: no cover - abstract
        raise NotImplementedError


# ---------------------------------------------------------------------------
# ESPN implementation
# ---------------------------------------------------------------------------


class EspnStandingsScraper(ConfederationScraper):
    """Pull standings from ESPN's lightweight JSON endpoint."""

    API_TEMPLATE = "https://site.web.api.espn.com/apis/v2/sports/soccer/{league}/standings"
    DEFAULT_PARAMS = {
        "region": "us",
        "lang": "en",
        "contentorigin": "espn",
        "level": 2,
    }

    def __init__(
        self,
        confederation: str,
        league_code: str,
        *,
        season: Optional[int] = None,
        season_type: Optional[int] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        url = self.API_TEMPLATE.format(league=league_code)
        super().__init__(confederation, url, session)
        params = dict(self.DEFAULT_PARAMS)
        if season:
            params["season"] = season
        if season_type:
            params["seasontype"] = season_type
        self.params = params

    def fetch_raw(self) -> Dict[str, Any]:
        resp = self.session.get(self.source_url, params=self.params, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def parse(self, payload: Dict[str, Any]) -> List[GroupStanding]:
        stages = self._extract_groups(payload)
        stage_name = self._infer_stage(payload)
        groups: List[GroupStanding] = []

        for group_payload in stages:
            standings = group_payload.get("standings", {})
            entries_payload = standings.get("entries", [])
            entries: List[StandingEntry] = [self._parse_entry(entry) for entry in entries_payload]
            group_name = group_payload.get("name") or group_payload.get("abbreviation") or "Group"

            groups.append(
                GroupStanding(
                    confederation=self.confederation,
                    group_name=group_name,
                    stage=stage_name,
                    entries=entries,
                    source_url=self.source_url,
                )
            )

        return groups

    # Helpers ----------------------------------------------------------------
    def _extract_groups(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        children = payload.get("children", [])
        if children:
            return children
        # Some leagues (e.g. CONMEBOL) come back as a single table.
        standings = payload.get("standings")
        if standings:
            return [{"name": payload.get("name", "League"), "standings": standings}]
        raise ValueError(f"No standings found in payload for {self.source_url}")

    @staticmethod
    def _infer_stage(payload: Dict[str, Any]) -> str:
        seasons = payload.get("seasons", [])
        if not seasons:
            return "unknown"
        season = seasons[0]
        types = season.get("types", [])
        for type_info in types:
            if type_info.get("hasStandings"):
                return type_info.get("name") or type_info.get("displayName") or "stage"
        return season.get("displayName") or "stage"

    @staticmethod
    def _parse_entry(entry: Dict[str, Any]) -> StandingEntry:
        stats_map = {stat.get("name"): stat for stat in entry.get("stats", [])}

        def stat_value(name: str, default: int = 0) -> int:
            stat = stats_map.get(name)
            if not stat:
                return default
            value = stat.get("value")
            if value is None:
                display = stat.get("displayValue")
                if display in (None, ""):
                    return default
                try:
                    value = float(display)
                except ValueError:
                    return default
            return int(value)

        team = entry.get("team", {})
        summary_stat = stats_map.get("overall")
        record_summary = summary_stat.get("summary") if summary_stat else None

        return StandingEntry(
            rank=stat_value("rank", default=0),
            team_id=team.get("id", ""),
            team_code=team.get("abbreviation", ""),
            team_name=team.get("displayName", team.get("name", "")),
            games_played=stat_value("gamesPlayed"),
            wins=stat_value("wins"),
            draws=stat_value("ties"),
            losses=stat_value("losses"),
            goals_for=stat_value("pointsFor"),
            goals_against=stat_value("pointsAgainst"),
            goal_difference=stat_value("pointDifferential"),
            points=stat_value("points"),
            record_summary=record_summary,
            note=(entry.get("note") or {}).get("description"),
            raw=entry,
        )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

ESPN_LEAGUE_CODES = {
    "AFC": "fifa.worldq.afc",
    "CAF": "fifa.worldq.caf",
    "CONCACAF": "fifa.worldq.concacaf",
    "CONMEBOL": "fifa.worldq.conmebol",
    "UEFA": "fifa.worldq.uefa",
    "OFC": "fifa.worldq.ofc",
}

# By default we let ESPN serve the latest stage without forcing season overrides.
ESPN_SEASON_OVERRIDES: Dict[str, Dict[str, Optional[int]]] = {}


def build_default_scrapers(
    *,
    session: Optional[requests.Session] = None,
    season: Optional[int] = None,
) -> List[ConfederationScraper]:
    """Instantiate one scraper per confederation."""
    scrapers: List[ConfederationScraper] = []
    for confed, league_code in ESPN_LEAGUE_CODES.items():
        override = ESPN_SEASON_OVERRIDES.get(confed)
        season_value = override.get("season") if override else season
        season_type_value = override.get("season_type") if override else None
        scrapers.append(
            EspnStandingsScraper(
                confederation=confed,
                league_code=league_code,
                season=season_value,
                season_type=season_type_value,
                # Leave None so ESPN picks latest per confed unless overridden.
                session=session,
            )
        )
    return scrapers


class ConfederationStandingsCollector:
    """Run multiple scrapers sequentially and collate results."""

    def __init__(self, scrapers: Iterable[ConfederationScraper]):
        self.scrapers = list(scrapers)

    def collect(self) -> Tuple[Dict[str, List[GroupStanding]], Dict[str, str]]:
        data: Dict[str, List[GroupStanding]] = {}
        errors: Dict[str, str] = {}
        for scraper in self.scrapers:
            try:
                data[scraper.confederation] = scraper.run()
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Failed to scrape %s", scraper.confederation)
                errors[scraper.confederation] = str(exc)
        return data, errors

    def flatten(self) -> List[Dict[str, Any]]:
        payload: List[Dict[str, Any]] = []
        data, _ = self.collect()
        for groups in data.values():
            for group in groups:
                payload.extend(group.as_records())
        return payload


# ---------------------------------------------------------------------------
# PostgreSQL writer (optional)
# ---------------------------------------------------------------------------


class PostgresStandingsWriter:
    """
    Minimal helper that upserts normalized standings rows into PostgreSQL.

    Expected schema (feel free to adapt):

        CREATE TABLE IF NOT EXISTS confed_standings (
            confederation TEXT NOT NULL,
            stage TEXT NOT NULL,
            group_name TEXT NOT NULL,
            team_id TEXT NOT NULL,
            team_code TEXT,
            team_name TEXT,
            rank INT,
            games_played INT,
            wins INT,
            draws INT,
            losses INT,
            goals_for INT,
            goals_against INT,
            goal_difference INT,
            points INT,
            record_summary TEXT,
            note TEXT,
            source_url TEXT,
            fetched_at TIMESTAMPTZ,
            checksum TEXT,
            PRIMARY KEY (confederation, stage, group_name, team_id)
        );
    """

    UPSERT_SQL = """
        INSERT INTO confed_standings (
            confederation, stage, group_name, team_id, team_code, team_name,
            rank, games_played, wins, draws, losses, goals_for, goals_against,
            goal_difference, points, record_summary, note, source_url,
            fetched_at, checksum
        ) VALUES (
            %(confederation)s, %(stage)s, %(group_name)s, %(team_id)s,
            %(team_code)s, %(team_name)s, %(rank)s, %(games_played)s,
            %(wins)s, %(draws)s, %(losses)s, %(goals_for)s, %(goals_against)s,
            %(goal_difference)s, %(points)s, %(record_summary)s, %(note)s,
            %(source_url)s, %(fetched_at)s, %(checksum)s
        )
        ON CONFLICT (confederation, stage, group_name, team_id)
        DO UPDATE SET
            rank = EXCLUDED.rank,
            games_played = EXCLUDED.games_played,
            wins = EXCLUDED.wins,
            draws = EXCLUDED.draws,
            losses = EXCLUDED.losses,
            goals_for = EXCLUDED.goals_for,
            goals_against = EXCLUDED.goals_against,
            goal_difference = EXCLUDED.goal_difference,
            points = EXCLUDED.points,
            record_summary = EXCLUDED.record_summary,
            note = EXCLUDED.note,
            source_url = EXCLUDED.source_url,
            fetched_at = EXCLUDED.fetched_at,
            checksum = EXCLUDED.checksum;
    """.strip()

    def __init__(self, **connect_kwargs: Any) -> None:
        if psycopg2 is None:  # pragma: no cover - optional dependency
            raise ImportError(
                "psycopg2 is required for PostgresStandingsWriter. "
                "Install it or provide a custom sink."
            )
        self.connect_kwargs = connect_kwargs

    def write(self, groups: Iterable[GroupStanding]) -> None:
        rows = []
        for group in groups:
            rows.extend(group.as_records())
        if not rows:
            logger.info("No standings rows to persist.")
            return

        with psycopg2.connect(**self.connect_kwargs) as conn:  # pragma: no cover - I/O
            with conn.cursor() as cur:
                cur.executemany(self.UPSERT_SQL, rows)
            conn.commit()
        logger.info("Persisted %s standings rows.", len(rows))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:  # pragma: no cover - helper for manual runs
    logging.basicConfig(level=logging.INFO)
    collector = ConfederationStandingsCollector(build_default_scrapers())
    data, errors = collector.collect()

    for confed, groups in data.items():
        print(f"{confed}: {len(groups)} groups")
        for group in groups:
            top = group.entries[0] if group.entries else None
            if top:
                print(f"  {group.group_name}: {top.team_name} leads ({top.points} pts)")

    if errors:
        print("\nErrors:")
        for confed, message in errors.items():
            print(f"- {confed}: {message}")


if __name__ == "__main__":  # pragma: no cover - manual execution only
    main()

