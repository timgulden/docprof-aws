# Async Course Generation - Test Results

## Test Date
2025-12-12

## Test Summary

### ✅ What's Working

1. **API Endpoints**
   - `POST /courses` returns immediately (<1 second) with `course_id` and `status: "processing"`
   - `GET /course-status/{courseId}` successfully reads state from DynamoDB
   - Status endpoint shows correct phase and progress information

2. **State Management**
   - Course state is saved to DynamoDB correctly
   - State includes query, hours, preferences, and current phase
   - Status endpoint correctly reads and returns state

3. **Event Publishing**
   - Events are being published to EventBridge successfully
   - No errors in `put_events` calls
   - Event format matches rule pattern (tested with `test-event-pattern`)

4. **Infrastructure**
   - EventBridge VPC endpoint exists and is available
   - EventBridge rules are enabled and configured correctly
   - Lambda handlers have correct permissions
   - Database environment variables added to all handlers

### ⚠️ Issue Identified

**EventBridge handlers are not being triggered automatically**

- Events are published successfully (no failures)
- EventBridge shows **zero matched events** in CloudWatch metrics
- Handlers work correctly when invoked directly
- Rule pattern matches events (tested)

**Possible Causes:**
1. EventBridge metrics delay (events may be processed but metrics not updated)
2. Custom event bus configuration issue
3. EventBridge rule not matching events despite pattern test passing
4. Timing/race condition with event publishing

## Test Results

### Test 1: API Response Time
```
POST /courses
Response time: <1 second ✅
Response: {"course_id": "...", "status": "processing", ...}
```

### Test 2: Status Polling
```
GET /course-status/{courseId}
Response: {"status": "processing", "phase": "searching_books", ...}
Status updates correctly ✅
```

### Test 3: Event Publishing
```
Events published: ✅ Success (no errors)
EventBridge matched events: ❌ Zero (expected >0)
Handler invocations: ❌ Zero (expected >0)
```

### Test 4: Manual Handler Invocation
```
Direct Lambda invoke: ✅ Works correctly
Handler processes event: ✅ Success
Database query: ✅ Works (with proper embedding dimensions)
```

## Next Steps

1. **Investigate EventBridge Matching**
   - Check EventBridge CloudWatch logs for rule evaluation
   - Verify event bus configuration
   - Test with default event bus to rule out custom bus issues

2. **Alternative Approach**
   - Consider using Step Functions for orchestration instead of EventBridge
   - Or use SQS + Lambda for more reliable event processing

3. **Immediate Workaround**
   - For testing, manually trigger handlers via AWS CLI
   - Or invoke handlers directly from course_request_handler (synchronous fallback)

## Files Modified

- `src/lambda/course_request_handler/handler.py` - Made async
- `src/lambda/course_status_handler/handler.py` - **NEW** - Status endpoint
- `src/lambda/shared/event_publisher.py` - Enhanced logging
- `terraform/environments/dev/main.tf` - Added Lambda and route
- `terraform/modules/iam/lambda_roles.tf` - Added EventBridge permissions
- All course handler Lambdas - Added database environment variables

## API Endpoints

- `POST /courses` - Start course generation (async)
- `GET /course-status/{courseId}` - Poll status
- `GET /course?courseId={finalCourseId}` - Retrieve final course

## Status

**Async API**: ✅ Working  
**Status Polling**: ✅ Working  
**EventBridge Flow**: ⚠️ Events published but handlers not triggered automatically
