# VPC Endpoints Implementation Guide - On-Demand Architecture

**Version:** 2.0  
**Date:** December 10, 2025  
**Purpose:** Implement on-demand VPC endpoints for cost-efficient AI services

---

## Executive Summary

This guide implements an **on-demand VPC endpoint architecture** where AI services (Bedrock and Polly) can be enabled/disabled via simple scripts. This approach allows:
- Full production architecture when enabled (~$0.04/hour)
- Zero networking costs when disabled
- Complete system functionality for all users when online
- Manual cost control via enable/disable scripts

**Key Innovation:** Infrastructure remains deployed in AWS, but VPC endpoints are created/destroyed on-demand to control costs while maintaining production-grade security patterns.

---

## Problem Statement

The initial VPC design included a NAT Gateway to allow Lambda functions in private subnets to access external services. However:

**NAT Gateway costs:**
- $0.045 per hour = ~$32.40/month (always running)
- $0.045 per GB data processed
- **Total: ~$35-40/month minimum, even when system is idle**

**VPC Endpoints costs (initial estimate):**
- Interface endpoints: $0.01 per hour per endpoint per AZ
- 2 endpoints × 2 AZs = 4 endpoint-hours per hour
- 4 × $0.01 × 730 hours/month = **~$29/month always running**

**The Real Problem:** Both approaches cost $30-40/month for 24/7 availability, but DocProf is a learning/demo project that may only be used 10-20 hours per month.

## Solution: On-Demand VPC Endpoints

Instead of choosing between NAT Gateway (expensive) or VPC endpoints (expensive), we implement **conditional VPC endpoints** that can be enabled/disabled on-demand:

**When ENABLED (your choice):**
- VPC endpoints created via Terraform
- Lambda can call Bedrock/Polly
- System fully functional for all users
- Cost: ~$0.04/hour while running

**When DISABLED (default):**
- VPC endpoints destroyed via Terraform
- Lambda cannot call AI services
- Base infrastructure remains (VPC, Aurora, S3, etc.)
- Cost: ~$0/hour for networking

**Monthly cost examples:**
- Use 10 hours/month: 10 × $0.04 = **$0.40/month**
- Use 20 hours/month: 20 × $0.04 = **$0.80/month**
- Use 50 hours/month: 50 × $0.04 = **$2.00/month**
- Use 100 hours/month: 100 × $0.04 = **$4.00/month**

**Compared to always-on:**
- NAT Gateway: $32/month (whether you use it or not)
- VPC Endpoints: $29/month (whether you use it or not)
- On-demand: $0.40-4.00/month (only pay for usage)

**Savings:** 85-98% cost reduction for intermittent usage

---

## How On-Demand Works

### Control Flow

```
Developer Laptop              AWS Cloud                All Users
────────────────              ─────────                ──────────

./enable-ai-services.sh  →  [Terraform Apply]
                             Creates VPC Endpoints
                             ↓
                        VPC Endpoints = ONLINE
                             ↓
                        Lambda can call Bedrock/Polly
                             ↓
                        API Gateway accepts requests
                             ↓
Anyone can use system   ←   System Fully Operational   ← Anyone
(costs accumulating)         
                             
[2-3 hours later]

./disable-ai-services.sh →  [Terraform Apply]
                             Destroys VPC Endpoints
                             ↓
                        VPC Endpoints = OFFLINE
                             ↓
                        Lambda cannot call AI services
                             ↓
System shows "offline"  ←   AI Features Disabled        ← Anyone
(costs stopped)
```

### Key Concepts

**1. Infrastructure vs. Endpoints**
- **Base infrastructure** (VPC, subnets, security groups, Lambda functions, Aurora): Always deployed
- **VPC endpoints** (Bedrock, Polly): Created/destroyed on-demand
- **Application** (React frontend, API Gateway): Always available

**2. Multi-User Access**
- When you enable endpoints, **everyone** can use the system
- Your laptop doesn't need to be online for others to use it
- You control when costs start/stop, not who can access
- Access control is separate (via Cognito authentication)

**3. State Management**
- Terraform tracks endpoint state
- Frontend checks endpoint existence via API
- Shows "ONLINE" or "OFFLINE" status to users
- Simple enable/disable scripts control state

---

## What Are VPC Endpoints?

VPC endpoints allow AWS services (Lambda, EC2, etc.) to access other AWS services **without traversing the public internet**. There are two types:

**1. Gateway Endpoints (Free):**
- For S3 and DynamoDB only
- Traffic stays within AWS network
- No hourly charges
- Already included in our VPC design

