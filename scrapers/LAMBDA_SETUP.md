# Lambda Deployment Guide - Step by Step

This guide walks you through preparing and deploying the World Cup qualifier scrapers to AWS Lambda.

## Prerequisites

- AWS CLI configured with appropriate credentials
- Python 3.9+ (Lambda runtime)
- Docker (optional, for local testing with Lambda environment)

## Step 1: Prepare Deployment Package

### Option A: Manual Package Creation

```bash
# Create deployment directory
mkdir -p lambda_deployment/scrapers
cd lambda_deployment

# Copy scraper files
cp -r ../scrapers/* scrapers/

# Install dependencies to a local directory
pip install -r scrapers/requirements_lambda.txt -t . --platform manylinux2014_x86_64 --only-binary :all:

# Remove unnecessary files
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
find . -type d -name "*.dist-info" -exec rm -r {} + 2>/dev/null || true
find . -type d -name "tests" -exec rm -r {} + 2>/dev/null || true

# Create deployment zip
zip -r scrapers_lambda.zip . -x "*.git*" "*.md" "*.txt" "*.log"

# Verify size (Lambda limit is 50MB zipped, 250MB unzipped)
ls -lh scrapers_lambda.zip
```

### Option B: Using Docker (Recommended for consistent builds)

```bash
# Create Dockerfile for Lambda build
cat > Dockerfile.lambda << 'EOF'
FROM public.ecr.aws/lambda/python:3.9

# Install dependencies
COPY scrapers/requirements_lambda.txt /tmp/
RUN pip install -r /tmp/requirements_lambda.txt -t /var/task

# Copy application code
COPY scrapers/ /var/task/scrapers/

# Set handler
CMD ["scrapers.lambda_handlers.handler_current_standings"]
EOF

# Build and extract
docker build -f Dockerfile.lambda -t lambda-scrapers .
docker create --name lambda-container lambda-scrapers
docker cp lambda-container:/var/task ./lambda_package
docker rm lambda-container
cd lambda_package && zip -r ../scrapers_lambda.zip .
```

## Step 2: Create Lambda Layers (Optional but Recommended)

For better dependency management, create a Lambda layer:

```bash
# Create layer directory
mkdir -p lambda_layer/python
cd lambda_layer/python

# Install dependencies
pip install -r ../../scrapers/requirements_lambda.txt -t .

# Remove unnecessary files
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete

# Create layer zip
cd ..
zip -r ../lambda_layer.zip python/

# Upload layer
aws lambda publish-layer-version \
  --layer-name wc-qualifiers-dependencies \
  --zip-file fileb://lambda_layer.zip \
  --compatible-runtimes python3.9
```

