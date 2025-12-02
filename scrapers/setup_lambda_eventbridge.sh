#!/bin/bash
# Automated setup script for Lambda + EventBridge
# Usage: ./setup_lambda_eventbridge.sh [function-name]

set -e

FUNCTION_NAME=${1:-"current-standings"}
REGION=${AWS_REGION:-"us-east-1"}

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 Setting up Lambda + EventBridge for World Cup Qualifiers${NC}"
echo "Region: $REGION"
echo ""

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}❌ Error: AWS credentials not configured. Run 'aws configure' first.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ AWS Account: $ACCOUNT_ID${NC}"

# Step 1: Check/Create IAM Role
echo -e "\n${YELLOW}Step 1: Checking IAM Role...${NC}"
ROLE_NAME="wc-qualifiers-lambda-role"

if aws iam get-role --role-name $ROLE_NAME --region $REGION &>/dev/null; then
    echo -e "${GREEN}✓ Role exists${NC}"
    ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)
else
    echo -e "${YELLOW}Creating IAM role...${NC}"
    cat > /tmp/lambda-trust-policy.json << 'EOF'
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
    
    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
        --region $REGION
    
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
        --region $REGION
    
    sleep 5  # Wait for role to propagate
    ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)
    echo -e "${GREEN}✓ Role created: $ROLE_ARN${NC}"
fi

# Step 2: Create deployment package
echo -e "\n${YELLOW}Step 2: Creating deployment package...${NC}"
if [ ! -f "scrapers_lambda.zip" ]; then
    echo "Running deploy script..."
    ./deploy.sh $FUNCTION_NAME
    if [ ! -f "../lambda_deployment/scrapers_lambda.zip" ]; then
        echo -e "${RED}❌ Deployment package not found. Run deploy.sh first.${NC}"
        exit 1
    fi
    cp ../lambda_deployment/scrapers_lambda.zip .
fi
echo -e "${GREEN}✓ Deployment package ready${NC}"

# Step 3: Create Lambda function
echo -e "\n${YELLOW}Step 3: Creating/Updating Lambda function...${NC}"

case $FUNCTION_NAME in
    "current-standings")
        LAMBDA_FUNC="wc-qualifiers-current-standings"
        HANDLER="scrapers.lambda_handlers.handler_current_standings"
        TIMEOUT=300
        MEMORY=512
        CRON="0 */6 * * ? *"
        DESC="every 6 hours"
        ENV_VARS='CONFED_SCRAPER_VERIFY_SSL=0,OUTPUT_CSV_PATH=/tmp/team_slot_probabilities.csv,OUTPUT_JSON_PATH=/tmp/qualifier_data.json,HISTORICAL_LOOKUP_PATH=/tmp/historical_probability_lookup.csv'
        ;;
    "historical-fetch")
        LAMBDA_FUNC="wc-qualifiers-historical-fetch"
        HANDLER="scrapers.lambda_handlers.handler_historical_fetch"
        TIMEOUT=900
        MEMORY=1024
        CRON="0 2 ? * SUN *"
        DESC="weekly on Sunday 2 AM UTC"
        ENV_VARS='CONFED_SCRAPER_VERIFY_SSL=0,HISTORICAL_STANDINGS_PATH=/tmp/historical_standings.csv'
        ;;
    "update-probabilities")
        LAMBDA_FUNC="wc-qualifiers-update-probabilities"
        HANDLER="scrapers.lambda_handlers.handler_update_probabilities"
        TIMEOUT=300
        MEMORY=512
        CRON="0 3 ? * SUN *"
        DESC="weekly on Sunday 3 AM UTC"
        ENV_VARS='HISTORICAL_LOOKUP_PATH=/tmp/historical_probability_lookup.csv'
        ;;
    *)
        echo -e "${RED}❌ Unknown function: $FUNCTION_NAME${NC}"
        echo "Valid options: current-standings, historical-fetch, update-probabilities"
        exit 1
        ;;
esac

if aws lambda get-function --function-name $LAMBDA_FUNC --region $REGION &>/dev/null; then
    echo -e "${YELLOW}Function exists, updating code...${NC}"
    aws lambda update-function-code \
        --function-name $LAMBDA_FUNC \
        --zip-file fileb://scrapers_lambda.zip \
        --region $REGION \
        --quiet
    
    aws lambda update-function-configuration \
        --function-name $LAMBDA_FUNC \
        --timeout $TIMEOUT \
        --memory-size $MEMORY \
        --environment Variables="{$ENV_VARS}" \
        --region $REGION \
        --quiet
    
    echo -e "${GREEN}✓ Function updated${NC}"
else
    echo -e "${YELLOW}Creating new function...${NC}"
    aws lambda create-function \
        --function-name $LAMBDA_FUNC \
        --runtime python3.9 \
        --role $ROLE_ARN \
        --handler $HANDLER \
        --zip-file fileb://scrapers_lambda.zip \
        --timeout $TIMEOUT \
        --memory-size $MEMORY \
        --environment Variables="{$ENV_VARS}" \
        --region $REGION \
        --description "World Cup qualifiers: $FUNCTION_NAME" \
        --quiet
    
    echo -e "${GREEN}✓ Function created${NC}"
fi

# Step 4: Create EventBridge rule
echo -e "\n${YELLOW}Step 4: Creating EventBridge rule...${NC}"
RULE_NAME="${LAMBDA_FUNC}-schedule"

if aws events describe-rule --name $RULE_NAME --region $REGION &>/dev/null; then
    echo -e "${YELLOW}Rule exists, updating...${NC}"
    aws events put-rule \
        --name $RULE_NAME \
        --schedule-expression "cron($CRON)" \
        --state ENABLED \
        --region $REGION \
        --quiet
else
    aws events put-rule \
        --name $RULE_NAME \
        --schedule-expression "cron($CRON)" \
        --state ENABLED \
        --description "Schedule for $LAMBDA_FUNC ($DESC)" \
        --region $REGION \
        --quiet
    echo -e "${GREEN}✓ Rule created${NC}"
fi

# Step 5: Add Lambda permission
echo -e "\n${YELLOW}Step 5: Adding EventBridge permissions...${NC}"
RULE_ARN="arn:aws:events:$REGION:$ACCOUNT_ID:rule/$RULE_NAME"

aws lambda add-permission \
    --function-name $LAMBDA_FUNC \
    --statement-id "allow-eventbridge-$(date +%s)" \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn $RULE_ARN \
    --region $REGION \
    --quiet 2>/dev/null || echo "Permission already exists"

# Step 6: Add Lambda as target
echo -e "\n${YELLOW}Step 6: Adding Lambda as EventBridge target...${NC}"
FUNCTION_ARN="arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$LAMBDA_FUNC"

aws events put-targets \
    --rule $RULE_NAME \
    --targets "Id=1,Arn=$FUNCTION_ARN" \
    --region $REGION \
    --quiet

echo -e "${GREEN}✓ Target added${NC}"

# Summary
echo -e "\n${GREEN}✅ Setup Complete!${NC}"
echo ""
echo "Function: $LAMBDA_FUNC"
echo "Schedule: $DESC (cron: $CRON)"
echo "Rule: $RULE_NAME"
echo ""
echo "Test the function:"
echo "  aws lambda invoke --function-name $LAMBDA_FUNC --region $REGION --payload '{}' response.json"
echo ""
echo "View logs:"
echo "  aws logs tail /aws/lambda/$LAMBDA_FUNC --follow --region $REGION"


