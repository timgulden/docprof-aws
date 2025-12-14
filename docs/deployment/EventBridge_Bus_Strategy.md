# EventBridge Bus Strategy: Default vs Custom Bus

## Current Situation

We have a **mixed state** where some EventBridge rules are on the **default bus** and others are on a **custom bus** (`docprof-dev-course-events`). This document explains the differences and recommends a consistent approach.

## Default Bus vs Custom Bus: Key Differences

### Default Event Bus

**Characteristics:**
- **Pre-configured**: Automatically exists in every AWS account
- **AWS Service Events**: Automatically receives events from AWS services (EC2 state changes, S3 uploads, etc.)
- **No Resource Policy Needed**: Same-account access works without additional configuration
- **Simpler Setup**: Less configuration overhead
- **Cannot be Deleted**: Always available

**Use Cases:**
- Processing AWS service events
- Simple event-driven architectures within a single account
- When you don't need isolation or cross-account sharing

**Limitations:**
- **No Isolation**: All events from AWS services and your applications share the same bus
- **No Cross-Account by Default**: Requires resource policy for cross-account access
- **Less Control**: Can't set custom permissions or policies on the bus itself

### Custom Event Bus

**Characteristics:**
- **User-Created**: Must be explicitly created
- **Isolation**: Separate namespace for your application events
- **Resource Policies**: Can define fine-grained access control (who can publish/subscribe)
- **Cross-Account Ready**: Designed for sharing events across AWS accounts
- **Can be Deleted**: Full lifecycle control

**Use Cases:**
- **Isolation**: Separating application events from AWS service events
- **Multi-Account**: Sharing events between AWS accounts
- **Security**: Implementing strict access controls
- **Organization**: Grouping related events by domain/application

**Limitations:**
- **More Configuration**: Requires resource policies for cross-account access
- **No AWS Service Events**: Doesn't automatically receive AWS service events
- **Additional Cost**: Slight overhead (minimal, but exists)

## Our Current Mixed State

### Rules on Default Bus:
- `docprof-dev-course-requested`
- `docprof-dev-embedding-generated`
- `docprof-dev-s3-document-upload`

### Rules on Custom Bus (`docprof-dev-course-events`):
- `docprof-dev-book-summaries-found`
- `docprof-dev-parts-generated`
- `docprof-dev-part-sections-generated`
- `docprof-dev-all-parts-complete`
- `docprof-dev-outline-reviewed`
- `docprof-dev-document-processed`
- `docprof-dev-source-summary-stored`

## The Problem with Mixed Buses

**Issue:** Events published to one bus cannot trigger rules on another bus. This breaks the course generation pipeline:

1. `course_request_handler` publishes `EmbeddingGenerated` to **default bus** ✅
2. `embedding_generated` rule on **default bus** should trigger `course_embedding_handler` ✅
3. `course_embedding_handler` publishes `BookSummariesFound` to **default bus** ❌
4. `book_summaries_found` rule is on **custom bus** ❌
5. **Pipeline breaks** - events don't match rules on different buses

## Recommended Solutions

### Option 1: Use Default Bus for Everything (Simplest)

**Pros:**
- ✅ Works immediately (no custom bus issues)
- ✅ Simpler configuration
- ✅ No resource policy needed
- ✅ Less to manage

**Cons:**
- ❌ No isolation from AWS service events
- ❌ All events mixed together
- ❌ Less control over access

**When to Use:**
- Single-account deployment
- Don't need isolation
- Want simplest setup

**Implementation:**
- Remove `event_bus_name` from all rules (use default)
- Remove `EVENT_BUS_NAME` env vars from Lambdas
- Delete custom bus (or keep for future use)

### Option 2: Fix Custom Bus and Use It Consistently (Recommended)

**Pros:**
- ✅ Isolation from AWS service events
- ✅ Better organization
- ✅ Ready for cross-account if needed
- ✅ More control and security

**Cons:**
- ❌ Need to fix the custom bus issue
- ❌ Slightly more configuration
- ❌ Need resource policy for cross-account (if needed)

**When to Use:**
- Want isolation
- May need cross-account sharing
- Want better organization
- Production-ready architecture

**Implementation:**
- Fix custom bus event matching issue (likely resource policy)
- Move all rules to custom bus
- Set `EVENT_BUS_NAME` env var consistently
- Ensure all Lambdas publish to custom bus

### Option 3: Hybrid Approach (Not Recommended)

**Why Not:**
- ❌ Breaks event flow between stages
- ❌ Confusing to maintain
- ❌ Hard to debug
- ❌ Events can't cross bus boundaries

## The Custom Bus Issue We Encountered

**Symptom:** Events published successfully (`put_events` returned success) but EventBridge showed zero `IncomingEvents` and zero `MatchedEvents` in CloudWatch metrics.

**Possible Causes:**
1. **Resource Policy Missing**: Custom buses may need resource-based policies even for same-account access
2. **Metrics Delay**: CloudWatch metrics can have delays (unlikely to be this)
3. **Event Format**: Events might not match rule patterns (we tested this, pattern was correct)
4. **Bus Configuration**: Some configuration issue with the custom bus itself

**What We Tried:**
- ✅ Verified IAM permissions (`events:PutEvents`)
- ✅ Verified rule patterns match events
- ✅ Verified rules are enabled
- ✅ Verified targets are configured
- ✅ Tested with default bus (works perfectly)

**What We Didn't Try:**
- Resource-based policy on custom bus
- EventBridge logging (to see if events reach the bus)
- Different event formats

## Recommendation

**For Now:** Use **Option 1 (Default Bus)** to unblock development:
- Fastest path to working system
- No custom bus debugging needed
- Can always migrate to custom bus later

**For Production:** Consider **Option 2 (Custom Bus)**:
- Better isolation and organization
- More professional architecture
- Worth fixing the custom bus issue properly

## Migration Path

If we start with default bus and want to migrate to custom bus later:

1. **Create resource policy** on custom bus allowing same-account access
2. **Update all Lambdas** to publish to custom bus (`EVENT_BUS_NAME` env var)
3. **Move all rules** to custom bus (update Terraform)
4. **Test thoroughly** to ensure events flow correctly
5. **Monitor CloudWatch metrics** to verify events are being processed

## Next Steps

1. ✅ Fix Lambda packaging issue (current blocker)
2. ✅ Choose bus strategy (default vs custom)
3. ✅ Implement consistently across all rules
4. ✅ Test end-to-end course generation flow
5. ✅ Document the decision and rationale



