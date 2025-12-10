# Aurora Serverless v2 Auto-Pause Configuration Guide
**Enabling $0/Hour Idle Cost on Your Existing v2 Cluster**

## Critical Update

**Date:** December 10, 2025

Aurora Serverless v2 **now supports auto-pause** as of November 2024. The previous migration guide to v1 was based on outdated information and is **not needed**.

Your existing v2 cluster can pause to 0 ACUs - you just need to update one configuration setting.

## Problem Statement

Your current Aurora Serverless v2 cluster has a **$43/month minimum cost** because:
- Minimum capacity is set to 0.5 ACU
- At 0.5 ACU, the cluster never pauses (it just scales down)
- Cost: 730 hours × $0.06 = $43.80/month even when completely idle

## Solution: Enable Auto-Pause on v2

Simply change the minimum capacity from **0.5 to 0 ACU** and add the auto-pause timeout.

**Result:**
- Cluster pauses after 5 minutes of no connections
- **$0/hour when paused** (only storage charges)
- Resumes automatically in ~15 seconds when accessed
- No migration needed, no data loss

## Cost Comparison

### Before (min_capacity = 0.5)
- **Always running** at 0.5 ACU minimum
- Cost: 730 hours × $0.06 = **$43.80/month**
- No pausing, no savings

### After (min_capacity = 0)
- **Auto-pauses** after 5 minutes of inactivity
- **$0/hour when paused** (only ~$1/month for storage)

**Example usage patterns:**

| Usage Pattern | Hours Active | Monthly Cost | Previous Cost | Savings |
|---------------|--------------|--------------|---------------|---------|
| Light testing (20 hrs/month) | 20 | $1.20 | $43.80 | **$42.60** |
| Demo prep (50 hrs/month) | 50 | $3.00 | $43.80 | **$40.80** |
| Active dev (100 hrs/month) | 100 | $6.00 | $43.80 | **$37.80** |
| Heavy use (200 hrs/month) | 200 | $12.00 | $43.80 | **$31.80** |
| Always-on (730 hrs/month) | 730 | $43.80 | $43.80 | $0 |

**Break-even point:** 730 hours/month (always running)

For a learning/demo project with intermittent usage, this is perfect.

## Requirements

Your cluster already meets the requirements:

**Engine version:** 16.6 ✅
- Minimum required: 16.3 for Aurora PostgreSQL
- You're already on 16.6, so you're good to go

**Region:** us-east-1 ✅
- Auto-pause is available in all commercial AWS regions

**No incompatible features:** ✅
- RDS Proxy: Not yet configured
- Performance Insights: Not enabled
- Enhanced Monitoring: Standard level only

## Implementation Steps

### Step 1: Check Current Configuration

```bash
cd terraform/environments/dev

# View current settings
terraform show | grep -A 10 serverlessv2_scaling_configuration
```

**Current configuration (from Phase 2.2):**
```hcl
serverlessv2_scaling_configuration {
  min_capacity = 0.5  # This prevents auto-pause
  max_capacity = 2.0
  # Missing: seconds_until_auto_pause
}
```

### Step 2: Update Terraform Configuration

Edit `terraform/modules/aurora/main.tf`:

**Find this block:**
```hcl
resource "aws_rds_cluster" "aurora" {
  cluster_identifier      = var.cluster_identifier
  engine                  = "aurora-postgresql"
  engine_mode             = "provisioned"  # Correct for v2
  engine_version          = "16.6"
  
  # ... other config ...
  
  serverlessv2_scaling_configuration {
    min_capacity = 0.5  # CHANGE THIS
    max_capacity = 2.0
  }
}
```

**Change to:**
```hcl
resource "aws_rds_cluster" "aurora" {
  cluster_identifier      = var.cluster_identifier
  engine                  = "aurora-postgresql"
  engine_mode             = "provisioned"  # Keep as-is
  engine_version          = "16.6"         # Keep as-is
  
  # ... other config ...
  
  serverlessv2_scaling_configuration {
    min_capacity             = 0     # CHANGED: Enable auto-pause
    max_capacity             = 2.0   # Keep as-is
    seconds_until_auto_pause = 300   # NEW: 5 minutes of inactivity
  }
}
```

**What changed:**
1. `min_capacity`: 0.5 → 0 (enables auto-pause capability)
2. `seconds_until_auto_pause`: Added with value 300 (5 minutes)

