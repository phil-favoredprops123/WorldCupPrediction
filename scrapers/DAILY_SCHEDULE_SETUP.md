# Setting Up Daily EventBridge Schedule

This guide shows you how to set up EventBridge to trigger your Lambda function daily.

## Prerequisites

- Lambda function `wc-qualifiers-current-standings` must exist
- AWS CLI configured OR access to AWS Console
- Region: `us-east-1` (or your preferred region)

---

## Option 1: Quick Setup (AWS CLI) 🚀

If your Lambda function already exists:

```bash
cd /Users/personal/Documents/git-repos/BLCKWorldCup
export AWS_DEFAULT_REGION=us-east-1

# Run the setup script (default: 2 AM UTC daily)
./scrapers/setup_daily_schedule.sh

# Or specify a custom time (24-hour format)
./scrapers/setup_daily_schedule.sh 14:30  # Runs at 2:30 PM UTC daily
```

That's it! The script will:
1. ✅ Check if Lambda function exists
2. ✅ Create/update EventBridge rule
3. ✅ Add Lambda permissions
4. ✅ Connect EventBridge to Lambda

---

## Option 2: Manual Setup (AWS Console) 🖥️

### Step 1: Create EventBridge Rule

1. Go to **EventBridge** → **Rules** → **Create rule**
   - https://console.aws.amazon.com/events/

2. **Define rule detail:**
   - **Name**: `wc-qualifiers-current-standings-daily-schedule`
   - **Description**: `Daily schedule for World Cup qualifiers scraper`
   - **Event bus**: `default`
   - **Rule type**: **Schedule**

3. **Schedule pattern:**
   - Select **Schedule**
   - Choose **Recurring schedule**
   - **Schedule type**: **Cron-based schedule**
   - **Cron expression**: `0 2 * * ? *` (runs daily at 2 AM UTC)
     - To change time, use format: `MINUTE HOUR * * ? *`
     - Examples:
       - `0 2 * * ? *` = 2:00 AM UTC daily
       - `0 14 * * ? *` = 2:00 PM UTC daily
       - `30 8 * * ? *` = 8:30 AM UTC daily

4. Click **Next**

### Step 2: Select Target

1. **Target types**: Select **AWS service**
2. **Select a target**: Choose **Lambda function**
3. **Function**: Select `wc-qualifiers-current-standings`
4. Click **Next**

### Step 3: Configure Tags (Optional)

- Skip or add tags
- Click **Next**

### Step 4: Review and Create

1. Review your settings
2. Click **Create rule**

### Step 5: Verify Permissions

EventBridge should automatically add permissions to your Lambda function. To verify:

1. Go to **Lambda** → `wc-qualifiers-current-standings`
2. **Configuration** → **Permissions**
3. Check that there's a policy allowing `events.amazonaws.com` to invoke the function

If it's missing, you can add it manually (see Step 6 below).

---

## Option 3: Manual Setup (AWS CLI) 💻

### Step 1: Create EventBridge Rule

```bash
export AWS_DEFAULT_REGION=us-east-1

# Create rule (runs daily at 2 AM UTC)
aws events put-rule \
  --name wc-qualifiers-current-standings-daily-schedule \
  --schedule-expression "cron(0 2 * * ? *)" \
  --state ENABLED \
  --description "Daily schedule for World Cup qualifiers scraper at 2 AM UTC" \
  --region us-east-1
```

**To change the time**, modify the cron expression:
- `cron(0 2 * * ? *)` = 2:00 AM UTC
- `cron(0 14 * * ? *)` = 2:00 PM UTC  
- `cron(30 8 * * ? *)` = 8:30 AM UTC

### Step 2: Add Lambda Permission

```bash
# Get your account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Add permission for EventBridge to invoke Lambda
aws lambda add-permission \
  --function-name wc-qualifiers-current-standings \
  --statement-id "allow-eventbridge-daily-$(date +%s)" \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "arn:aws:events:us-east-1:$ACCOUNT_ID:rule/wc-qualifiers-current-standings-daily-schedule" \
  --region us-east-1
```

### Step 3: Add Lambda as Target

