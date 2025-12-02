# AWS Lambda + EventBridge Setup Guide

Step-by-step instructions to deploy your World Cup qualifier scrapers to AWS Lambda with EventBridge scheduling.

## Prerequisites

- AWS account with appropriate permissions
- AWS CLI installed and configured (`aws configure`)
- Python 3.9+ installed locally
- Deployment package ready (see `LAMBDA_SETUP.md`)

## Step 1: Create IAM Role for Lambda

### Option A: Using AWS CLI

```bash
# 1. Create trust policy file
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

# 2. Create the IAM role
aws iam create-role \
  --role-name wc-qualifiers-lambda-role \
  --assume-role-policy-document file://lambda-trust-policy.json

# 3. Attach basic execution policy
aws iam attach-role-policy \
  --role-name wc-qualifiers-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# 4. Get the role ARN (save this for Step 2)
aws iam get-role \
  --role-name wc-qualifiers-lambda-role \
  --query 'Role.Arn' \
  --output text
```

**Save the Role ARN** - you'll need it in the next step (format: `arn:aws:iam::ACCOUNT_ID:role/wc-qualifiers-lambda-role`)

### Option B: Using AWS Console

1. Go to **IAM Console** → **Roles** → **Create role**
2. Select **AWS service** → **Lambda**
3. Click **Next**
4. Search and attach: **AWSLambdaBasicExecutionRole**
5. Name: `wc-qualifiers-lambda-role`
6. Click **Create role**
7. Copy the **Role ARN** from the role details page

## Step 2: Create Deployment Package

```bash
# Navigate to scrapers directory
cd scrapers

# Create deployment directory
mkdir -p ../lambda_deployment/scrapers
cd ../lambda_deployment

# Copy scraper files
cp -r ../scrapers/* scrapers/

# Install dependencies
pip install -r scrapers/requirements_lambda.txt -t . --quiet

# Clean up unnecessary files
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
find . -type d -name "*.dist-info" -exec rm -r {} + 2>/dev/null || true

# Create zip file
zip -r scrapers_lambda.zip . -q -x "*.git*" "*.md" "*.txt" "*.log" "*.sh"

# Verify size (should be under 50MB)
ls -lh scrapers_lambda.zip
```

## Step 3: Create Lambda Function

### Option A: Using AWS CLI

Replace `<ROLE_ARN>` with the ARN from Step 1, and `<REGION>` with your AWS region (e.g., `us-east-1`):

```bash
# Set variables
ROLE_ARN="arn:aws:iam::YOUR_ACCOUNT_ID:role/wc-qualifiers-lambda-role"
REGION="us-east-1"
FUNCTION_NAME="wc-qualifiers-current-standings"

# Create the Lambda function
aws lambda create-function \
  --function-name $FUNCTION_NAME \
  --runtime python3.9 \
  --role $ROLE_ARN \
  --handler scrapers.lambda_handlers.handler_current_standings \
  --zip-file fileb://scrapers_lambda.zip \
  --timeout 300 \
  --memory-size 512 \
  --region $REGION \
  --environment Variables="{
    CONFED_SCRAPER_VERIFY_SSL=0,
    OUTPUT_CSV_PATH=/tmp/team_slot_probabilities.csv,
    OUTPUT_JSON_PATH=/tmp/qualifier_data.json,
    HISTORICAL_LOOKUP_PATH=/tmp/historical_probability_lookup.csv
  }" \
  --description "Updates current World Cup qualifier standings and probabilities"
```

### Option B: Using AWS Console

1. Go to **Lambda Console** → **Functions** → **Create function**
2. Select **Author from scratch**
3. **Function name**: `wc-qualifiers-current-standings`
4. **Runtime**: Python 3.9
5. **Architecture**: x86_64
6. Click **Change default execution role**
   - Select **Use an existing role**
   - Choose `wc-qualifiers-lambda-role`
