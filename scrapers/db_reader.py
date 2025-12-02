"""
Database reader for querying World Cup qualifier data from PostgreSQL.

Provides helper functions for Streamlit and other applications to read
team probabilities and scraper job logs from the database.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class PostgresReader:
    """Reads qualifier data from PostgreSQL/RDS database."""

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize PostgreSQL reader.

        Args:
            connection_string: PostgreSQL connection string. If None, reads from
                DATABASE_URL or constructs from individual env vars:
                - DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
        """
        if connection_string is None:
            connection_string = self._build_connection_string()

        self.connection_string = connection_string

    def _build_connection_string(self) -> str:
        """Build connection string from environment variables."""
        # Try DATABASE_URL first (common in Lambda/RDS)
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return db_url

        # Otherwise construct from individual vars
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        dbname = os.getenv("DB_NAME", "worldcup")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "")

        return f"host={host} port={port} dbname={dbname} user={user} password={password}"

    def get_connection(self):
        """Get a database connection."""
        return psycopg2.connect(self.connection_string)

    def get_team_probabilities(
        self,
        confederation: Optional[str] = None,
        qualification_status: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Get team slot probabilities from database.

        Args:
            confederation: Filter by confederation (e.g., 'UEFA', 'CAF')
            qualification_status: Filter by status (e.g., 'Qualified', 'In Progress')
            limit: Maximum number of rows to return

        Returns:
            DataFrame with team probabilities
        """
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = "SELECT * FROM team_slot_probabilities WHERE 1=1"
            params = []

            if confederation:
                query += " AND confederation = %s"
                params.append(confederation)

            if qualification_status:
                query += " AND qualification_status = %s"
                params.append(qualification_status)

            query += " ORDER BY prob_fill_slot DESC, team"

            if limit:
                query += " LIMIT %s"
                params.append(limit)

            cur.execute(query, params)
            rows = cur.fetchall()

            if rows:
                df = pd.DataFrame([dict(row) for row in rows])
                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            logger.error("Failed to get team probabilities: %s", str(e), exc_info=True)
            raise
        finally:
            if conn:
                conn.close()

    def get_team_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics about teams.

        Returns:
            Dictionary with stats: total, qualified, in_progress, by_confederation
        """
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            # Total teams
            cur.execute("SELECT COUNT(*) FROM team_slot_probabilities")
            total = cur.fetchone()[0]

            # Qualified teams
            cur.execute(
                "SELECT COUNT(*) FROM team_slot_probabilities WHERE qualification_status = 'Qualified'"
            )
            qualified = cur.fetchone()[0]

            # In progress teams
            cur.execute(
                "SELECT COUNT(*) FROM team_slot_probabilities WHERE qualification_status = 'In Progress'"
            )
            in_progress = cur.fetchone()[0]

            # By confederation
            cur.execute(
                """
                SELECT confederation, COUNT(*) as count
                FROM team_slot_probabilities
                GROUP BY confederation
                ORDER BY confederation
                """
            )
            by_confederation = {row[0]: row[1] for row in cur.fetchall()}

            return {
                "total": total,
                "qualified": qualified,
                "in_progress": in_progress,
                "by_confederation": by_confederation,
            }

        except Exception as e:
            logger.error("Failed to get team stats: %s", str(e), exc_info=True)
            raise
        finally:
            if conn:
                conn.close()

    def get_recent_scraper_jobs(self, limit: int = 10) -> pd.DataFrame:
        """
        Get recent scraper job logs.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            DataFrame with scraper job information
        """
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT 
                    id, job_type, status, rows_processed, rows_inserted, rows_updated,
                    execution_time_seconds, started_at, completed_at, error_message
                FROM scraper_jobs
                ORDER BY started_at DESC
                LIMIT %s
            """

            cur.execute(query, (limit,))
            rows = cur.fetchall()

            if rows:
                df = pd.DataFrame([dict(row) for row in rows])
                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            logger.error("Failed to get scraper jobs: %s", str(e), exc_info=True)
            raise
        finally:
            if conn:
                conn.close()

    def get_latest_update_time(self) -> Optional[str]:
        """
        Get the timestamp of the most recent team probability update.

        Returns:
            ISO format timestamp string, or None if no updates found
        """
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            cur.execute(
                """
                SELECT MAX(updated_at) as latest_update
                FROM team_slot_probabilities
                """
            )
            result = cur.fetchone()
            if result and result[0]:
                return result[0].isoformat()
            return None

        except Exception as e:
            logger.error("Failed to get latest update time: %s", str(e), exc_info=True)
            return None
        finally:
            if conn:
                conn.close()


def get_team_probabilities(
    confederation: Optional[str] = None,
    qualification_status: Optional[str] = None,
    connection_string: Optional[str] = None,
) -> pd.DataFrame:
    """
    Convenience function to get team probabilities.

    Args:
        confederation: Filter by confederation
        qualification_status: Filter by status
        connection_string: Optional PostgreSQL connection string

    Returns:
        DataFrame with team probabilities
    """
    reader = PostgresReader(connection_string=connection_string)
    return reader.get_team_probabilities(
        confederation=confederation, qualification_status=qualification_status
    )


def get_team_stats(connection_string: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to get team statistics.

    Args:
        connection_string: Optional PostgreSQL connection string

    Returns:
        Dictionary with team statistics
    """
    reader = PostgresReader(connection_string=connection_string)
    return reader.get_team_stats()