**2. Interface Endpoints (Paid):**
- For all other AWS services (Bedrock, Polly, etc.)
- Create ENI (Elastic Network Interface) in your VPC
- Charged per hour per endpoint
- More cost-effective than NAT Gateway for AWS service access

### Why VPC Endpoints Instead of NAT Gateway?

| Aspect | NAT Gateway | VPC Endpoints |
|--------|-------------|---------------|
| **Cost** | $32/month + data | $7/month per endpoint |
| **Use Case** | General internet access | AWS service access only |
| **Our Needs** | Bedrock + Polly only | Bedrock + Polly only |
| **Data Charges** | $0.045/GB | Included in hourly rate |
| **Performance** | Good | Better (stays in AWS network) |
| **Security** | Internet traversal | Private AWS network only |
| **Management** | Fully managed | Fully managed |

**For DocProf, we only need to access:**
1. Bedrock (Claude for LLM, Titan for embeddings)
2. Polly (text-to-speech)
3. S3 (already free via Gateway Endpoint)
4. Aurora (same VPC, no internet needed)
5. DynamoDB (already free via Gateway Endpoint)

**Cost calculation:**
- Bedrock endpoint: $7.00/month
- Polly endpoint: $7.00/month
- **Total: $14/month vs. $32/month NAT Gateway**
- **Savings: $18/month (56% reduction)**

### Additional Benefits

**1. Better Security**
- Traffic never leaves AWS network
- No exposure to internet threats
- Ideal for government/compliance use cases

**2. Better Performance**
- Lower latency (private AWS network)
- No internet routing overhead
- More consistent performance

**3. Simpler Architecture**
- No NAT Gateway to monitor
- No Elastic IP to manage
- Fewer moving parts

**4. Scalability**
- Endpoints scale automatically
- No bandwidth limits
- No single point of failure

---

## Architecture Changes

### Before (NAT Gateway - Always On)

```
Internet
    ↓
[Internet Gateway]
    ↓
[Public Subnet] ← User requests
    ↓
[NAT Gateway] ($32/month always)
    ↓
[Private Subnet]
    ↓
[Lambda] → (via NAT) → Internet → Bedrock/Polly
```

**Problems:**
- $32/month even when idle
- Internet traversal = latency + security risk

### After (On-Demand VPC Endpoints)

**State 1: DISABLED (Default)**
```
Internet
    ↓
[Internet Gateway]
    ↓
[Public Subnet] ← User requests via API Gateway
    ↓
[Private Subnet]
    ↓
[Lambda] → ✗ No VPC Endpoints → Cannot call Bedrock/Polly
           (Cost: $0/hour)
           
API returns: "AI services offline, contact admin"
```

**State 2: ENABLED (On-Demand)**
```
Internet
    ↓
[Internet Gateway]
    ↓
[Public Subnet] ← User requests via API Gateway
    ↓
[Private Subnet]
    ↓
[Lambda] → [VPC Endpoints] → Bedrock/Polly (private AWS network)
           (Cost: ~$0.04/hour)
           
System fully operational for all users
```

**Benefits:**
- Pay only for hours used
- Production architecture when enabled
- Simple enable/disable control
- Multi-user access when online

---

## Implementation Plan

### Step 1: Add Conditional Variable

**File:** `terraform/modules/vpc/variables.tf`

**Add this variable:**

```hcl
variable "enable_ai_endpoints" {
  description = "Enable VPC endpoints for Bedrock and Polly (costs ~$0.04/hour when enabled)"
  type        = bool
  default     = false  # Default to disabled
}
```

This variable controls whether VPC endpoints are created or destroyed.

### Step 2: Remove NAT Gateway (Not Needed)

**File:** `terraform/modules/vpc/main.tf`

**Remove or comment out these resources:**

```hcl
# Remove this block
# resource "aws_eip" "nat" {
#   domain = "vpc"
#   
#   tags = {
#     Name = "docprof-nat-eip"
#   }
# }

# Remove this block
# resource "aws_nat_gateway" "main" {
#   allocation_id = aws_eip.nat.id
#   subnet_id     = aws_subnet.public[0].id
#   
#   tags = {
#     Name = "docprof-nat-gateway"
#   }
#   
#   depends_on = [aws_internet_gateway.main]
# }
```

**Update private route table (remove NAT route):**

