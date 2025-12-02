#!/bin/bash
# Quick script to set up daily EventBridge schedule for Lambda
# Usage: ./setup_daily_schedule.sh [time-utc]

set -e

FUNCTION_NAME="wc-qualifiers-current-standings"
REGION=${AWS_DEFAULT_REGION:-"us-east-1"}
TIME_UTC=${1:-"02:00"}  # Default: 2 AM UTC (can be changed)

# Parse time (format: HH:MM)
HOUR=$(echo $TIME_UTC | cut -d: -f1)
MINUTE=$(echo $TIME_UTC | cut -d: -f2)

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}📅 Setting up daily EventBridge schedule for Lambda${NC}"
echo "Function: $FUNCTION_NAME"
echo "Schedule: Daily at $TIME_UTC UTC"
echo "Region: $REGION"
echo ""

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}❌ Error: AWS credentials not configured. Run 'aws configure' first.${NC}"
    exit 1
fi

# Check if Lambda function exists
if ! aws lambda get-function --function-name $FUNCTION_NAME --region $REGION &>/dev/null; then
    echo -e "${RED}❌ Lambda function '$FUNCTION_NAME' not found.${NC}"
    echo ""
    echo "Please create the Lambda function first:"
    echo "  1. Upload the zip package via AWS Console or CLI"
    echo "  2. Or run: ./scrapers/setup_lambda_eventbridge.sh current-standings"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ Lambda function found${NC}"

# Create/Update EventBridge rule
RULE_NAME="${FUNCTION_NAME}-daily-schedule"
CRON_EXPRESSION="cron($MINUTE $HOUR * * ? *)"

echo -e "\n${YELLOW}Creating/updating EventBridge rule...${NC}"

if aws events describe-rule --name $RULE_NAME --region $REGION &>/dev/null; then
    echo "  → Updating existing rule..."
    aws events put-rule \
        --name $RULE_NAME \
        --schedule-expression "$CRON_EXPRESSION" \
        --state ENABLED \
        --region $REGION \
        --description "Daily schedule for $FUNCTION_NAME at $TIME_UTC UTC" \
        --quiet
    echo -e "${GREEN}✓ Rule updated${NC}"
else
    echo "  → Creating new rule..."
    aws events put-rule \
        --name $RULE_NAME \
        --schedule-expression "$CRON_EXPRESSION" \
        --state ENABLED \
        --description "Daily schedule for $FUNCTION_NAME at $TIME_UTC UTC" \
        --region $REGION \
        --quiet
    echo -e "${GREEN}✓ Rule created${NC}"
fi

# Add Lambda permission for EventBridge
echo -e "\n${YELLOW}Adding EventBridge permissions to Lambda...${NC}"
RULE_ARN="arn:aws:events:$REGION:$ACCOUNT_ID:rule/$RULE_NAME"
STATEMENT_ID="allow-eventbridge-daily-$(date +%s)"

aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id "$STATEMENT_ID" \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn $RULE_ARN \
    --region $REGION \
    --quiet 2>/dev/null && echo -e "${GREEN}✓ Permission added${NC}" || echo "  → Permission already exists (skipping)"

# Add Lambda as target
echo -e "\n${YELLOW}Adding Lambda as EventBridge target...${NC}"
FUNCTION_ARN="arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$FUNCTION_NAME"

aws events put-targets \
    --rule $RULE_NAME \
    --targets "Id=1,Arn=$FUNCTION_ARN" \
    --region $REGION \
    --quiet

echo -e "${GREEN}✓ Target added${NC}"

# Summary
echo -e "\n${GREEN}✅ Daily schedule configured!${NC}"
echo ""
echo "Rule name: $RULE_NAME"
echo "Schedule: Daily at $TIME_UTC UTC"
echo "Cron: $CRON_EXPRESSION"
echo ""
echo "To test manually:"
echo "  aws lambda invoke --function-name $FUNCTION_NAME --region $REGION --payload '{}' response.json"
echo ""
echo "To view logs:"
echo "  aws logs tail /aws/lambda/$FUNCTION_NAME --follow --region $REGION"
echo ""
echo "To disable the schedule:"
echo "  aws events disable-rule --name $RULE_NAME --region $REGION"
echo ""
echo "To change the time, run this script again with a different time:"
echo "  ./setup_daily_schedule.sh 14:30  # Runs at 2:30 PM UTC"


