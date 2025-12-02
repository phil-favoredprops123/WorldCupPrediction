#!/bin/bash
# Quick deployment script for Lambda functions
# Usage: ./deploy.sh [function-name]

set -e

FUNCTION_NAME=${1:-"all"}
REGION=${AWS_REGION:-"us-east-1"}
LAYER_NAME="wc-qualifiers-dependencies"

echo "🚀 Deploying World Cup Qualifiers Scrapers to Lambda"
echo "Region: $REGION"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create deployment package
echo -e "${YELLOW}📦 Creating deployment package...${NC}"
mkdir -p lambda_deployment/scrapers
cp -r scrapers/* lambda_deployment/scrapers/ 2>/dev/null || cp -r ./* lambda_deployment/scrapers/

cd lambda_deployment

# Install dependencies
echo -e "${YELLOW}📥 Installing dependencies (Linux-compatible wheels)...${NC}"
# Use pip's cross-platform install so the packages match AWS Lambda's Linux environment,
# even when building on macOS. This avoids numpy/pandas import errors on Lambda.
python3 -m pip install \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 39 \
  --only-binary=:all: \
  -r scrapers/requirements_lambda.txt \
  -t . \
  --upgrade \
  --quiet

# Clean up
echo -e "${YELLOW}🧹 Cleaning up...${NC}"
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete
find . -type d -name "*.dist-info" -exec rm -r {} + 2>/dev/null || true

# Create zip
echo -e "${YELLOW}📦 Creating zip file...${NC}"
zip -r scrapers_lambda.zip . -q -x "*.git*" "*.md" "*.txt" "*.log" "*.sh"

ZIP_SIZE=$(du -h scrapers_lambda.zip | cut -f1)
echo -e "${GREEN}✓ Package created: scrapers_lambda.zip ($ZIP_SIZE)${NC}"

# Check size
ZIP_SIZE_BYTES=$(stat -f%z scrapers_lambda.zip 2>/dev/null || stat -c%s scrapers_lambda.zip 2>/dev/null)
if [ "$ZIP_SIZE_BYTES" -gt 52428800 ]; then
    echo -e "${YELLOW}⚠️  Warning: Package size exceeds 50MB. Consider using Lambda Layers.${NC}"
fi

# Deploy functions
deploy_function() {
    local func_name=$1
    local handler=$2
    local timeout=$3
    local memory=$4
    
    echo -e "${YELLOW}📤 Deploying $func_name...${NC}"
    
    # Check if function exists
    if aws lambda get-function --function-name "$func_name" --region "$REGION" &>/dev/null; then
        echo "  → Updating existing function..."
        aws lambda update-function-code \
            --function-name "$func_name" \
            --zip-file fileb://scrapers_lambda.zip \
            --region "$REGION" \
            --quiet
        
        aws lambda update-function-configuration \
            --function-name "$func_name" \
            --timeout "$timeout" \
            --memory-size "$memory" \
            --region "$REGION" \
            --quiet
    else
        echo "  → Creating new function..."
        echo "  ⚠️  Note: You need to create the function first with IAM role. Run:"
        echo "     aws lambda create-function --function-name $func_name --runtime python3.9 --role <ROLE_ARN> --handler $handler --zip-file fileb://scrapers_lambda.zip"
    fi
    
    echo -e "${GREEN}✓ $func_name deployed${NC}"
}

# Deploy based on argument
if [ "$FUNCTION_NAME" = "all" ] || [ "$FUNCTION_NAME" = "current-standings" ]; then
    deploy_function "wc-qualifiers-current-standings" \
        "scrapers.lambda_handlers.handler_current_standings" \
        300 512
fi

if [ "$FUNCTION_NAME" = "all" ] || [ "$FUNCTION_NAME" = "historical-fetch" ]; then
    deploy_function "wc-qualifiers-historical-fetch" \
        "scrapers.lambda_handlers.handler_historical_fetch" \
        900 1024
fi

if [ "$FUNCTION_NAME" = "all" ] || [ "$FUNCTION_NAME" = "update-probabilities" ]; then
    deploy_function "wc-qualifiers-update-probabilities" \
        "scrapers.lambda_handlers.handler_update_probabilities" \
        300 512
fi

cd ..
echo -e "${GREEN}✅ Deployment complete!${NC}"