```hcl
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  
  # Remove this route block:
  # route {
  #   cidr_block     = "0.0.0.0/0"
  #   nat_gateway_id = aws_nat_gateway.main.id
  # }
  
  tags = {
    Name        = "${var.project_name}-private-rt"
    Environment = var.environment
  }
}

# Keep route table associations as-is
resource "aws_route_table_association" "private" {
  count          = length(var.private_subnet_cidrs)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}
```

**Create new file:** `terraform/modules/vpc/endpoints.tf`

```hcl
# Security group for VPC endpoints
resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.project_name}-vpc-endpoints-"
  description = "Security group for VPC endpoints"
  vpc_id      = aws_vpc.main.id
  
  # Allow inbound HTTPS from Lambda security group
  ingress {
    description     = "HTTPS from Lambda"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }
  
  # Allow outbound (required for endpoint functionality)
  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name        = "${var.project_name}-vpc-endpoints-sg"
    Environment = var.environment
  }
  
  lifecycle {
    create_before_destroy = true
  }
}

# VPC Endpoint for Bedrock Runtime
resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  
  # Enable private DNS so Lambda can use standard Bedrock endpoint
  private_dns_enabled = true
  
  tags = {
    Name        = "${var.project_name}-bedrock-runtime-endpoint"
    Environment = var.environment
    Service     = "bedrock-runtime"
  }
}

# VPC Endpoint for Polly
resource "aws_vpc_endpoint" "polly" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.polly"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  
  # Enable private DNS so Lambda can use standard Polly endpoint
  private_dns_enabled = true
  
  tags = {
    Name        = "${var.project_name}-polly-endpoint"
    Environment = var.environment
    Service     = "polly"
  }
}

# S3 Gateway Endpoint (already included, but shown here for completeness)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
  
  tags = {
    Name        = "${var.project_name}-s3-endpoint"
    Environment = var.environment
    Service     = "s3"
  }
}

# DynamoDB Gateway Endpoint (free, for session storage)
resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
  
  tags = {
    Name        = "${var.project_name}-dynamodb-endpoint"
    Environment = var.environment
    Service     = "dynamodb"
  }
}
```

### Step 3: Add Conditional VPC Endpoints

**Create new file:** `terraform/modules/vpc/endpoints.tf`

**Key pattern: Use `count` with conditional to create/destroy resources**

```hcl
# Security group for VPC endpoints (always created)
resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.project_name}-vpc-endpoints-"
  description = "Security group for VPC endpoints"
  vpc_id      = aws_vpc.main.id
  
  # Allow inbound HTTPS from Lambda security group
  ingress {
    description     = "HTTPS from Lambda"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }
  
  # Allow outbound (required for endpoint functionality)
  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name        = "${var.project_name}-vpc-endpoints-sg"
    Environment = var.environment
  }
  
  lifecycle {
    create_before_destroy = true
  }
}

# VPC Endpoint for Bedrock Runtime - CONDITIONAL
# count = 0 means resource doesn't exist
# count = 1 means resource is created
resource "aws_vpc_endpoint" "bedrock_runtime" {
  count = var.enable_ai_endpoints ? 1 : 0
  
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  
  # Enable private DNS so Lambda can use standard Bedrock endpoint
  private_dns_enabled = true
  
  tags = {
    Name        = "${var.project_name}-bedrock-runtime-endpoint"
    Environment = var.environment
    Service     = "bedrock-runtime"
    OnDemand    = "true"
  }
}

# VPC Endpoint for Polly - CONDITIONAL
resource "aws_vpc_endpoint" "polly" {
  count = var.enable_ai_endpoints ? 1 : 0
  
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.polly"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  
  # Enable private DNS so Lambda can use standard Polly endpoint
  private_dns_enabled = true
  
  tags = {
    Name        = "${var.project_name}-polly-endpoint"
    Environment = var.environment
    Service     = "polly"
    OnDemand    = "true"
  }
}

# S3 Gateway Endpoint - ALWAYS ON (FREE)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
  
  tags = {
    Name        = "${var.project_name}-s3-endpoint"
    Environment = var.environment
    Service     = "s3"
  }
}

# DynamoDB Gateway Endpoint - ALWAYS ON (FREE)
resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]
  
  tags = {
    Name        = "${var.project_name}-dynamodb-endpoint"
    Environment = var.environment
    Service     = "dynamodb"
  }
}
```

**Important:** The `count` parameter makes resources conditional:
- `count = 1`: Resource is created
- `count = 0`: Resource doesn't exist (or is destroyed if it existed)
- When `var.enable_ai_endpoints` changes, Terraform creates or destroys the endpoints

### Step 4: Update VPC Module Interface