**What stayed the same:**
- `engine_mode`: "provisioned" (correct for v2)
- `engine_version`: "16.6" (already supports auto-pause)
- `max_capacity`: 2.0 (adequate for your workload)
- Everything else in the cluster configuration

### Step 3: Update Variables (Optional)

If you want to make these configurable, edit `terraform/modules/aurora/variables.tf`:

**Add these variables:**
```hcl
variable "min_capacity_acu" {
  description = "Minimum Aurora Capacity Units (0 enables auto-pause)"
  type        = number
  default     = 0
  
  validation {
    condition     = var.min_capacity_acu >= 0 && var.min_capacity_acu <= 256
    error_message = "min_capacity_acu must be between 0 and 256"
  }
}

variable "max_capacity_acu" {
  description = "Maximum Aurora Capacity Units"
  type        = number
  default     = 2.0
  
  validation {
    condition     = var.max_capacity_acu >= 0.5 && var.max_capacity_acu <= 256
    error_message = "max_capacity_acu must be between 0.5 and 256"
  }
}

variable "seconds_until_auto_pause" {
  description = "Seconds of inactivity before auto-pause (300-86400, only applies if min_capacity = 0)"
  type        = number
  default     = 300  # 5 minutes
  
  validation {
    condition     = var.seconds_until_auto_pause >= 300 && var.seconds_until_auto_pause <= 86400
    error_message = "seconds_until_auto_pause must be between 300 (5 min) and 86400 (24 hours)"
  }
}
```

**Then use them in the cluster resource:**
```hcl
serverlessv2_scaling_configuration {
  min_capacity             = var.min_capacity_acu
  max_capacity             = var.max_capacity_acu
  seconds_until_auto_pause = var.min_capacity_acu == 0 ? var.seconds_until_auto_pause : null
}
```

**Note:** The `seconds_until_auto_pause` parameter only applies when `min_capacity = 0`. If you set `min_capacity > 0`, auto-pause is disabled.

### Step 4: Review Terraform Plan

```bash
cd terraform/environments/dev
terraform plan
```

**Expected output:**
```
Terraform will perform the following actions:

  # aws_rds_cluster.aurora will be updated in-place
  ~ resource "aws_rds_cluster" "aurora" {
        id                    = "docprof-dev-aurora"
        
      ~ serverlessv2_scaling_configuration {
          ~ min_capacity             = 0.5 -> 0
          ~ seconds_until_auto_pause = null -> 300
            # (1 unchanged attribute hidden)
        }
    }

Plan: 0 to add, 1 to change, 0 to destroy.
```

**Key points:**
- Shows "updated in-place" (no destruction/recreation)
- No data loss
- Change takes effect immediately
- Cluster stays running during change

### Step 5: Apply Changes

```bash
terraform apply
```

**What happens:**
1. AWS updates the cluster configuration (~30 seconds)
2. Cluster remains available during update
3. Auto-pause capability is enabled
4. Cluster will pause after 5 minutes of no connections

**Output:**
```
aws_rds_cluster.aurora: Modifying... [id=docprof-dev-aurora]
aws_rds_cluster.aurora: Modifications complete after 28s [id=docprof-dev-aurora]

Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

### Step 6: Verify Configuration

**Check via AWS CLI:**
```bash
aws rds describe-db-clusters \
  --db-cluster-identifier docprof-dev-aurora \
  --query 'DBClusters[0].ServerlessV2ScalingConfiguration'
```

**Expected output:**
```json
{
    "MinCapacity": 0.0,
    "MaxCapacity": 2.0,
    "SecondsUntilAutoPause": 300
}
```

**Check via Terraform:**
```bash
terraform output -json | jq '.db_endpoint'
```

**Check via Console:**
1. Go to RDS → Databases
2. Click `docprof-dev-aurora`
3. Click "Configuration" tab
4. Under "Capacity settings":
   - Minimum ACUs: 0
   - Maximum ACUs: 2
   - Auto-pause: 300 seconds

### Step 7: Test Auto-Pause Behavior

**Initial state:**
- After applying the change, cluster is still running (available)
- Currently consuming ACU based on load

**Test pause:**
```bash
# Close all connections to database
# (Close psql sessions, stop any Lambda functions, etc.)

# Wait 5 minutes

