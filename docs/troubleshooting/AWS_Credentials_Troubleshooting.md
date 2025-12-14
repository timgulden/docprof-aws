# AWS Credentials Troubleshooting Guide

## Quick Diagnosis

### 1. Check if AWS CLI is configured
```bash
aws sts get-caller-identity
```

**Expected output:**
```json
{
    "UserId": "AIDA...",
    "Account": "176520790264",
    "Arn": "arn:aws:iam::176520790264:user/..."
}
```

**If this fails:** AWS CLI is not configured or credentials are missing.

---

### 2. Check AWS Profile Configuration

This project uses the **`docprof-dev`** AWS profile.

#### Check if profile exists:
```bash
cat ~/.aws/credentials | grep -A 3 "\[docprof-dev\]"
```

#### Check profile configuration:
```bash
cat ~/.aws/config | grep -A 5 "\[profile docprof-dev\]"
```

**Expected `~/.aws/credentials`:**
```ini
[docprof-dev]
aws_access_key_id = AKIA...
aws_secret_access_key = ...
```

**Expected `~/.aws/config`:**
```ini
[profile docprof-dev]
region = us-east-1
output = json
```

---

### 3. Test Profile Access

```bash
# Set profile explicitly
export AWS_PROFILE=docprof-dev

# Verify it works
aws sts get-caller-identity

# Test Terraform can access AWS
cd terraform/environments/dev
terraform init
terraform plan
```

---

## Common Issues & Solutions

### Issue 1: "Unable to locate credentials"

**Symptoms:**
```
Error: Unable to locate credentials
```

**Solutions:**

1. **Set AWS_PROFILE environment variable:**
   ```bash
   export AWS_PROFILE=docprof-dev
   ```

2. **Or use in command:**
   ```bash
   AWS_PROFILE=docprof-dev terraform plan
   ```

3. **Check if profile exists:**
   ```bash
   aws configure list-profiles
   ```

4. **If profile doesn't exist, create it:**
   ```bash
   aws configure --profile docprof-dev
   ```
   Then enter:
   - AWS Access Key ID
   - AWS Secret Access Key
   - Default region: `us-east-1`
   - Default output format: `json`

---

### Issue 2: "Access Denied" or "Unauthorized"

**Symptoms:**
```
Error: AccessDenied: User: arn:aws:iam::... is not authorized to perform: ...
```

**Solutions:**

1. **Verify credentials are correct:**
   ```bash
   AWS_PROFILE=docprof-dev aws sts get-caller-identity
   ```

2. **Check IAM permissions:**
   - User/role needs permissions for Terraform operations
   - Common required permissions:
     - `ec2:*` (for VPC, subnets, security groups)
     - `rds:*` (for Aurora)
     - `lambda:*` (for Lambda functions)
     - `iam:*` (for roles and policies)
     - `s3:*` (for buckets)
     - `logs:*` (for CloudWatch)
     - `bedrock:*` (for Bedrock models)
     - `secretsmanager:*` (for Secrets Manager)

3. **Verify account ID matches:**
   ```bash
   AWS_PROFILE=docprof-dev aws sts get-caller-identity
   ```
   Should show account: `176520790264`

---

### Issue 3: "InvalidClientTokenId"

**Symptoms:**
```
Error: InvalidClientTokenId: The security token included in the request is invalid.
```

**Solutions:**

1. **Credentials are expired or incorrect:**
   ```bash
   # Re-configure the profile
   aws configure --profile docprof-dev
   ```

2. **Check for typos in credentials file:**
   ```bash
   cat ~/.aws/credentials
   ```

3. **If using temporary credentials (SSO), refresh:**
   ```bash
   aws sso login --profile docprof-dev
   ```

---

### Issue 4: Terraform can't find credentials

**Symptoms:**
```
Error: No valid credential sources found
```

**Solutions:**

1. **Terraform uses AWS SDK credential chain:**
   - Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
   - AWS credentials file (`~/.aws/credentials`)
   - AWS config file (`~/.aws/config`)
   - IAM roles (if running on EC2/ECS/Lambda)

2. **Set profile for Terraform:**
   ```bash
   export AWS_PROFILE=docprof-dev
   cd terraform/environments/dev
   terraform init
   terraform plan
   ```

3. **Or use the wrapper script:**
   ```bash
   ./scripts/terraform.sh plan
   ```

---

### Issue 5: Wrong Region

**Symptoms:**
```
Error: InvalidParameterValue: The parameter is not valid
```

**Solutions:**

1. **Check configured region:**
   ```bash
   AWS_PROFILE=docprof-dev aws configure get region
   ```
   Should be: `us-east-1`

2. **Set region explicitly:**
   ```bash
   export AWS_DEFAULT_REGION=us-east-1
   # or
   export AWS_REGION=us-east-1
   ```

3. **Update profile config:**
   ```bash
   aws configure set region us-east-1 --profile docprof-dev
   ```

---

## Verification Checklist

Run these commands to verify everything is set up correctly:

```bash
# 1. Check AWS CLI is installed
aws --version

# 2. List available profiles
aws configure list-profiles

# 3. Check current profile (if set)
echo $AWS_PROFILE

# 4. Test profile access
AWS_PROFILE=docprof-dev aws sts get-caller-identity

# 5. Check region
AWS_PROFILE=docprof-dev aws configure get region

# 6. Test Terraform access
cd terraform/environments/dev
AWS_PROFILE=docprof-dev terraform init
AWS_PROFILE=docprof-dev terraform plan
```

---

## Project-Specific Configuration

### This Project Uses:
- **Profile Name:** `docprof-dev`
- **Region:** `us-east-1`
- **Account ID:** `176520790264`

### Scripts That Use AWS_PROFILE:
- `scripts/upload_book.sh` - Uses `AWS_PROFILE=docprof-dev`
- `scripts/terraform.sh` - Sets `AWS_PROFILE=docprof-dev`
- `scripts/enable-ai-services.sh` - Uses `AWS_PROFILE=docprof-dev`
- `scripts/disable-ai-services.sh` - Uses `AWS_PROFILE=docprof-dev`

### Terraform Configuration:
- Terraform provider doesn't explicitly set profile
- Relies on AWS SDK default credential chain
- **Recommendation:** Always set `AWS_PROFILE=docprof-dev` before running Terraform

---

## Quick Fix Commands

### If nothing works, try this sequence:

```bash
# 1. Set profile
export AWS_PROFILE=docprof-dev

# 2. Verify credentials
aws sts get-caller-identity

# 3. Set region
export AWS_DEFAULT_REGION=us-east-1

# 4. Test Terraform
cd terraform/environments/dev
terraform init
terraform plan
```

---

## Additional Resources

- [AWS CLI Configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- [Terraform AWS Provider Authentication](https://registry.terraform.io/providers/hashicorp/aws/latest/docs#authentication)
- [AWS Credential Chain](https://docs.aws.amazon.com/sdk-for-go/v1/developer-guide/configuring-sdk.html#specifying-credentials)

---

**Last Updated:** December 11, 2025



