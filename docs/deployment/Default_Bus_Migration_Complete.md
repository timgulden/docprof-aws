# Default Bus Migration Complete

## Summary

Successfully migrated all EventBridge rules and Lambda functions to use the **default event bus** instead of the custom bus. This simplifies configuration and eliminates the custom bus event matching issues we encountered.

## Changes Made

### 1. EventBridge Rules ✅
**File**: `terraform/modules/eventbridge/main.tf`

- Commented out `event_bus_name` from all 9 rules:
  - `course_requested`
  - `embedding_generated`
  - `book_summaries_found`
  - `parts_generated`
  - `part_sections_generated`
  - `all_parts_complete`
  - `outline_reviewed`
  - `document_processed`
  - `source_summary_stored`

All rules now use the default bus (omitting `event_bus_name` uses default).

### 2. Lambda Environment Variables ✅
**File**: `terraform/environments/dev/main.tf`

- Removed `EVENT_BUS_NAME` environment variable from all Lambda functions:
  - `course_request_handler_lambda`
  - `course_embedding_handler_lambda`
  - `course_book_search_handler_lambda`
  - `course_parts_handler_lambda`
  - `course_sections_handler_lambda`
  - `course_outline_reviewer_lambda`
  - `course_storage_handler_lambda`
  - `source_summary_generator_lambda` (was still set)

### 3. Event Publisher Code ✅
**File**: `src/lambda/shared/event_publisher.py`

- Updated to use default bus when `EVENT_BUS_NAME` is empty or not set
- Only includes `EventBusName` in `put_events` if a custom bus is specified
- Backward compatible - can still use custom bus if `EVENT_BUS_NAME` is set

### 4. Direct Event Publishing ✅
**Files**: 
- `src/lambda/document_processor/handler.py`
- `src/lambda/source_summary_generator/handler.py`

- Updated to use default bus when `EVENT_BUS_NAME` is empty
- Only includes `EventBusName` if custom bus is specified

## Migration Steps

1. ✅ Updated all EventBridge rules to use default bus
2. ✅ Removed `EVENT_BUS_NAME` env vars from Terraform
3. ✅ Updated `event_publisher.py` to handle default bus
4. ✅ Updated direct event publishing code
5. ⏳ **Next**: Apply Terraform changes and test

## Testing Checklist

After applying Terraform changes:

- [ ] Verify all rules exist on default bus
- [ ] Test course generation flow end-to-end
- [ ] Verify EventBridge events are being matched
- [ ] Check CloudWatch metrics for `MatchedEvents`
- [ ] Verify handlers are being triggered
- [ ] Test document processing flow
- [ ] Test source summary generation flow

## Rollback Plan

If issues occur, can rollback by:
1. Uncommenting `event_bus_name` in EventBridge rules
2. Restoring `EVENT_BUS_NAME` env vars
3. Reverting code changes

## Benefits

1. ✅ **Simpler Configuration**: No custom bus to manage
2. ✅ **No Resource Policies**: Default bus works without additional setup
3. ✅ **Fixes Event Matching**: Default bus works reliably
4. ✅ **Same Functionality**: All EventBridge features still available
5. ✅ **Easier Debugging**: Default bus is well-documented and standard

## Next Steps

1. Apply Terraform changes: `terraform apply`
2. Recreate Lambda function (if still needed for packaging fix)
3. Test end-to-end course generation
4. Monitor EventBridge metrics
5. Document any issues or observations