**File:** `terraform/environments/dev/main.tf`

**Pass the variable to the VPC module:**

```hcl
module "vpc" {
  source = "../../modules/vpc"
  
  project_name    = var.project_name
  environment     = var.environment
  aws_region      = var.aws_region
  
  # This variable controls whether AI endpoints are created
  enable_ai_endpoints = var.enable_ai_endpoints
  
  # ... other vpc config
}
```

**File:** `terraform/environments/dev/variables.tf`

**Add the variable:**

```hcl
variable "enable_ai_endpoints" {
  description = "Enable VPC endpoints for AI services (Bedrock, Polly)"
  type        = bool
  default     = false
}
```

**File:** `terraform/environments/dev/terraform.tfvars`

**Set default value:**

```hcl
# Default to disabled (save costs)
enable_ai_endpoints = false
```

### Step 5: Update VPC Outputs

**File:** `terraform/modules/vpc/outputs.tf`

**Add these outputs (note conditional access for on-demand endpoints):**

```hcl
# Existing outputs...

# Conditional endpoint outputs (use try() to handle when count = 0)
output "bedrock_endpoint_id" {
  description = "ID of Bedrock VPC endpoint (if enabled)"
  value       = try(aws_vpc_endpoint.bedrock_runtime[0].id, null)
}

output "polly_endpoint_id" {
  description = "ID of Polly VPC endpoint (if enabled)"
  value       = try(aws_vpc_endpoint.polly[0].id, null)
}

output "s3_endpoint_id" {
  description = "ID of S3 VPC endpoint"
  value       = aws_vpc_endpoint.s3.id
}

output "dynamodb_endpoint_id" {
  description = "ID of DynamoDB VPC endpoint"
  value       = aws_vpc_endpoint.dynamodb.id
}

output "vpc_endpoints_sg_id" {
  description = "Security group ID for VPC endpoints"
  value       = aws_security_group.vpc_endpoints.id
}

output "ai_endpoints_enabled" {
  description = "Whether AI endpoints are currently enabled"
  value       = var.enable_ai_endpoints
}
```

**Important:** Use `[0]` to access the first element when `count = 1`, and `try()` to return `null` when `count = 0`.

### Step 6: Update Lambda Security Group

**File:** `terraform/modules/vpc/security_groups.tf`

**Update Lambda security group to allow outbound to VPC endpoints:**

```hcl
resource "aws_security_group" "lambda" {
  name_prefix = "${var.project_name}-lambda-"
  description = "Security group for Lambda functions"
  vpc_id      = aws_vpc.main.id
  
  # Allow outbound to Aurora
  egress {
    description     = "PostgreSQL to Aurora"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.aurora.id]
  }
  
  # Allow outbound HTTPS to VPC endpoints
  egress {
    description     = "HTTPS to VPC endpoints"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.vpc_endpoints.id]
  }
  
  # Allow outbound HTTPS (for downloading packages during deployment)
  # Note: This will fail without NAT Gateway or VPC endpoint
  # For package downloads, consider Lambda layers or container images
  egress {
    description = "HTTPS for general access"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name        = "${var.project_name}-lambda-sg"
    Environment = var.environment
  }
  
  lifecycle {
    create_before_destroy = true
  }
}
```

**Note on the last egress rule:** Lambda functions in private subnets without NAT Gateway cannot reach the internet. This means:
- ✓ Can access AWS services via VPC endpoints
- ✓ Can access Aurora in same VPC
- ✗ Cannot download packages from PyPI during deployment
- **Solution:** Use Lambda layers or pre-built deployment packages

### Step 5: Verify Variables

**File:** `terraform/modules/vpc/variables.tf`

**Ensure these variables exist:**

```hcl
variable "aws_region" {
  description = "AWS region for VPC endpoints"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "availability_zones" {
  description = "Availability zones for subnets"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}
```

---

## Control Scripts

These scripts enable/disable AI services on-demand by changing the Terraform variable and applying changes.

### Enable AI Services Script

**File:** `scripts/enable-ai-services.sh`

```bash
#!/bin/bash
set -e

echo "🚀 Enabling AI services (Bedrock + Polly VPC endpoints)..."
echo "This will take ~3-5 minutes and cost ~$0.04/hour while running."
echo ""

cd terraform/environments/dev

# Enable AI endpoints
terraform apply \
  -var="enable_ai_endpoints=true" \
  -auto-approve

echo ""
echo "✅ AI services are now ONLINE"
echo "💡 Remember to disable when done to save costs"
echo "   Run: ./scripts/disable-ai-services.sh"
```

