"""
PostgreSQL writer for storing World Cup qualifier data in RDS.

Writes team slot probabilities and logs scraper jobs to the database.
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import execute_values, Json
from psycopg2.pool import SimpleConnectionPool

logger = logging.getLogger(__name__)


class PostgresWriter:
    """Writes qualifier data to PostgreSQL/RDS database."""

    def __init__(
        self,
        connection_string: Optional[str] = None,
        min_conn: int = 1,
        max_conn: int = 5,
    ):
        """
        Initialize PostgreSQL writer.

        Args:
            connection_string: PostgreSQL connection string. If None, reads from
                DATABASE_URL or constructs from individual env vars:
                - DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
            min_conn: Minimum connections in pool
            max_conn: Maximum connections in pool
        """
        if connection_string is None:
            connection_string = self._build_connection_string()

        self.connection_string = connection_string
        self.pool: Optional[SimpleConnectionPool] = None
        self._init_pool(min_conn, max_conn)

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

    def _init_pool(self, min_conn: int, max_conn: int) -> None:
        """Initialize connection pool."""
        try:
            self.pool = SimpleConnectionPool(
                min_conn, max_conn, self.connection_string
            )
            logger.info("PostgreSQL connection pool initialized")
        except Exception as e:
            logger.error("Failed to initialize PostgreSQL pool: %s", str(e))
            raise

    def get_connection(self):
        """Get a connection from the pool."""
        if self.pool is None:
            raise RuntimeError("Connection pool not initialized")
        return self.pool.getconn()

    def put_connection(self, conn):
        """Return a connection to the pool."""
        if self.pool:
            self.pool.putconn(conn)

    def close(self):
        """Close all connections in the pool."""
        if self.pool:
            self.pool.closeall()
            logger.info("PostgreSQL connection pool closed")

    def write_team_probabilities(
        self, rows: List[Dict[str, Any]]
    ) -> Tuple[int, int]:
        """
        Upsert team slot probabilities into database.

        Args:
            rows: List of team probability dictionaries matching CSV structure

        Returns:
            Tuple of (rows_inserted, rows_updated)
        """
        if not rows:
            logger.warning("No rows to write")
            return 0, 0

        conn = None
        inserted = 0
        updated = 0

        try:
            conn = self.get_connection()
            cur = conn.cursor()

            # Prepare data for upsert
            upsert_query = """
                INSERT INTO team_slot_probabilities (
                    team, confederation, qualification_status, prob_fill_slot,
                    current_group, position, points, played, goal_diff, form
                ) VALUES %s
                ON CONFLICT (team, confederation, current_group)
                DO UPDATE SET
                    qualification_status = EXCLUDED.qualification_status,
                    prob_fill_slot = EXCLUDED.prob_fill_slot,
                    position = EXCLUDED.position,
                    points = EXCLUDED.points,
                    played = EXCLUDED.played,
                    goal_diff = EXCLUDED.goal_diff,
                    form = EXCLUDED.form,
                    updated_at = NOW()
                RETURNING (xmax = 0) AS inserted;
            """

            values = []
            for row in rows:
                values.append((
                    row.get("team"),
                    row.get("confederation"),
                    row.get("qualification_status"),
                    row.get("prob_fill_slot"),
                    row.get("current_group"),
                    row.get("position") if row.get("position") else None,
                    row.get("points") if row.get("points") else None,
                    row.get("played") if row.get("played") else None,
                    row.get("goal_diff") if row.get("goal_diff") else None,
                    row.get("form") or "",
                ))

            results = execute_values(cur, upsert_query, values, fetch=True)
            
            # Count inserts vs updates
            for result in results:
                if result[0]:  # inserted = True
                    inserted += 1
                else:
                    updated += 1

            conn.commit()
            logger.info(
                "Wrote %s team probabilities: %s inserted, %s updated",
                len(rows),
                inserted,
                updated,
            )

            return inserted, updated

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error("Failed to write team probabilities: %s", str(e), exc_info=True)
            raise
        finally:
            if conn:
                self.put_connection(conn)

    def log_scraper_job(
        self,
        job_type: str,
        status: str,
        rows_processed: int,
        rows_inserted: int,
        rows_updated: int,
        rows_failed: int = 0,
        confederation_counts: Optional[Dict[str, int]] = None,
        confederations_scraped: Optional[List[str]] = None,
        source_urls: Optional[List[str]] = None,
        output_files: Optional[List[str]] = None,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
        execution_time_seconds: Optional[float] = None,
        started_at: Optional[datetime] = None,
        lambda_request_id: Optional[str] = None,
        environment: Optional[str] = None,
        notes: Optional[str] = None,
        input_params: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Log a scraper job to the database.

        Returns:
            The ID of the created scraper_job record
        """
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()

            # Calculate input hash if params provided
            input_hash = None
            if input_params:
                input_str = json.dumps(input_params, sort_keys=True)
                input_hash = hashlib.sha256(input_str.encode()).hexdigest()

            # Calculate output hash if files provided
            output_hash = None
            if output_files:
                # Simple hash of file list (in production, hash actual file contents)
                output_str = json.dumps(sorted(output_files), sort_keys=True)
                output_hash = hashlib.sha256(output_str.encode()).hexdigest()[:64]

            completed_at = datetime.utcnow() if status != "running" else None

            insert_query = """
                INSERT INTO scraper_jobs (
                    job_type, status, rows_processed, rows_inserted, rows_updated,
                    rows_failed, confederation_counts, confederations_scraped,
                    source_urls, output_files, output_hash, error_message,
                    error_details, warnings, execution_time_seconds,
                    started_at, completed_at, lambda_request_id, environment,
                    notes, input_hash, input_params, execution_context
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id;
            """

            cur.execute(
                insert_query,
                (
                    job_type,
                    status,
                    rows_processed,
                    rows_inserted,
                    rows_updated,
                    rows_failed,
                    Json(confederation_counts) if confederation_counts else None,
                    confederations_scraped,
                    source_urls,
                    Json(output_files) if output_files else None,
                    output_hash,
                    error_message,
                    Json(error_details) if error_details else None,
                    Json(warnings) if warnings else None,
                    execution_time_seconds,
                    started_at,
                    completed_at,
                    lambda_request_id,
                    environment or os.getenv("ENVIRONMENT", "production"),
                    notes,
                    input_hash,
                    Json(input_params) if input_params else None,
                    "lambda" if lambda_request_id else "local",
                ),
            )

            job_id = cur.fetchone()[0]
            conn.commit()

            logger.info("Logged scraper job #%s: %s (%s)", job_id, job_type, status)
            return job_id

        except Exception as e:
            if conn:
                conn.rollback()
            logger.error("Failed to log scraper job: %s", str(e), exc_info=True)
            raise
        finally:
            if conn:
                self.put_connection(conn)


def write_team_probabilities_to_db(
    rows: List[Dict[str, Any]],
    connection_string: Optional[str] = None,
) -> Tuple[int, int]:
    """
    Convenience function to write team probabilities.

    Args:
        rows: List of team probability dictionaries
        connection_string: Optional PostgreSQL connection string

    Returns:
        Tuple of (rows_inserted, rows_updated)
    """
    writer = PostgresWriter(connection_string=connection_string)
    try:
        return writer.write_team_probabilities(rows)
    finally:
        writer.close()