# Check cluster status
aws rds describe-db-clusters \
  --db-cluster-identifier docprof-dev-aurora \
  --query 'DBClusters[0].Status'

# Should return: "paused"
```

**Test resume:**
```bash
# Get connection details
ENDPOINT=$(terraform output -raw db_endpoint)
USERNAME=$(terraform output -raw db_master_username)
PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id $(terraform output -raw db_master_password_secret_arn) \
  --query SecretString --output text | jq -r .password)

# Attempt connection (will trigger resume)
psql -h $ENDPOINT -U $USERNAME -d docprof

# First connection after pause:
# - Takes ~15 seconds to establish
# - Database wakes automatically
# - Subsequent connections are instant
```

**Expected behavior:**
1. Initial connection attempt appears to hang for ~15 seconds
2. Connection succeeds
3. Database is now active (status: "available")
4. Following queries are instant
5. After 5 minutes of no connections, pauses again

## Monitoring Auto-Pause Behavior

### CloudWatch Metrics

Key metrics to watch:
- **ServerlessDatabaseCapacity**: Current ACU (shows 0 when paused)
- **ACUUtilization**: Percentage of current capacity used
- **DatabaseConnections**: Number of active connections

**Check current capacity:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name ServerlessDatabaseCapacity \
  --dimensions Name=DBClusterIdentifier,Value=docprof-dev-aurora \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average
```

**When paused:**
- ServerlessDatabaseCapacity: 0
- DatabaseConnections: 0
- ACUUtilization: N/A (no capacity)

**When active:**
- ServerlessDatabaseCapacity: 0.5-2.0 (depends on load)
- DatabaseConnections: 1+ (your connections)
- ACUUtilization: % of allocated capacity in use

### AWS Console Monitoring

1. Go to RDS → Databases → docprof-dev-aurora
2. Click "Monitoring" tab
3. Look for "Serverless database capacity" graph
   - Flat line at 0 = paused
   - Values above 0 = active

### Cost Explorer

Track actual costs:
1. Go to AWS Cost Explorer
2. Filter by service: "Amazon Relational Database Service"
3. Group by: "Usage Type"
4. Look for "ServerlessV2Usage"
   - Hours with 0 usage = paused (no compute charges)
   - Hours with >0 usage = active (billed per second)

## Auto-Pause Configuration Tuning

### Adjusting Pause Timeout

Default: 5 minutes (300 seconds)

**Faster pause (more aggressive savings):**
```hcl
seconds_until_auto_pause = 300   # 5 minutes (default)
seconds_until_auto_pause = 600   # 10 minutes
seconds_until_auto_pause = 1800  # 30 minutes
```

**Slower pause (fewer cold starts):**
```hcl
seconds_until_auto_pause = 3600  # 1 hour
seconds_until_auto_pause = 7200  # 2 hours
seconds_until_auto_pause = 86400 # 24 hours (max)
```

**Recommendation:** Start with 300 seconds. Adjust based on usage patterns:
- Frequent short sessions → 600 seconds (10 min) to reduce cold starts
- Infrequent long sessions → 300 seconds (5 min) for maximum savings

### Adjusting Capacity Range

**Minimum capacity** (when active):
```hcl
min_capacity = 0     # Auto-pause enabled ($0/hr when paused)
min_capacity = 0.5   # Auto-pause disabled, always at least 0.5 ACU
min_capacity = 1.0   # Faster scaling, higher minimum cost
```

**Maximum capacity** (under load):
```hcl
max_capacity = 2.0   # Current setting, good for moderate workload
max_capacity = 4.0   # Better for burst traffic
max_capacity = 8.0   # High-performance queries
```

**Recommendation for DocProf:**
- Keep `min_capacity = 0` (enable auto-pause)
- Keep `max_capacity = 2.0` (adequate for vector search)

## Connection Handling for Paused Database

### Application Considerations

**Lambda functions:**
- Set Lambda timeout > 30 seconds (to handle cold start)
- Implement connection retry logic
- Consider using RDS Proxy (Phase 3) for connection pooling

**Frontend queries:**
- Show loading indicator: "Database is waking up..."
- First query after pause: expect 15-second delay
- Subsequent queries: instant response

**Development workflow:**
- First connection of the day: ~15-second wait
- Keep connection open during active work to prevent re-pause
- Let it pause overnight/weekends for savings

### Expected Resume Behavior