**Make executable:**
```bash
chmod +x scripts/enable-ai-services.sh
```

### Disable AI Services Script

**File:** `scripts/disable-ai-services.sh`

```bash
#!/bin/bash
set -e

echo "🛑 Disabling AI services..."
echo ""

cd terraform/environments/dev

# Disable AI endpoints
terraform apply \
  -var="enable_ai_endpoints=false" \
  -auto-approve

echo ""
echo "✅ AI services are now OFFLINE"
echo "💰 No longer incurring hourly charges"
```

**Make executable:**
```bash
chmod +x scripts/disable-ai-services.sh
```

### Check Status Script

**File:** `scripts/check-ai-status.sh`

```bash
#!/bin/bash

echo "Checking AI services status..."
echo ""

cd terraform/environments/dev

# Check current state
ENABLED=$(terraform output -raw ai_endpoints_enabled 2>/dev/null || echo "unknown")

if [ "$ENABLED" = "true" ]; then
    echo "● AI Services: ONLINE"
    echo "💰 Costing ~$0.04/hour"
    echo ""
    echo "To disable: ./scripts/disable-ai-services.sh"
elif [ "$ENABLED" = "false" ]; then
    echo "○ AI Services: OFFLINE"
    echo "💰 No hourly charges"
    echo ""
    echo "To enable: ./scripts/enable-ai-services.sh"
else
    echo "⚠️  Status: UNKNOWN (infrastructure may not be deployed)"
fi
```

**Make executable:**
```bash
chmod +x scripts/check-ai-status.sh
```

### Usage

**Before using DocProf:**
```bash
./scripts/enable-ai-services.sh
# Wait 3-5 minutes
# Use DocProf for your session
```

**Check status anytime:**
```bash
./scripts/check-ai-status.sh
```

**When done for the day:**
```bash
./scripts/disable-ai-services.sh
# Wait 1-2 minutes
# Costs stop accumulating
```

### How It Works

1. **Enable script**:
   - Runs `terraform apply` with `enable_ai_endpoints=true`
   - Terraform creates VPC endpoints (count changes from 0 to 1)
   - Takes 3-5 minutes
   - Costs start: ~$0.04/hour

2. **Disable script**:
   - Runs `terraform apply` with `enable_ai_endpoints=false`
   - Terraform destroys VPC endpoints (count changes from 1 to 0)
   - Takes 1-2 minutes
   - Costs stop

3. **System behavior**:
   - Base infrastructure stays deployed (VPC, Lambda, Aurora, etc.)
   - When endpoints exist: Lambda can call Bedrock/Polly
   - When endpoints don't exist: Lambda calls fail gracefully
   - Frontend shows status to users

---

## Testing and Validation

### After Deployment

**1. Verify VPC Endpoints Created:**
```bash
# Run terraform and check output
terraform apply

# Should show endpoints created
aws ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values=<your-vpc-id>" \
  --query 'VpcEndpoints[*].[ServiceName,State,VpcEndpointType]' \
  --output table
```

**Expected output:**
```
-----------------------------------------------------------------
|                   DescribeVpcEndpoints                       |
+----------------------------------------------+--------+-------+
| com.amazonaws.us-east-1.bedrock-runtime     | available | Interface |
| com.amazonaws.us-east-1.polly               | available | Interface |
| com.amazonaws.us-east-1.s3                  | available | Gateway   |
| com.amazonaws.us-east-1.dynamodb            | available | Gateway   |
+----------------------------------------------+--------+-------+
```

**2. Verify Private DNS Enabled:**
```bash
aws ec2 describe-vpc-endpoints \
  --vpc-endpoint-ids <bedrock-endpoint-id> \
  --query 'VpcEndpoints[0].PrivateDnsEnabled'
```

Should return: `true`

**3. Test Lambda Connectivity (Phase 3):**

When you deploy Lambda functions, test that they can reach Bedrock:

```python
# Simple Lambda test function
import boto3
import json

def lambda_handler(event, context):
    # This will use the VPC endpoint automatically
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    
    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20241022-v2:0',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Say hello"}]
            })
        )
        return {
            'statusCode': 200,
            'body': 'Bedrock connection successful via VPC endpoint!'
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }
```

If this works, your VPC endpoints are correctly configured.

---

## Cost Analysis

### On-Demand Cost Model

