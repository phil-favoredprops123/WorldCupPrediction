"""
AWS Lambda handlers for World Cup qualifier scrapers.

These handlers are designed to be invoked by EventBridge on a schedule.
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler_current_standings(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for updating current team slot probabilities.
    
    Invoked by EventBridge every 6 hours to refresh current standings.
    Writes results to both CSV (for backup) and PostgreSQL database.
    
    Args:
        event: EventBridge event (can be empty dict)
        context: Lambda context object
        
    Returns:
        Dict with statusCode and body
    """
    started_at = datetime.utcnow()
    lambda_request_id = getattr(context, 'aws_request_id', None) if context else None
    job_id = None
    rows_inserted = 0
    rows_updated = 0
    
    try:
        from scrapers.update_team_slot_probabilities import update_team_slot_probabilities
        from scrapers.postgres_writer import PostgresWriter
        
        logger.info("Starting current standings update")
        
        # Set Lambda-friendly paths if not already set
        if not os.getenv("OUTPUT_CSV_PATH"):
            os.environ["OUTPUT_CSV_PATH"] = "/tmp/team_slot_probabilities.csv"
        if not os.getenv("OUTPUT_JSON_PATH"):
            os.environ["OUTPUT_JSON_PATH"] = "/tmp/qualifier_data.json"
        if not os.getenv("HISTORICAL_LOOKUP_PATH"):
            # Look for bundled CSV first, then try S3, then fallback to /tmp
            bundled_path = "/var/task/scrapers/historical_probability_lookup.csv"
            tmp_path = "/tmp/historical_probability_lookup.csv"
            
            if os.path.exists(bundled_path):
                os.environ["HISTORICAL_LOOKUP_PATH"] = bundled_path
                logger.info("✅ Found bundled historical lookup CSV at %s", bundled_path)
            else:
                # Try downloading from S3 if bucket is configured
                s3_bucket = os.getenv("HISTORICAL_LOOKUP_S3_BUCKET")
                s3_key = os.getenv("HISTORICAL_LOOKUP_S3_KEY", "historical_probability_lookup.csv")
                
                if s3_bucket and not os.path.exists(tmp_path):
                    try:
                        import boto3
                        s3 = boto3.client("s3")
                        logger.info("Downloading historical lookup from s3://%s/%s", s3_bucket, s3_key)
                        s3.download_file(s3_bucket, s3_key, tmp_path)
                        logger.info("✅ Downloaded historical lookup CSV to %s", tmp_path)
                    except Exception as e:
                        logger.warning("Failed to download from S3: %s", str(e))
                
                os.environ["HISTORICAL_LOOKUP_PATH"] = tmp_path
                if not os.path.exists(bundled_path):
                    logger.warning("⚠️ Bundled CSV not found at %s, using %s", bundled_path, tmp_path)
        
        # Update standings (writes to CSV/JSON)
        df = update_team_slot_probabilities()
        
        # Write to database if connection is available
        db_writer = None
        try:
            db_writer = PostgresWriter()
            logger.info("Writing team probabilities to database...")
            
            # Convert DataFrame to list of dicts for database write
            rows = df.to_dict('records')
            rows_inserted, rows_updated = db_writer.write_team_probabilities(rows)
            logger.info("✅ Database write complete: %s inserted, %s updated", rows_inserted, rows_updated)
            
            # Log job to database
            execution_time = (datetime.utcnow() - started_at).total_seconds()
            job_id = db_writer.log_scraper_job(
                job_type="current_standings",
                status="success",
                rows_processed=len(df),
                rows_inserted=rows_inserted,
                rows_updated=rows_updated,
                rows_failed=0,
                output_files=[os.getenv("OUTPUT_CSV_PATH"), os.getenv("OUTPUT_JSON_PATH")],
                execution_time_seconds=execution_time,
                started_at=started_at,
                lambda_request_id=lambda_request_id,
                environment=os.getenv("ENVIRONMENT", "production"),
                notes=f"Updated {len(df)} teams via Lambda",
            )
            logger.info("✅ Logged scraper job #%s", job_id)
            
        except Exception as db_error:
            logger.warning("Database write failed (continuing with CSV only): %s", str(db_error))
            # Log failed job if we can connect
            if db_writer:
                try:
                    execution_time = (datetime.utcnow() - started_at).total_seconds()
                    db_writer.log_scraper_job(
                        job_type="current_standings",
                        status="partial",
                        rows_processed=len(df),
                        rows_inserted=0,
                        rows_updated=0,
                        rows_failed=0,
                        output_files=[os.getenv("OUTPUT_CSV_PATH"), os.getenv("OUTPUT_JSON_PATH")],
                        execution_time_seconds=execution_time,
                        started_at=started_at,
                        lambda_request_id=lambda_request_id,
                        environment=os.getenv("ENVIRONMENT", "production"),
                        error_message=f"Database write failed: {str(db_error)}",
                        notes="CSV updated successfully, database write failed",
                    )
                except:
                    pass
        finally:
            if db_writer:
                db_writer.close()
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Current standings updated successfully",
                "teams_count": len(df),
                "rows_inserted": rows_inserted,
                "rows_updated": rows_updated,
                "job_id": job_id,
                "output_csv": os.getenv("OUTPUT_CSV_PATH"),
                "output_json": os.getenv("OUTPUT_JSON_PATH"),
                "lambda_request_id": lambda_request_id,
            }),
        }
    except Exception as e:
        logger.error(f"Error updating current standings: {str(e)}", exc_info=True)
        
        # Try to log failed job
        try:
            from scrapers.postgres_writer import PostgresWriter
            db_writer = PostgresWriter()
            execution_time = (datetime.utcnow() - started_at).total_seconds()
            db_writer.log_scraper_job(
                job_type="current_standings",
                status="failed",
                rows_processed=0,
                rows_inserted=0,
                rows_updated=0,
                rows_failed=0,
                execution_time_seconds=execution_time,
                started_at=started_at,
                lambda_request_id=lambda_request_id,
                environment=os.getenv("ENVIRONMENT", "production"),
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
            )
            db_writer.close()
        except:
            pass
        
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Failed to update current standings",
                "message": str(e),
            }),
        }