Note the Layer ARN from the output (you'll need it in Step 3).

## Step 3: Create IAM Role for Lambda

```bash
# Create trust policy
cat > lambda-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name wc-qualifiers-lambda-role \
  --assume-role-policy-document file://lambda-trust-policy.json

# Attach basic Lambda execution policy
aws iam attach-role-policy \
  --role-name wc-qualifiers-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# If using RDS, attach VPC execution policy
aws iam attach-role-policy \
  --role-name wc-qualifiers-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole

# Get role ARN
aws iam get-role --role-name wc-qualifiers-lambda-role --query 'Role.Arn' --output text
```

Note the Role ARN (you'll need it in Step 4).

## Step 4: Create Lambda Functions

### Function 1: Current Standings Updater

```bash
# Create function
aws lambda create-function \
  --function-name wc-qualifiers-current-standings \
  --runtime python3.9 \
  --role <ROLE_ARN_FROM_STEP_3> \
  --handler scrapers.lambda_handlers.handler_current_standings \
  --zip-file fileb://scrapers_lambda.zip \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables="{
    CONFED_SCRAPER_VERIFY_SSL=0,
    OUTPUT_CSV_PATH=/tmp/team_slot_probabilities.csv,
    OUTPUT_JSON_PATH=/tmp/qualifier_data.json,
    HISTORICAL_LOOKUP_PATH=/tmp/historical_probability_lookup.csv
  }" \
  --layers <LAYER_ARN_FROM_STEP_2> \
  --description "Updates current World Cup qualifier standings and probabilities"

# Or update existing function
aws lambda update-function-code \
  --function-name wc-qualifiers-current-standings \
  --zip-file fileb://scrapers_lambda.zip
```

### Function 2: Historical Data Fetcher

```bash
aws lambda create-function \
  --function-name wc-qualifiers-historical-fetch \
  --runtime python3.9 \
  --role <ROLE_ARN> \
  --handler scrapers.lambda_handlers.handler_historical_fetch \
  --zip-file fileb://scrapers_lambda.zip \
  --timeout 900 \
  --memory-size 1024 \
  --environment Variables="{
    CONFED_SCRAPER_VERIFY_SSL=0,
    HISTORICAL_STANDINGS_PATH=/tmp/historical_standings.csv
  }" \
  --layers <LAYER_ARN> \
  --description "Fetches historical World Cup qualifying data"
```

### Function 3: Probability Lookup Generator

```bash
aws lambda create-function \
  --function-name wc-qualifiers-update-probabilities \
  --runtime python3.9 \
  --role <ROLE_ARN> \
  --handler scrapers.lambda_handlers.handler_update_probabilities \
  --zip-file fileb://scrapers_lambda.zip \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables="{
    HISTORICAL_LOOKUP_PATH=/tmp/historical_probability_lookup.csv
  }" \
  --layers <LAYER_ARN> \
  --description "Regenerates historical probability lookup table"
```

## Step 5: Configure VPC (If Using RDS)

If your Lambda needs to connect to RDS:

```bash
# Update function with VPC configuration
aws lambda update-function-configuration \
  --function-name wc-qualifiers-current-standings \
  --vpc-config "{
    SubnetIds=[subnet-12345,subnet-67890],
    SecurityGroupIds=[sg-12345]
  }"
```

**Important**: VPC configuration adds cold start latency. Consider using RDS Proxy for connection pooling.

## Step 6: Set Up EventBridge Rules

### Rule 1: Current Standings (Every 6 Hours)

```bash
# Create rule
aws events put-rule \
  --name wc-qualifiers-current-standings-schedule \
  --schedule-expression "cron(0 */6 * * ? *)" \
  --state ENABLED \
  --description "Update current standings every 6 hours"

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
  --function-name wc-qualifiers-current-standings \
  --statement-id allow-eventbridge-current-standings \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:<REGION>:<ACCOUNT_ID>:rule/wc-qualifiers-current-standings-schedule

# Add Lambda as target
aws events put-targets \
  --rule wc-qualifiers-current-standings-schedule \
  --targets "Id=1,Arn=arn:aws:lambda:<REGION>:<ACCOUNT_ID>:function:wc-qualifiers-current-standings"
```

### Rule 2: Historical Fetch (Weekly)

```bash
aws events put-rule \
  --name wc-qualifiers-historical-fetch-schedule \
  --schedule-expression "cron(0 2 ? * SUN *)" \
  --state ENABLED \
  --description "Fetch historical data weekly on Sunday 2 AM UTC"

aws lambda add-permission \
  --function-name wc-qualifiers-historical-fetch \
  --statement-id allow-eventbridge-historical-fetch \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:<REGION>:<ACCOUNT_ID>:rule/wc-qualifiers-historical-fetch-schedule

aws events put-targets \
  --rule wc-qualifiers-historical-fetch-schedule \
  --targets "Id=1,Arn=arn:aws:lambda:<REGION>:<ACCOUNT_ID>:function:wc-qualifiers-historical-fetch"
```

### Rule 3: Probability Update (After Historical Fetch)

```bash
aws events put-rule \
  --name wc-qualifiers-update-probabilities-schedule \
  --schedule-expression "cron(0 3 ? * SUN *)" \
  --state ENABLED \
  --description "Update probability lookup after historical fetch"

aws lambda add-permission \
  --function-name wc-qualifiers-update-probabilities \
  --statement-id allow-eventbridge-update-probabilities \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:<REGION>:<ACCOUNT_ID>:rule/wc-qualifiers-update-probabilities-schedule

aws events put-targets \
  --rule wc-qualifiers-update-probabilities-schedule \
  --targets "Id=1,Arn=arn:aws:lambda:<REGION>:<ACCOUNT_ID>:function:wc-qualifiers-update-probabilities"
```

## Step 7: Test Locally (Before Deploying)

Create a test script:

```python
# test_lambda_local.py
import json
from scrapers.lambda_handlers import handler_current_standings

# Test event (empty for scheduled runs)
event = {}
context = type('Context', (), {
    'function_name': 'test',
    'function_version': '$LATEST',
    'invoked_function_arn': 'arn:aws:lambda:us-east-1:123456789012:function:test',
    'memory_limit_in_mb': 512,
    'aws_request_id': 'test-request-id'
})()

result = handler_current_standings(event, context)
print(json.dumps(result, indent=2))
```

Run it:
```bash
python test_lambda_local.py
```

## Step 8: Test in Lambda

```bash
# Invoke function manually
aws lambda invoke \
  --function-name wc-qualifiers-current-standings \
  --payload '{}' \
  response.json

# Check response
cat response.json

# Check logs
aws logs tail /aws/lambda/wc-qualifiers-current-standings --follow
```

## Step 9: Monitor and Debug

### CloudWatch Logs
```bash
# View recent logs
aws logs tail /aws/lambda/wc-qualifiers-current-standings --since 1h

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/wc-qualifiers-current-standings \
  --filter-pattern "ERROR"
```

### CloudWatch Metrics
Monitor in AWS Console:
- Invocations
- Errors
- Duration
- Throttles

### Set Up Alarms
```bash
# Alarm for function errors
aws cloudwatch put-metric-alarm \
  --alarm-name wc-qualifiers-errors \
  --alarm-description "Alert on Lambda function errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=FunctionName,Value=wc-qualifiers-current-standings
```

## Step 10: Handle Output (S3 or RDS)

### Option A: Write to S3

Update Lambda handlers to upload results to S3:

```python
import boto3
s3 = boto3.client('s3')

# After generating CSV
s3.upload_file(
    '/tmp/team_slot_probabilities.csv',
    'your-bucket-name',
    'team_slot_probabilities.csv'
)
```

### Option B: Write to RDS

Use the schema from `schemas/schema_world_cup_qualifiers.sql` and add database writer:

```python
import psycopg2
import os

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
# Insert into team_slot_probabilities table
```

## Troubleshooting

### Common Issues

1. **Timeout Errors**: Increase timeout or optimize code
2. **Memory Errors**: Increase memory allocation
3. **Import Errors**: Check layer includes all dependencies
4. **VPC Connection Issues**: Verify security groups and subnets
5. **Cold Starts**: Use provisioned concurrency for critical functions

### Debugging Tips

- Enable X-Ray tracing for detailed execution traces
- Use CloudWatch Logs Insights for querying logs
- Test with small datasets first
- Monitor Lambda metrics in CloudWatch

## Cost Estimation

- **Free Tier**: 1M requests/month, 400K GB-seconds/month
- **Estimated Monthly Cost** (beyond free tier):
  - Current standings: ~4/day × 30s × 512MB = ~$0.20/month
  - Historical fetch: ~1/week × 15min × 1024MB = ~$0.10/month
  - **Total**: ~$0.30-0.50/month

## Next Steps

1. Set up S3 bucket for output storage
2. Configure RDS connection (if using database)
3. Set up CloudWatch dashboards for monitoring
4. Create CI/CD pipeline for automated deployments
5. Add database logging (scraper_jobs, prediction_runs tables)