**VPC Endpoints (Interface type) when ENABLED:**
- $0.01 per hour per endpoint per AZ
- Bedrock endpoint: 2 AZs × $0.01/hour = $0.02/hour
- Polly endpoint: 2 AZs × $0.01/hour = $0.02/hour
- **Total: $0.04/hour when enabled**
- **Total: $0.00/hour when disabled**

### Monthly Cost Examples

Based on actual usage hours:

| Usage Pattern | Hours/Month | VPC Endpoint Cost | Total Estimate* |
|---------------|-------------|-------------------|-----------------|
| **Light** (demos only) | 10 hours | $0.40 | $2-5 |
| **Moderate** (2-3 sessions/week) | 20 hours | $0.80 | $3-8 |
| **Regular** (daily 1-hour sessions) | 30 hours | $1.20 | $5-12 |
| **Heavy** (daily 2-3 hours) | 60 hours | $2.40 | $8-18 |
| **Very Heavy** (3+ hours/day) | 100 hours | $4.00 | $12-25 |
| **Always-On** (legacy comparison) | 730 hours | $29.20 | $35-50 |

*Total includes VPC endpoints + Aurora + S3 + CloudWatch + other services

**Key Insight:** With on-demand endpoints, you save 85-95% compared to always-on for typical learning/demo usage patterns.

### Comparison: Always-On vs On-Demand

**Scenario: Use DocProf 20 hours/month (moderate usage)**

| Architecture | Monthly Cost | Annual Cost | Savings |
|--------------|-------------|-------------|---------|
| NAT Gateway (always-on) | $32.00 | $384.00 | Baseline |
| VPC Endpoints (always-on) | $29.20 | $350.40 | 9% |
| **VPC Endpoints (on-demand)** | **$0.80** | **$9.60** | **97%** |

**Scenario: Use DocProf 100 hours/month (heavy usage)**

| Architecture | Monthly Cost | Annual Cost | Savings |
|--------------|-------------|-------------|---------|
| NAT Gateway (always-on) | $32.00 | $384.00 | Baseline |
| VPC Endpoints (always-on) | $29.20 | $350.40 | 9% |
| **VPC Endpoints (on-demand)** | **$4.00** | **$48.00** | **87%** |

### Cost Optimization Tips

**1. Enable Only When Needed**
```bash
# Before your session
./scripts/enable-ai-services.sh

# After your session
./scripts/disable-ai-services.sh
```

**2. Batch Your Work**
- Enable once, use for 2-3 hours
- Better than enabling/disabling multiple times per day
- Saves time (avoid waiting for Terraform applies)

**3. Set Reminders**
- Calendar reminder to disable after demos
- Slack/email reminder after 4 hours enabled
- Prevents accidental always-on state

**4. Monitor Costs**
- Check AWS Cost Explorer weekly
- Set billing alarm at $10/month
- Review endpoint usage monthly

### Break-Even Analysis

**When does on-demand cost the same as always-on?**

Always-on cost: $29.20/month
On-demand rate: $0.04/hour

Break-even: $29.20 / $0.04 = 730 hours/month

**Conclusion:** If you use DocProf 24/7 (730 hours/month), on-demand and always-on cost the same. For any less usage, on-demand is cheaper.

---

## Comparison with NAT Gateway

| Factor | NAT Gateway | VPC Endpoints (2 AZ) | VPC Endpoints (1 AZ) |
|--------|-------------|---------------------|---------------------|
| **Monthly Cost** | $32.40 | $29.20 | $14.60 |
| **Data Transfer** | $0.045/GB | Included | Included |
| **Use Case** | General internet | AWS services only | AWS services only |
| **High Availability** | Single NAT in 1 AZ | Endpoints in each AZ | Endpoint in 1 AZ only |
| **Performance** | Good | Better | Better |
| **Security** | Internet routing | Private AWS network | Private AWS network |
| **Scalability** | Auto-scales | Auto-scales | Auto-scales |

**Key insight:** For DocProf, we only access AWS services (Bedrock, Polly, S3, DynamoDB, Aurora). VPC endpoints are purpose-built for this use case and provide better security and performance, though cost savings vs. NAT Gateway are minimal in 2-AZ setup.

**Real cost savings come from:**
1. Single-AZ deployment (dev): ~$15/month saved
2. Destroy endpoints when not in use: ~$29/month saved
3. Lambda in public subnets (dev): ~$29/month saved

---

## Production vs. Development Trade-offs

### Production Architecture (What to Show in Interviews)
- ✓ Lambda in private subnets (security best practice)
- ✓ VPC endpoints for AWS services (no internet traversal)
- ✓ Multi-AZ deployment (high availability)
- ✓ Security groups with least privilege
- Cost: ~$29/month for networking

