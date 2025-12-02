# S3 Setup for Historical Lookup CSV

## ✅ Completed Steps

1. ✅ S3 bucket created: `blck-worldcup-data`
2. ✅ CSV uploaded to: `s3://blck-worldcup-data/historical_probability_lookup.csv`
3. ✅ Lambda code updated to download from S3
4. ✅ Lambda package rebuilt: `lambda_deployment/scrapers_lambda.zip`

## 📋 Remaining Steps

### Step 1: Upload Lambda Package

**Via AWS Console:**
1. Go to https://console.aws.amazon.com/lambda/
2. Open function: `wc-qualifiers-current-standings`
3. In **Code** tab → **Upload from** → **.zip file**
4. Select: `/Users/personal/Documents/git-repos/BLCKWorldCup/lambda_deployment/scrapers_lambda.zip`
5. Click **Save**

**Via AWS CLI:**
```bash
cd /Users/personal/Documents/git-repos/BLCKWorldCup
aws lambda update-function-code \
  --function-name wc-qualifiers-current-standings \
  --zip-file fileb://lambda_deployment/scrapers_lambda.zip \
  --region us-east-1
```

### Step 2: Set Environment Variables

**Via AWS Console:**
1. In Lambda function → **Configuration** tab → **Environment variables**
2. Click **Edit**
3. Click **Add environment variable**
4. Add:
   - **Key**: `HISTORICAL_LOOKUP_S3_BUCKET`
   - **Value**: `blck-worldcup-data`
5. (Optional) Add:
   - **Key**: `HISTORICAL_LOOKUP_S3_KEY`
   - **Value**: `historical_probability_lookup.csv`
6. Click **Save**

**Via AWS CLI:**
```bash
aws lambda update-function-configuration \
  --function-name wc-qualifiers-current-standings \
  --environment Variables="{HISTORICAL_LOOKUP_S3_BUCKET=blck-worldcup-data,HISTORICAL_LOOKUP_S3_KEY=historical_probability_lookup.csv}" \
  --region us-east-1
```

### Step 3: Update IAM Permissions

Your Lambda execution role needs permission to read from S3.

**First, get your Lambda role name:**

**Via AWS Console:**
1. In Lambda function → **Configuration** tab → **Permissions**
2. Click on the **Execution role** link (opens IAM)
3. Note the role name (e.g., `wc-qualifiers-lambda-role`)

**Via AWS CLI:**
```bash
aws lambda get-function-configuration \
  --function-name wc-qualifiers-current-standings \
  --query Role \
  --output text \
  --region us-east-1
```
This returns something like: `arn:aws:iam::875741101104:role/wc-qualifiers-lambda-role`

Extract the role name (the part after `/role/`): `wc-qualifiers-lambda-role`

**Then add the S3 policy:**

**Via AWS Console:**
1. Go to **IAM** → **Roles**
2. Find and click your Lambda execution role
3. Click **Add permissions** → **Create inline policy**
4. Click **JSON** tab
5. Paste this policy:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": "arn:aws:s3:::blck-worldcup-data/*"
        }
    ]
}
```
6. Click **Next**
7. Name it: `LambdaS3ReadAccess`
8. Click **Create policy**

**Via AWS CLI:**
```bash
# Replace ROLE_NAME with your actual role name from above
ROLE_NAME="wc-qualifiers-lambda-role"

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name LambdaS3ReadAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::blck-worldcup-data/*"
    }]
  }' \
  --region us-east-1
```

### Step 4: Test the Function

**Via AWS Console:**
1. Go to **Test** tab
2. Create/use test event: `{}`
3. Click **Test**
4. Check **Logs** output - you should see:
   - `Downloading historical lookup from s3://blck-worldcup-data/historical_probability_lookup.csv`
   - `✅ Downloaded historical lookup CSV to /tmp/historical_probability_lookup.csv`
   - `Loaded X rank-level and Y bucket-level historical probabilities.`
   - **No warning** about missing CSV!

**Via AWS CLI:**
```bash
aws lambda invoke \
  --function-name wc-qualifiers-current-standings \
  --payload '{}' \
  --region us-east-1 \
  response.json && cat response.json
```

## 🔄 Updating the CSV in the Future

When you regenerate `historical_probability_lookup.csv` locally:

```bash
# Regenerate the CSV
python3 scrapers/historical_standings_fetcher.py

# Upload to S3
aws s3 cp historical_probability_lookup.csv \
  s3://blck-worldcup-data/historical_probability_lookup.csv \
  --region us-east-1
```

Lambda will automatically download the new version on the next run!