```bash
# Get your account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Add Lambda as target
aws events put-targets \
  --rule wc-qualifiers-current-standings-daily-schedule \
  --targets "Id=1,Arn=arn:aws:lambda:us-east-1:$ACCOUNT_ID:function:wc-qualifiers-current-standings" \
  --region us-east-1
```

---

## Verify It's Working

### Check Rule Status

**Via Console:**
- EventBridge → Rules → `wc-qualifiers-current-standings-daily-schedule`
- Status should be **Enabled**

**Via CLI:**
```bash
aws events describe-rule \
  --name wc-qualifiers-current-standings-daily-schedule \
  --region us-east-1
```

### Test Manually

Trigger the Lambda manually to test:

```bash
aws lambda invoke \
  --function-name wc-qualifiers-current-standings \
  --payload '{}' \
  --region us-east-1 \
  response.json && cat response.json
```

### View Logs

**Via Console:**
- Lambda → `wc-qualifiers-current-standings` → **Monitor** → **Logs**

**Via CLI:**
```bash
aws logs tail /aws/lambda/wc-qualifiers-current-standings --follow --region us-east-1
```

### Wait for Next Run

The function will run automatically at the scheduled time. You can check CloudWatch Logs the next day to see the execution.

---

## Managing the Schedule

### Disable the Schedule

**Via Console:**
- EventBridge → Rules → Select rule → **Disable**

**Via CLI:**
```bash
aws events disable-rule \
  --name wc-qualifiers-current-standings-daily-schedule \
  --region us-east-1
```

### Enable the Schedule

```bash
aws events enable-rule \
  --name wc-qualifiers-current-standings-daily-schedule \
  --region us-east-1
```

### Change the Time

**Via Console:**
- EventBridge → Rules → Select rule → **Edit** → Update cron expression

**Via CLI:**
```bash
# Change to 8:30 AM UTC
aws events put-rule \
  --name wc-qualifiers-current-standings-daily-schedule \
  --schedule-expression "cron(30 8 * * ? *)" \
  --state ENABLED \
  --region us-east-1
```

Or just run the setup script again:
```bash
./scrapers/setup_daily_schedule.sh 08:30
```

### Delete the Schedule

**Via Console:**
- EventBridge → Rules → Select rule → **Delete**

**Via CLI:**
```bash
aws events delete-rule \
  --name wc-qualifiers-current-standings-daily-schedule \
  --region us-east-1
```

---

## Cron Expression Reference

Format: `cron(MINUTE HOUR DAY MONTH DAY-OF-WEEK YEAR)`

- `MINUTE`: 0-59
- `HOUR`: 0-23 (UTC)
- `DAY`: 1-31 (use `?` for day-of-week)
- `MONTH`: 1-12 or JAN-DEC
- `DAY-OF-WEEK`: 1-7 or SUN-SAT (use `?` for day)
- `YEAR`: 1970-2199 (use `*` for any)

**Common patterns:**
- `cron(0 2 * * ? *)` = Daily at 2:00 AM UTC
- `cron(0 */6 * * ? *)` = Every 6 hours
- `cron(0 0 * * ? *)` = Daily at midnight UTC
- `cron(0 12 ? * MON *)` = Every Monday at noon UTC

---

## Troubleshooting

### "Function not found" error

Make sure your Lambda function exists:
```bash
aws lambda get-function --function-name wc-qualifiers-current-standings --region us-east-1
```

If it doesn't exist, create it first (see `S3_SETUP_INSTRUCTIONS.md`).

### "Access denied" error

Check that your IAM user/role has permissions for:
- `events:PutRule`
- `events:PutTargets`
- `lambda:AddPermission`
- `lambda:GetFunction`

### Lambda not executing

1. Check rule is **Enabled** (not Disabled)
2. Check Lambda function is active
3. Check CloudWatch Logs for errors
4. Verify EventBridge has permission to invoke Lambda (Lambda → Configuration → Permissions)

---

## Next Steps

After setting up the daily schedule:

1. ✅ Set up S3 environment variable (see `S3_SETUP_INSTRUCTIONS.md`)
2. ✅ Add S3 read permissions to Lambda role
3. ✅ Test the function manually
4. ✅ Wait for the first scheduled run and check logs

Your Lambda will now run automatically every day! 🎉