### Development Architecture (What to Run for Learning)
- Lambda in public subnets (or single-AZ private)
- Can still demonstrate VPC endpoint knowledge via code
- Single-AZ deployment
- Cost: ~$0-15/month for networking

**You can deploy the production architecture for demos, then tear it down:**
```bash
# Deploy for interview/demo
terraform apply

# Tear down after demo
terraform destroy

# Cost: Only charged for hours it's running
# Example: 2 hours demo = 2 hours × $0.01/hour/AZ × 2 endpoints × 2 AZs = $0.08
```

---

## Recommendations

### For Your Learning Project

**Immediate (Phase 1):**
1. ✓ Remove NAT Gateway from VPC module (save $32/month)
2. ✓ Add conditional VPC endpoints to module (with `count` parameter)
3. ✓ Deploy VPC with endpoints disabled (cost: $0/month for networking)
4. ✓ Continue to Phase 1.4 (IAM roles)
5. ✓ Create enable/disable control scripts

**Phase 3 (When adding Lambda + AI services):**
- Deploy with endpoints disabled by default
- Use `./scripts/enable-ai-services.sh` when you need to demo or develop
- Use `./scripts/disable-ai-services.sh` when done
- **Cost: Pay only for hours actually used (~$0.04/hour)**

**For Interviews/Demos:**
1. Enable endpoints 30 minutes before demo
2. Give interviewer the URL - anyone can use it while enabled
3. Run demo/interview
4. Disable endpoints after demo
5. **Total cost per demo: 2 hours × $0.04 = $0.08**

### Best Practices

**Daily Usage:**
```bash
# Morning: Start work session
./scripts/enable-ai-services.sh
# Takes 3-5 minutes - get coffee while it provisions

# Work on DocProf for 2-3 hours
# Cost: 3 hours × $0.04 = $0.12

# Evening: End work session
./scripts/disable-ai-services.sh
# Takes 1-2 minutes
```

**Demo Preparation:**
```bash
# 30 minutes before demo
./scripts/enable-ai-services.sh

# Verify it works
./scripts/check-ai-status.sh

# Run demo - other people can access it too

# After demo
./scripts/disable-ai-services.sh
```

**Cost Monitoring:**
```bash
# Check status anytime
./scripts/check-ai-status.sh

# Review costs weekly
aws ce get-cost-and-usage \
  --time-period Start=2025-12-01,End=2025-12-10 \
  --granularity DAILY \
  --metrics BlendedCost
```

### Multi-User Access Pattern

**Important:** Once enabled, the system works for everyone:

```
You (from laptop):
  ./scripts/enable-ai-services.sh
  
Interviewer (from their office):
  https://docprof.cloudfront.net → Works!
  
Colleague (from home):  
  https://docprof.cloudfront.net → Works!
  
All using same infrastructure → All accumulating costs at $0.04/hour
```

**Access control is separate from cost control:**
- Enable/disable controls **when costs accrue**
- Cognito controls **who can log in**
- API Gateway controls **API access**
- Your laptop doesn't need to be online for others to use the system

### Documentation for Interviews

**Talking points:**
1. "I used on-demand VPC endpoints instead of always-on NAT Gateway"
2. "Saves 85-95% on networking costs for intermittent usage"
3. "Production architecture when enabled, zero cost when disabled"
4. "Simple scripts control infrastructure state"
5. "Demonstrates understanding of cost optimization in AWS"
6. "Trade-off: 3-5 minute enable time vs. always-available"

**Demonstrate in interview:**
- Show the Terraform conditional code (`count = var.enable_ai_endpoints ? 1 : 0`)
- Explain why VPC endpoints are better than NAT Gateway for AWS-only access
- Discuss trade-offs: cost vs. convenience
- Show how it works for multiple users simultaneously

---

## Next Steps

### Implementation Sequence

**Step 1: Update Terraform Configuration** (15 minutes)
1. Add `enable_ai_endpoints` variable to `terraform/modules/vpc/variables.tf`
2. Remove NAT Gateway resources from `terraform/modules/vpc/main.tf`
3. Create `terraform/modules/vpc/endpoints.tf` with conditional endpoints (using `count`)
4. Update outputs in `terraform/modules/vpc/outputs.tf` (use `try()` for conditional resources)
5. Pass variable through in `terraform/environments/dev/main.tf`
6. Set default to `false` in `terraform/environments/dev/terraform.tfvars`