7. Click **Create function**
8. Scroll to **Code source** section
9. Click **Upload from** → **.zip file**
10. Select your `scrapers_lambda.zip` file
11. Click **Save**
12. In **Configuration** → **General configuration** → **Edit**:
    - **Timeout**: 5 min 0 sec
    - **Memory**: 512 MB
13. In **Configuration** → **Environment variables** → **Edit**:
    - Add:
      - `CONFED_SCRAPER_VERIFY_SSL` = `0`
      - `OUTPUT_CSV_PATH` = `/tmp/team_slot_probabilities.csv`
      - `OUTPUT_JSON_PATH` = `/tmp/qualifier_data.json`
      - `HISTORICAL_LOOKUP_PATH` = `/tmp/historical_probability_lookup.csv`
14. In **Code** section, set **Handler** to: `scrapers.lambda_handlers.handler_current_standings`
15. Click **Deploy**

## Step 4: Test Lambda Function

### Option A: Using AWS CLI

```bash
# Invoke function manually
aws lambda invoke \
  --function-name wc-qualifiers-current-standings \
  --region $REGION \
  --payload '{}' \
  response.json

# View response
cat response.json

# Check logs
aws logs tail /aws/lambda/wc-qualifiers-current-standings --follow --region $REGION
```

### Option B: Using AWS Console

1. Go to your Lambda function
2. Click **Test** tab
3. Click **Create new test event**
4. **Event name**: `test-event`
5. **Event JSON**: `{}`
6. Click **Save**
7. Click **Test**
8. View results in **Execution results**
9. Check **CloudWatch Logs** for detailed output

## Step 5: Create EventBridge Rule

### Option A: Using AWS CLI

```bash
# Set variables
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
FUNCTION_NAME="wc-qualifiers-current-standings"
RULE_NAME="wc-qualifiers-current-standings-schedule"

# 1. Create EventBridge rule (runs every 6 hours)
aws events put-rule \
  --name $RULE_NAME \
  --schedule-expression "cron(0 */6 * * ? *)" \
  --state ENABLED \
  --description "Update current standings every 6 hours" \
  --region $REGION

# 2. Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
  --function-name $FUNCTION_NAME \
  --statement-id allow-eventbridge-invoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "arn:aws:events:$REGION:$ACCOUNT_ID:rule/$RULE_NAME" \
  --region $REGION

# 3. Add Lambda as target for the rule
aws events put-targets \
  --rule $RULE_NAME \
  --targets "Id=1,Arn=arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$FUNCTION_NAME" \
  --region $REGION

# Verify the rule was created
aws events describe-rule --name $RULE_NAME --region $REGION
```

### Option B: Using AWS Console

1. Go to **EventBridge Console** → **Rules** → **Create rule**
2. **Name**: `wc-qualifiers-current-standings-schedule`
3. **Description**: `Update current standings every 6 hours`
4. **Event bus**: `default`
5. **Rule type**: **Schedule**
6. **Schedule pattern**: **Cron-based schedule**
7. **Cron expression**: `0 */6 * * ? *` (every 6 hours)
8. Click **Next**
9. **Target types**: **AWS service**
10. **Select a target**: **Lambda function**
11. **Function**: Select `wc-qualifiers-current-standings`
12. Click **Next**
13. Review and click **Create rule**

## Step 6: Verify Setup

### Check Rule Status

```bash
# List all rules
aws events list-rules --name-prefix wc-qualifiers --region $REGION

# Check rule targets
aws events list-targets-by-rule \
  --rule wc-qualifiers-current-standings-schedule \
  --region $REGION
```

### Monitor Execution

1. **CloudWatch Logs**:
   ```bash
   aws logs tail /aws/lambda/wc-qualifiers-current-standings --follow --region $REGION
   ```

2. **Lambda Metrics** (Console):
   - Go to Lambda function → **Monitor** tab
   - View: Invocations, Duration, Errors, Throttles

3. **EventBridge Metrics** (Console):
   - Go to EventBridge → **Rules** → Your rule → **Metrics** tab