**Timeline for first connection after pause:**
```
T+0s:  Client initiates connection
T+1s:  Aurora detects request, begins wake process
T+5s:  Database engine starting
T+10s: Warming buffer cache, preparing for connections
T+15s: Connection established, ready for queries
T+16s: First query executes normally
T+17s: All subsequent queries are instant
```

**Performance after resume:**
- Initial capacity may be lower than before pause
- Scales up automatically based on workload
- Full performance within 30-60 seconds

## Features That Prevent Auto-Pause

Certain configurations keep the database active:

**Connection-based:**
- RDS Proxy maintaining open connections
- Lambda functions with persistent connections
- Long-running queries or transactions

**Feature-based:**
- None for your current setup
- Auto-pause works with standard Aurora features

**How to identify blocking:**
Check the instance log (console or CLI):
```bash
aws rds download-db-log-file-portion \
  --db-instance-identifier docprof-dev-aurora-instance-1 \
  --log-file-name instance.log \
  --output text
```

Look for messages like:
- "Instance cannot pause: active connections"
- "Instance cannot pause: long-running transaction"

## Troubleshooting

### Issue: Database Won't Pause

**Check 1: Active connections**
```sql
-- Connect to database
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- If count > 0, find the connections
SELECT pid, usename, application_name, state, query 
FROM pg_stat_activity 
WHERE state = 'active';

-- Force close connections (if needed)
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE pid <> pg_backend_pid() AND datname = 'docprof';
```

**Check 2: Configuration**
```bash
# Verify min_capacity = 0
aws rds describe-db-clusters \
  --db-cluster-identifier docprof-dev-aurora \
  --query 'DBClusters[0].ServerlessV2ScalingConfiguration.MinCapacity'

# Should return: 0.0
```

**Check 3: Engine version**
```bash
# Verify version supports auto-pause (need 16.3+)
aws rds describe-db-clusters \
  --db-cluster-identifier docprof-dev-aurora \
  --query 'DBClusters[0].EngineVersion'

# Should return: "16.6" (supports auto-pause)
```

### Issue: Slow Resume Times

**Normal:** 10-15 seconds for first connection after pause

**If consistently > 30 seconds:**
- Check AWS service health dashboard
- Verify security group rules (network vs. wake delay)
- Consider setting `min_capacity = 0.5` to disable auto-pause

**Trade-off decision:**
- Resume time > 30 seconds consistently → Set `min_capacity = 0.5`
- Cost: $43/month, but instant connections
- For demo/learning, 15-second resume is acceptable

### Issue: Terraform Apply Fails

**Error:** `InvalidParameterCombination: SecondsUntilAutoPause requires MinCapacity of 0`

**Solution:**
```hcl
# Make sure min_capacity = 0 is set
serverlessv2_scaling_configuration {
  min_capacity             = 0  # Required for auto-pause
  max_capacity             = 2.0
  seconds_until_auto_pause = 300
}
```

**Error:** `InvalidParameterValue: SecondsUntilAutoPause must be between 300 and 86400`

**Solution:**
```hcl
# Use valid range (5 minutes to 24 hours)
seconds_until_auto_pause = 300  # Minimum: 5 minutes
# or
seconds_until_auto_pause = 86400  # Maximum: 24 hours
```

### Issue: "Engine Version Not Supported"

**Error:** `InvalidParameterCombination: Aurora Serverless v2 auto-pause not supported for version X.X`

**Your case:** Engine version 16.6 **already supports auto-pause**, so you won't see this error.

**If you ever downgrade:** Minimum versions:
- PostgreSQL: 16.3, 15.7, 14.12, 13.15
- MySQL: 3.08.0

## Rollback Plan

If auto-pause causes issues, you can easily disable it:

**Option 1: Disable auto-pause, keep v2**
```hcl
serverlessv2_scaling_configuration {
  min_capacity = 0.5  # Disable auto-pause
  max_capacity = 2.0
  # Remove seconds_until_auto_pause
}
```

Cost: $43/month minimum, but instant connections always

**Option 2: Increase pause timeout**
```hcl
serverlessv2_scaling_configuration {
  min_capacity             = 0
  max_capacity             = 2.0
  seconds_until_auto_pause = 3600  # 1 hour instead of 5 min
}
```

Fewer pauses, fewer cold starts, less savings