def handler_historical_fetch(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for fetching historical standings.
    
    Invoked by EventBridge weekly to backfill historical data.
    Can also be invoked manually with custom season ranges.
    
    Event payload (optional):
        {
            "start_season": 1990,
            "end_season": 2025
        }
    
    Args:
        event: EventBridge event (may contain start_season/end_season)
        context: Lambda context object
        
    Returns:
        Dict with statusCode and body
    """
    try:
        from scrapers.historical_standings_fetcher import fetch_historical_standings
        
        # Extract season range from event or use defaults
        start_season = event.get("start_season", 1990)
        end_season = event.get("end_season", 2025)
        
        # Set Lambda-friendly paths if not already set
        if not os.getenv("HISTORICAL_STANDINGS_PATH"):
            os.environ["HISTORICAL_STANDINGS_PATH"] = "/tmp/historical_standings.csv"
        
        logger.info(f"Starting historical fetch for seasons {start_season}-{end_season}")
        
        seasons = list(range(start_season, end_season + 1))
        rows = fetch_historical_standings(seasons)
        
        # Get Lambda request ID if available
        lambda_request_id = getattr(context, 'aws_request_id', None) if context else None
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Historical standings fetched successfully",
                "seasons_processed": f"{start_season}-{end_season}",
                "rows_collected": len(rows),
                "output_file": os.getenv("HISTORICAL_STANDINGS_PATH"),
                "lambda_request_id": lambda_request_id,
            }),
        }
    except Exception as e:
        logger.error(f"Error fetching historical standings: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Failed to fetch historical standings",
                "message": str(e),
            }),
        }


def handler_update_probabilities(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for regenerating historical probability lookup table.
    
    Invoked by EventBridge after historical data is updated to rebuild
    the probability lookup table.
    
    Args:
        event: EventBridge event (can be empty dict)
        context: Lambda context object
        
    Returns:
        Dict with statusCode and body
    """
    try:
        from scrapers.historical_standings_fetcher import compute_probability_lookup
        import pandas as pd
        from pathlib import Path
        
        # Set Lambda-friendly paths if not already set
        historical_csv = Path(os.getenv("HISTORICAL_STANDINGS_PATH", "/tmp/historical_standings.csv"))
        lookup_path = Path(os.getenv("HISTORICAL_LOOKUP_PATH", "/tmp/historical_probability_lookup.csv"))
        
        logger.info("Starting probability lookup generation")
        
        # Load historical standings
        if not historical_csv.exists():
            return {
                "statusCode": 404,
                "body": json.dumps({
                    "error": "Historical standings file not found",
                    "expected_path": str(historical_csv),
                }),
            }
        
        df = pd.read_csv(historical_csv)
        lookup_df = compute_probability_lookup(df)
        
        if not lookup_df.empty:
            lookup_df.to_csv(lookup_path, index=False)
            logger.info("Wrote probability lookup to %s", lookup_path)
        
        # Get Lambda request ID if available
        lambda_request_id = getattr(context, 'aws_request_id', None) if context else None
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Probability lookup generated successfully",
                "lookup_rows": len(lookup_df),
                "output_file": str(lookup_path),
                "lambda_request_id": lambda_request_id,
            }),
        }
    except Exception as e:
        logger.error(f"Error generating probability lookup: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Failed to generate probability lookup",
                "message": str(e),
            }),
        }

