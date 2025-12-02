# Database Integration Setup Guide

This guide explains how to connect your Lambda functions and Streamlit app to PostgreSQL/RDS.

## Overview

The system now supports writing Lambda results to PostgreSQL and reading from the database in Streamlit:

1. **Lambda Handlers** → Write to PostgreSQL via `PostgresWriter`
2. **Streamlit App** → Reads from PostgreSQL via `PostgresReader` (with CSV fallback)

## Database Connection Configuration

### Option 1: DATABASE_URL (Recommended)

Set a single connection string environment variable:

```bash
export DATABASE_URL="postgresql://user:password@host:5432/dbname"
```

### Option 2: Individual Environment Variables

Set individual connection parameters:

```bash
export DB_HOST="your-rds-endpoint.amazonaws.com"
export DB_PORT="5432"
export DB_NAME="worldcup"
export DB_USER="postgres"
export DB_PASSWORD="your-password"
```

## Lambda Configuration

### 1. Add Environment Variables to Lambda Function

In AWS Lambda Console → Your Function → Configuration → Environment Variables:

```
DATABASE_URL=postgresql://user:password@host:5432/dbname
# OR use individual vars:
DB_HOST=your-rds-endpoint.amazonaws.com
DB_PORT=5432
DB_NAME=worldcup
DB_USER=postgres
DB_PASSWORD=your-password
ENVIRONMENT=production
```

### 2. Update Lambda VPC Configuration (if RDS is in VPC)

If your RDS instance is in a VPC:

1. Go to Lambda → Configuration → VPC
2. Select the same VPC as your RDS instance
3. Select subnets (at least 2 for high availability)
4. Select security group that allows access to RDS port (5432)

### 3. Update RDS Security Group

Ensure your RDS security group allows inbound connections from:
- Lambda security group (if Lambda is in VPC)
- Your IP address (for Streamlit local development)

## Streamlit Configuration

### Local Development

Create a `.env` file in your project root:

```bash
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

Or set environment variables before running Streamlit:

```bash
export DATABASE_URL="postgresql://user:password@host:5432/dbname"
streamlit run streamlit_collector.py
```

### Streamlit Cloud / Production

Set environment variables in your Streamlit Cloud settings:
- Go to your app → Settings → Secrets
- Add `DATABASE_URL` or individual DB_* variables

## Database Schema

Make sure your database has the required tables. Run the schema file:

```bash
psql -h your-host -U your-user -d worldcup -f schemas/schema_world_cup_qualifiers.sql
```

Required tables:
- `team_slot_probabilities` - Current team standings and probabilities
- `scraper_jobs` - Job execution logs
- `historical_standings` - Historical data (optional)
- `historical_probability_lookup` - Probability lookup table (optional)

## Testing the Connection

### Test Lambda Connection

You can test the Lambda handler locally:

```python
from scrapers.lambda_handlers import handler_current_standings
result = handler_current_standings({}, None)
print(result)
```

### Test Streamlit Connection

Run Streamlit and check the sidebar - it should show:
- ✅ Database Connected (if connection works)
- ⚠️ Database: ... (if connection fails, will use CSV fallback)

### Test Database Reader Directly

```python
from scrapers.db_reader import PostgresReader

reader = PostgresReader()
df = reader.get_team_probabilities()
print(df.head())

stats = reader.get_team_stats()
print(stats)
```

## How It Works

### Lambda Flow

1. EventBridge triggers Lambda function
2. Lambda calls `update_team_slot_probabilities()` (writes CSV/JSON)
3. Lambda uses `PostgresWriter` to write to database
4. Lambda logs job to `scraper_jobs` table
5. Returns success/failure status

### Streamlit Flow

1. App starts and tries to connect to database
2. If connected: reads from `team_slot_probabilities` table
3. If not connected: falls back to reading `team_slot_probabilities.csv`
4. Shows database connection status in sidebar
5. Displays recent Lambda jobs if database is available

## Troubleshooting

### Lambda Can't Connect to Database

1. **Check VPC Configuration**: Lambda must be in same VPC as RDS
2. **Check Security Groups**: RDS must allow Lambda security group
3. **Check Environment Variables**: Verify DATABASE_URL or DB_* vars are set
4. **Check RDS Endpoint**: Ensure you're using the correct endpoint
5. **Check CloudWatch Logs**: Look for connection errors

### Streamlit Can't Connect

1. **Check Environment Variables**: Set DATABASE_URL or DB_* vars
2. **Check Network**: Ensure your IP can reach RDS (check security groups)
3. **Check Credentials**: Verify username/password are correct
4. **Fallback Works**: App will use CSV if database unavailable

### Database Write Fails

- Lambda will continue and write to CSV/JSON even if database fails
- Check CloudWatch logs for specific error messages
- Verify table schema matches expected structure
- Check for permission issues (INSERT/UPDATE permissions)

## Security Best Practices

1. **Use Secrets Manager**: Store database credentials in AWS Secrets Manager
2. **Use IAM Database Authentication**: If supported by your RDS instance
3. **Use SSL/TLS**: Enable SSL for database connections
4. **Limit Access**: Restrict security groups to only necessary sources
5. **Rotate Credentials**: Regularly rotate database passwords

## Next Steps

1. Set up your RDS instance (if not already done)
2. Run the schema SQL to create tables
3. Configure Lambda environment variables
4. Test Lambda function manually
5. Configure Streamlit environment variables
6. Test Streamlit app
7. Monitor CloudWatch logs for any issues