## Comparison to Aurora Serverless v1

You might see references to Aurora Serverless v1 with auto-pause. Here's why v2 is better:

| Feature | Serverless v1 | Serverless v2 (Your Setup) |
|---------|---------------|----------------------------|
| **Auto-pause** | ✅ Yes | ✅ Yes (as of Nov 2024) |
| **Resume time** | ~30 seconds | ~15 seconds |
| **Max version** | PostgreSQL 13.12 | PostgreSQL 16.6 |
| **Scaling granularity** | 2 ACU jumps (2, 4, 8...) | 0.5 ACU increments |
| **Max capacity** | 256 ACU | 256 ACU |
| **Multi-AZ** | No (single AZ) | Yes (with readers) |
| **Reads** | Writer only | Up to 15 readers |
| **Engine mode** | "serverless" | "provisioned" |

**Verdict:** v2 is superior in every way. You made the right choice initially, just needed to enable auto-pause.

## Cost Summary

### Monthly Cost Breakdown

**Active usage (when database is running):**
- Compute: $0.06/hour per 0.5 ACU
- Your range: 0.5-2.0 ACU = $0.06-0.24/hour

**Paused (when idle):**
- Compute: $0/hour
- Storage: ~$0.10/GB/month

**Example monthly costs:**

| Scenario | Active Hours | Compute Cost | Storage Cost | Total |
|----------|--------------|--------------|--------------|-------|
| Light testing | 20 | $1.20 | $1.00 | **$2.20** |
| Demo prep | 50 | $3.00 | $1.00 | **$4.00** |
| Active dev | 100 | $6.00 | $1.00 | **$7.00** |
| Heavy use | 200 | $12.00 | $1.00 | **$13.00** |

**Compared to previous (min_capacity = 0.5):**
- Was: $43.80/month (always running)
- Now: $2-13/month (depends on usage)
- **Savings: $31-42/month (71-96% reduction)**

## Interview Talking Points

**Recent AWS Features:**
- "Identified that Aurora Serverless v2 gained auto-pause capability in November 2024"
- "Stayed current with latest AWS releases to optimize costs"
- "Enabled 0 ACU minimum capacity for true pay-per-use pricing"

**Cost Optimization:**
- "Reduced database costs from $43/month to ~$5/month for typical usage"
- "96% cost reduction for intermittent workload pattern"
- "Accepted 15-second cold start for massive cost savings"

**Trade-offs:**
- "Appropriate for demo/learning environment"
- "Would reconsider for production with strict SLAs"
- "Demonstrates understanding of cost vs. performance balance"

**Architecture:**
- "Combined with on-demand VPC endpoints for comprehensive cost control"
- "Total infrastructure idle cost: ~$6/month (VPC + database + S3)"
- "Scales automatically under load, pauses automatically when idle"

## Next Steps After Configuration

1. **Verify auto-pause works:**
   - Close all connections
   - Wait 10 minutes
   - Check status: should show "paused"
   - Connect: should resume automatically

2. **Monitor for a few days:**
   - Check CloudWatch metrics
   - Verify billing shows $0/hour when paused
   - Confirm resume behavior is acceptable

3. **Continue with Phase 2.3:**
   - Data migration scripts
   - Load corpus into Aurora
   - Benchmark vector search performance

4. **Proceed to Phase 3:**
   - Lambda functions (compute layer)
   - RDS Proxy for connection pooling
   - API Gateway for REST endpoints

## Summary

**What you're doing:**
- Changing `min_capacity` from 0.5 to 0
- Adding `seconds_until_auto_pause = 300`

**What you're NOT doing:**
- ❌ Migrating to v1
- ❌ Destroying and recreating cluster
- ❌ Downgrading engine version
- ❌ Losing any data

**What you get:**
- ✅ Auto-pause after 5 minutes idle
- ✅ $0/hour when paused
- ✅ Automatic resume in ~15 seconds
- ✅ Same v2 features and performance
- ✅ 71-96% cost reduction

**Risk level:** Very low
- In-place configuration change
- No data loss
- Reversible immediately
- Cluster stays available during change

**Time required:** 5 minutes (including Terraform apply)

**Cost impact:** -$35-42/month for typical usage

---

**Status:** Ready to implement (correct approach)
**Date:** December 10, 2025
**Note:** Previous v1 migration guide is obsolete and should be ignored