**Step 2: Create Control Scripts** (5 minutes)
1. Create `scripts/enable-ai-services.sh`
2. Create `scripts/disable-ai-services.sh`
3. Create `scripts/check-ai-status.sh`
4. Make all scripts executable: `chmod +x scripts/*.sh`

**Step 3: Test Locally** (5 minutes)
```bash
cd terraform/environments/dev
terraform init    # If first time
terraform plan    # Should show endpoints with count = 0
```

**Step 4: Deploy Base Infrastructure** (10 minutes)
```bash
# Deploy VPC with endpoints disabled (default)
terraform apply

# Verify deployment
./scripts/check-ai-status.sh
# Should show: ○ AI Services: OFFLINE
```

**Step 5: Test Enable/Disable** (10 minutes)
```bash
# Enable endpoints
./scripts/enable-ai-services.sh
# Wait 3-5 minutes

# Check status
./scripts/check-ai-status.sh
# Should show: ● AI Services: ONLINE

# Disable endpoints
./scripts/disable-ai-services.sh
# Wait 1-2 minutes

# Check status again
./scripts/check-ai-status.sh
# Should show: ○ AI Services: OFFLINE
```

**Step 6: Continue to Phase 1.4** (IAM roles)
- With VPC infrastructure deployed and tested
- Endpoints remain disabled (no ongoing costs)
- Ready to add IAM roles for Lambda

### Quick Start Commands

**From the project root:**

```bash
# 1. Review changes
cd terraform/environments/dev
terraform plan

# 2. Deploy infrastructure (endpoints disabled by default)
terraform apply

# 3. When you need to use DocProf
cd ../../..
./scripts/enable-ai-services.sh

# 4. Check status
./scripts/check-ai-status.sh

# 5. When done
./scripts/disable-ai-services.sh
```

### Validation Checklist

After implementation, verify:
- [ ] `terraform plan` shows conditional resources correctly
- [ ] Can deploy with endpoints disabled (count = 0)
- [ ] Can enable endpoints via script (count changes to 1)
- [ ] Can disable endpoints via script (count changes to 0)
- [ ] Outputs handle conditional resources (no errors when count = 0)
- [ ] Status script reports correct state
- [ ] No errors in Terraform apply

### Expected Terraform Output

**With endpoints disabled:**
```
Apply complete! Resources: 15 added, 0 changed, 0 destroyed.

Outputs:
ai_endpoints_enabled = false
bedrock_endpoint_id = null
polly_endpoint_id = null
```

**With endpoints enabled:**
```
Apply complete! Resources: 17 added, 0 changed, 0 destroyed.

Outputs:
ai_endpoints_enabled = true
bedrock_endpoint_id = "vpce-xxxxx"
polly_endpoint_id = "vpce-yyyyy"
```

---

## Summary

**On-Demand VPC Endpoints Architecture:**

**What we're building:**
- Conditional VPC endpoints controlled by Terraform variable
- Simple enable/disable scripts for cost control
- Production architecture when enabled, zero networking cost when disabled
- Multi-user access when online

**Why this approach:**
- **Cost savings:** 85-95% reduction vs. always-on for typical usage
- **Production-ready:** Full VPC endpoint architecture when enabled
- **Learning value:** Demonstrates infrastructure-as-code and cost optimization
- **Flexibility:** Pay only for hours actually used
- **Simplicity:** Three scripts control everything

**Cost model:**
- Disabled (default): $0/hour for networking
- Enabled (on-demand): ~$0.04/hour for endpoints
- Monthly: 20 hours = $0.80, 100 hours = $4.00
- Compare to always-on: $29-32/month

**How it works:**
1. Base infrastructure always deployed (VPC, subnets, security groups, Lambda)
2. VPC endpoints created/destroyed on-demand via Terraform
3. Enable before using, disable after using
4. System works for all users when enabled
5. Your laptop controls when costs accrue, not who can access

**Key benefits:**
- ✓ Production-grade security (private AWS network access)
- ✓ Minimal cost for learning/demo project
- ✓ Simple control via scripts
- ✓ Multi-user capable when enabled
- ✓ Great interview talking point

**Implementation:**
- Remove NAT Gateway (not needed)
- Add conditional VPC endpoints (use `count` parameter)
- Create enable/disable scripts
- Deploy with endpoints disabled by default
- Enable only when needed

This approach balances learning objectives (demonstrate modern AWS architecture) with practical constraints (minimize recurring costs during development) while maintaining the ability to run a production-ready system on-demand.

---

**End of VPC Endpoints Implementation Guide - On-Demand Architecture**
