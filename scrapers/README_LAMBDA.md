# AWS Lambda Deployment Guide

This directory contains scrapers designed to run on AWS Lambda with EventBridge scheduling.

## Structure

- `confederation_scraper.py` - Core ESPN scraper module
- `update_team_slot_probabilities.py` - Updates current standings and probabilities
- `historical_standings_fetcher.py` - Fetches historical data from past World Cups
- `lambda_handlers.py` - Lambda entry points for each scraper function
- `requirements_lambda.txt` - Python dependencies for Lambda

## Lambda Functions

### 1. `handler_current_standings`
**Purpose**: Update current team slot probabilities every 6 hours

**EventBridge Schedule**: `cron(0 */6 * * ? *)`

**Handler**: `lambda_handlers.handler_current_standings`

**Environment Variables**:
- `CONFED_SCRAPER_VERIFY_SSL` (optional): Set to `0` to disable SSL verification

### 2. `handler_historical_fetch`
**Purpose**: Backfill historical standings weekly

**EventBridge Schedule**: `cron(0 2 ? * SUN *)` (Sunday 2 AM)

**Handler**: `lambda_handlers.handler_historical_fetch`

**Event Payload** (optional):
```json
{
  "start_season": 1990,
  "end_season": 2025
}
```

### 3. `handler_update_probabilities`
**Purpose**: Regenerate probability lookup table after historical updates

**EventBridge Schedule**: `cron(0 3 ? * SUN *)` (Sunday 3 AM, after historical fetch)

**Handler**: `lambda_handlers.handler_update_probabilities`

## Deployment Steps

### 1. Create Lambda Deployment Package

```bash
# Create deployment directory
mkdir lambda_deployment
cd lambda_deployment

# Copy scraper files
cp -r ../scrapers .

# Install dependencies
pip install -r scrapers/requirements_lambda.txt -t .

# Create deployment zip
zip -r scrapers_lambda.zip . -x "*.pyc" "__pycache__/*" "*.git*"
```

### 2. Create Lambda Layers (Recommended)

For better dependency management, create Lambda layers:

```bash
# Create layer directory
mkdir python
pip install -r scrapers/requirements_lambda.txt -t python/

# Zip layer
zip -r lambda_layer.zip python/
```

Upload to Lambda Layers, then reference in your function configuration.

### 3. Create Lambda Functions

Use AWS CLI or Console:

```bash
# Create function for current standings
aws lambda create-function \
  --function-name wc-qualifiers-current-standings \
  --runtime python3.9 \
  --role arn:aws:iam::ACCOUNT:role/lambda-execution-role \
  --handler scrapers.lambda_handlers.handler_current_standings \
  --zip-file fileb://scrapers_lambda.zip \
  --timeout 300 \
  --memory-size 512

# Create function for historical fetch
aws lambda create-function \
  --function-name wc-qualifiers-historical-fetch \
  --runtime python3.9 \
  --role arn:aws:iam::ACCOUNT:role/lambda-execution-role \
  --handler scrapers.lambda_handlers.handler_historical_fetch \
  --zip-file fileb://scrapers_lambda.zip \
  --timeout 900 \
  --memory-size 1024

# Create function for probability update
aws lambda create-function \
  --function-name wc-qualifiers-update-probabilities \
  --runtime python3.9 \
  --role arn:aws:iam::ACCOUNT:role/lambda-execution-role \
  --handler scrapers.lambda_handlers.handler_update_probabilities \
  --zip-file fileb://scrapers_lambda.zip \
  --timeout 300 \
  --memory-size 512
```

### 4. Create EventBridge Rules

```bash
# Current standings - every 6 hours
aws events put-rule \
  --name wc-qualifiers-current-standings-schedule \
  --schedule-expression "cron(0 */6 * * ? *)" \
  --state ENABLED

aws lambda add-permission \
  --function-name wc-qualifiers-current-standings \
  --statement-id allow-eventbridge \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:REGION:ACCOUNT:rule/wc-qualifiers-current-standings-schedule

aws events put-targets \
  --rule wc-qualifiers-current-standings-schedule \
  --targets "Id=1,Arn=arn:aws:lambda:REGION:ACCOUNT:function:wc-qualifiers-current-standings"

# Historical fetch - weekly Sunday 2 AM
aws events put-rule \
  --name wc-qualifiers-historical-fetch-schedule \
  --schedule-expression "cron(0 2 ? * SUN *)" \
  --state ENABLED

aws lambda add-permission \
  --function-name wc-qualifiers-historical-fetch \
  --statement-id allow-eventbridge \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:REGION:ACCOUNT:rule/wc-qualifiers-historical-fetch-schedule

aws events put-targets \
  --rule wc-qualifiers-historical-fetch-schedule \
  --targets "Id=1,Arn=arn:aws:lambda:REGION:ACCOUNT:function:wc-qualifiers-historical-fetch"

# Probability update - weekly Sunday 3 AM
aws events put-rule \
  --name wc-qualifiers-update-probabilities-schedule \
  --schedule-expression "cron(0 3 ? * SUN *)" \
  --state ENABLED

aws lambda add-permission \
  --function-name wc-qualifiers-update-probabilities \
  --statement-id allow-eventbridge \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:REGION:ACCOUNT:rule/wc-qualifiers-update-probabilities-schedule

aws events put-targets \
  --rule wc-qualifiers-update-probabilities-schedule \
  --targets "Id=1,Arn=arn:aws:lambda:REGION:ACCOUNT:function:wc-qualifiers-update-probabilities"
```

## VPC Configuration (if using RDS)

If your Lambda needs to write to RDS, configure VPC:

1. Add VPC configuration to Lambda function
2. Ensure Lambda security group can reach RDS
3. Consider using RDS Proxy for connection pooling

## Monitoring

- CloudWatch Logs: Each function logs to `/aws/lambda/FUNCTION_NAME`
- CloudWatch Metrics: Monitor invocations, errors, duration
- Set up CloudWatch Alarms for failed invocations

## Cost Estimation

- Current standings: ~4 invocations/day × 30s = ~2 minutes/day
- Historical fetch: ~1 invocation/week × 15min = ~15 minutes/week
- Probability update: ~1 invocation/week × 5min = ~5 minutes/week

Total: ~$0.20-0.50/month (within free tier for first 1M requests)