## Step 7: Create Additional Functions (Optional)

Repeat Steps 3-5 for the other two functions:

### Historical Fetch Function

```bash
# Create function
aws lambda create-function \
  --function-name wc-qualifiers-historical-fetch \
  --runtime python3.9 \
  --role $ROLE_ARN \
  --handler scrapers.lambda_handlers.handler_historical_fetch \
  --zip-file fileb://scrapers_lambda.zip \
  --timeout 900 \
  --memory-size 1024 \
  --region $REGION \
  --environment Variables="{CONFED_SCRAPER_VERIFY_SSL=0,HISTORICAL_STANDINGS_PATH=/tmp/historical_standings.csv}"

# Create weekly schedule (Sunday 2 AM UTC)
aws events put-rule \
  --name wc-qualifiers-historical-fetch-schedule \
  --schedule-expression "cron(0 2 ? * SUN *)" \
  --state ENABLED \
  --region $REGION

# Add permission and target (similar to Step 5)
```

### Probability Update Function

```bash
# Create function
aws lambda create-function \
  --function-name wc-qualifiers-update-probabilities \
  --runtime python3.9 \
  --role $ROLE_ARN \
  --handler scrapers.lambda_handlers.handler_update_probabilities \
  --zip-file fileb://scrapers_lambda.zip \
  --timeout 300 \
  --memory-size 512 \
  --region $REGION \
  --environment Variables="{HISTORICAL_LOOKUP_PATH=/tmp/historical_probability_lookup.csv}"

# Create weekly schedule (Sunday 3 AM UTC)
aws events put-rule \
  --name wc-qualifiers-update-probabilities-schedule \
  --schedule-expression "cron(0 3 ? * SUN *)" \
  --state ENABLED \
  --region $REGION

# Add permission and target
```

## Step 8: Set Up CloudWatch Alarms (Optional)

```bash
# Alarm for function errors
aws cloudwatch put-metric-alarm \
  --alarm-name wc-qualifiers-errors \
  --alarm-description "Alert when Lambda function has errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=FunctionName,Value=wc-qualifiers-current-standings \
  --region $REGION
```

## Troubleshooting

### Common Issues

1. **"Access Denied" errors**:
   - Verify IAM role has correct permissions
   - Check EventBridge has permission to invoke Lambda

2. **Function timeout**:
   - Increase timeout in function configuration
   - Check CloudWatch Logs for slow operations

3. **Import errors**:
   - Verify all dependencies are in the zip file
   - Check handler path is correct

4. **Function not executing**:
   - Verify EventBridge rule is enabled
   - Check rule targets are configured
   - Verify cron expression is correct

### Debug Commands

```bash
# View recent invocations
aws lambda list-functions --region $REGION

# Get function configuration
aws lambda get-function-configuration \
  --function-name wc-qualifiers-current-standings \
  --region $REGION

# View recent logs
aws logs tail /aws/lambda/wc-qualifiers-current-standings \
  --since 1h \
  --region $REGION

# Check EventBridge rule
aws events describe-rule \
  --name wc-qualifiers-current-standings-schedule \
  --region $REGION
```

## Quick Reference: Cron Expressions

- Every 6 hours: `0 */6 * * ? *`
- Every day at 2 AM: `0 2 * * ? *`
- Every Sunday at 2 AM: `0 2 ? * SUN *`
- Every Monday at 9 AM: `0 9 ? * MON *`

## Next Steps

1. **Set up S3 bucket** for storing output files
2. **Configure RDS connection** if using database
3. **Set up CloudWatch dashboards** for monitoring
4. **Create CI/CD pipeline** for automated deployments

## Cost Estimate

- **Free Tier**: 1M requests/month, 400K GB-seconds/month
- **Estimated Cost**: ~$0.20-0.50/month (beyond free tier)
  - Current standings: 4 invocations/day × 30s × 512MB
  - Historical fetch: 1 invocation/week × 15min × 1024MB

