# Deployment Guide - Step by Step

## Prerequisites

### 1. AWS Credentials Setup

You need AWS credentials configured. This project uses the `docprof-dev` profile.

**Option A: If you already have AWS credentials:**
```bash
# Check if profile exists
cat ~/.aws/credentials | grep -A 3 "\[docprof-dev\]"

# If it exists, set it as default for this session
export AWS_PROFILE=docprof-dev

# Verify it works
aws sts get-caller-identity
```

**Option B: If you need to configure credentials:**
```bash
# Configure AWS CLI with your credentials
aws configure --profile docprof-dev

# You'll be prompted for:
# - AWS Access Key ID
# - AWS Secret Access Key  
# - Default region: us-east-1
# - Default output format: json

# Set profile for this session
export AWS_PROFILE=docprof-dev

# Verify it works
aws sts get-caller-identity
```

### 2. Terraform Installed
```bash
terraform version
# Should show version >= 1.5.0
```

### 3. Node.js and npm Installed
```bash
node --version  # Should be >= 18
npm --version
```

## Step 1: Deploy Infrastructure

```bash
# Navigate to Terraform directory
cd terraform/environments/dev

# Initialize Terraform (if not already done)
terraform init

# Review what will be created
terraform plan

# Apply changes (creates Cognito, updates API Gateway)
terraform apply

# Type 'yes' when prompted
```

**Expected output:**
- Cognito User Pool created
- Cognito User Pool Client created
- Cognito User Pool Domain created
- API Gateway updated with Cognito authorizer
- All endpoints now require authentication

## Step 2: Get Configuration Values

After deployment, get the values needed for the frontend:

```bash
# Get Cognito User Pool ID
terraform output cognito_user_pool_id

# Get Cognito Client ID
terraform output cognito_user_pool_client_id

# Get API Gateway URL
terraform output api_gateway_url

# Get Cognito Domain (optional, for hosted UI)
terraform output cognito_domain
```

**Example output:**
```
cognito_user_pool_id = "us-east-1_ABC123XYZ"
cognito_user_pool_client_id = "1a2b3c4d5e6f7g8h9i0j"
api_gateway_url = "https://abc123xyz.execute-api.us-east-1.amazonaws.com/dev"
```

## Step 3: Configure Frontend

```bash
# Navigate to frontend directory
cd ../../../src/frontend

# Create .env file
cat > .env << EOF
VITE_COGNITO_USER_POOL_ID=<paste-user-pool-id-here>
VITE_COGNITO_USER_POOL_CLIENT_ID=<paste-client-id-here>
VITE_API_GATEWAY_URL=<paste-api-gateway-url-here>
VITE_AWS_REGION=us-east-1
EOF

# Edit .env file with actual values from Step 2
# Or use your preferred editor:
# nano .env
# or
# code .env
```

## Step 4: Install Frontend Dependencies

```bash
# Make sure you're in src/frontend directory
cd src/frontend

# Install dependencies
npm install

# This will install:
# - React and React DOM
# - AWS Amplify
# - All other dependencies
```

## Step 5: Start Development Server

```bash
# Start Vite dev server
npm run dev

# You should see:
# VITE v7.x.x  ready in xxx ms
# ➜  Local:   http://localhost:5173/
# ➜  Network: use --host to expose
```

## Step 6: Open in Browser

1. Open your browser
2. Navigate to `http://localhost:5173`
3. You should see the **Login** page
4. Click "Register" to create a new account
5. Enter email and password
6. After registration/login, you'll see the main interface!

## Troubleshooting

### "No valid credential sources found"
- Make sure AWS credentials are configured
- Set `export AWS_PROFILE=docprof-dev`
- Verify with `aws sts get-caller-identity`

### "VITE_COGNITO_USER_POOL_ID is not set"
- Check that `.env` file exists in `src/frontend/`
- Verify all variables start with `VITE_`
- Restart dev server after changing `.env`

### "Network error" when calling API
- Verify API Gateway URL is correct
- Check that Cognito is deployed
- Verify API Gateway has Cognito authorizer configured
- Check browser console for CORS errors

### Can't login after registration
- Check if email verification is required
- In dev, Cognito can be configured to auto-confirm emails
- Check CloudWatch logs for Lambda errors

## Next Steps After Deployment

1. ✅ Test login/registration
2. ✅ Test chat functionality
3. ✅ Test book upload
4. ✅ Test course generation (with polling)
5. ✅ Deploy frontend to S3 + CloudFront (optional)

## Cost Estimate

**Cognito:**
- Free tier: 50,000 MAU (Monthly Active Users)
- After free tier: $0.0055 per MAU
- For dev/testing: Effectively free

**API Gateway:**
- Free tier: 1M requests/month
- After free tier: $3.50 per million requests
- For dev/testing: Effectively free

**Total additional cost for Cognito + API Gateway auth: ~$0/month for dev**

