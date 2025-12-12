# Course Generation UI Integration Guide

## Overview

Course generation is an **asynchronous process** that takes 30-60+ seconds. The API returns immediately, and the UI polls a status endpoint to track progress.

## Architecture

```
UI → POST /courses → Returns course_id immediately (<1 second)
     ↓
     Poll GET /course-status/{courseId} every 2-10 seconds
     ↓
     When status === "complete" → GET /course?courseId={finalCourseId}
```

## API Endpoints

### 1. Start Course Generation

**Endpoint**: `POST /courses`

**Request**:
```json
{
  "query": "Learn DCF valuation",
  "hours": 2.0,
  "preferences": {
    "depth": "balanced",
    "presentation_style": "conversational",
    "pace": "moderate",
    "additional_notes": ""
  }
}
```

**Response** (immediate, <1 second):
```json
{
  "course_id": "acb733ba-20fd-4c7c-a028-73fbbda873b1",
  "status": "processing",
  "message": "Course generation started. Poll /course-status/{course_id} for progress.",
  "query": "Learn DCF valuation",
  "hours": 2.0
}
```

**Error Responses**:
- `400 Bad Request`: Missing required field (e.g., `query`)
- `500 Internal Server Error`: Server error (check logs)

### 2. Poll Course Status

**Endpoint**: `GET /course-status/{courseId}`

**Path Parameter**: `courseId` (UUID from step 1)

**Response** (processing):
```json
{
  "course_id": "acb733ba-20fd-4c7c-a028-73fbbda873b1",
  "status": "processing",
  "phase": "searching_books",
  "progress": {},
  "query": "Learn DCF valuation",
  "hours": 2.0
}
```

**Response** (generating sections):
```json
{
  "course_id": "acb733ba-20fd-4c7c-a028-73fbbda873b1",
  "status": "processing",
  "phase": "generating_sections",
  "progress": {
    "parts_count": 3
  },
  "query": "Learn DCF valuation",
  "hours": 2.0
}
```

**Response** (complete):
```json
{
  "course_id": "acb733ba-20fd-4c7c-a028-73fbbda873b1",
  "status": "complete",
  "phase": "complete",
  "progress": {
    "course_id": "final-uuid-from-database",
    "title": "DCF Valuation Course",
    "estimated_hours": 2.0
  },
  "query": "Learn DCF valuation",
  "hours": 2.0
}
```

**Response** (error):
```json
{
  "course_id": "acb733ba-20fd-4c7c-a028-73fbbda873b1",
  "status": "error",
  "phase": "error",
  "error": "Failed to generate course: No relevant books found",
  "query": "Learn DCF valuation",
  "hours": 2.0
}
```

**Error Responses**:
- `400 Bad Request`: Missing `courseId` parameter
- `404 Not Found`: Course not found (invalid courseId or expired)

### 3. Retrieve Final Course

**Endpoint**: `GET /course?courseId={finalCourseId}`

**Query Parameter**: `courseId` (from `progress.course_id` in complete status response)

**Response**:
```json
{
  "course": {
    "course_id": "final-uuid",
    "user_id": "user-uuid",
    "title": "DCF Valuation Course",
    "original_query": "Learn DCF valuation",
    "estimated_hours": 2.0,
    "created_at": "2025-12-12T01:00:00Z",
    "last_modified": "2025-12-12T01:02:00Z",
    "preferences": {...},
    "status": "active"
  },
  "sections": [
    {
      "section_id": "uuid",
      "course_id": "final-uuid",
      "order_index": 0,
      "title": "Introduction to DCF",
      "learning_objectives": [...],
      "content_summary": "...",
      "estimated_minutes": 30,
      "status": "not_started",
      ...
    },
    ...
  ]
}
```

## Status Values

### `status` Field
- `"processing"`: Course generation in progress
- `"complete"`: Course generation finished successfully
- `"error"`: Course generation failed (check `error` field)

### `phase` Field
- `"initializing"`: Initial setup
- `"searching_books"`: Searching for relevant books
- `"generating_sections"`: Generating course sections
- `"reviewing_outline"`: Reviewing and adjusting outline
- `"complete"`: Finished

## Polling Strategy

### Recommended Approach

```javascript
async function pollCourseStatus(courseId, onProgress) {
  const pollInterval = {
    initial: 2000,    // 2 seconds
    after30s: 5000,  // 5 seconds after 30s
    after60s: 10000  // 10 seconds after 60s
  };
  
  const startTime = Date.now();
  let currentInterval = pollInterval.initial;
  
  const poll = async () => {
    try {
      const response = await fetch(`/course-status/${courseId}`);
      const data = await response.json();
      
      // Call progress callback
      onProgress(data);
      
      // Stop polling if complete or error
      if (data.status === 'complete' || data.status === 'error') {
        return data;
      }
      
      // Adjust polling interval based on elapsed time
      const elapsed = Date.now() - startTime;
      if (elapsed > 60000) {
        currentInterval = pollInterval.after60s;
      } else if (elapsed > 30000) {
        currentInterval = pollInterval.after30s;
      }
      
      // Continue polling
      setTimeout(poll, currentInterval);
      
    } catch (error) {
      console.error('Error polling course status:', error);
      // Retry with exponential backoff or show error to user
      setTimeout(poll, currentInterval * 2);
    }
  };
  
  // Start polling
  poll();
}
```

### React Hook Example

```typescript
import { useState, useEffect } from 'react';

interface CourseStatus {
  course_id: string;
  status: 'processing' | 'complete' | 'error';
  phase: string;
  progress: Record<string, any>;
  query?: string;
  hours?: number;
  error?: string;
}

function useCourseStatus(courseId: string | null) {
  const [status, setStatus] = useState<CourseStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!courseId) return;

    let pollInterval: NodeJS.Timeout;
    let timeout: NodeJS.Timeout;
    const startTime = Date.now();

    const poll = async () => {
      try {
        const response = await fetch(
          `https://api.example.com/course-status/${courseId}`
        );
        
        if (!response.ok) {
          if (response.status === 404) {
            setError('Course not found');
            return;
          }
          throw new Error(`HTTP ${response.status}`);
        }

        const data: CourseStatus = await response.json();
        setStatus(data);
        setLoading(false);

        // Stop polling if complete or error
        if (data.status === 'complete' || data.status === 'error') {
          clearInterval(pollInterval);
          clearTimeout(timeout);
          return;
        }

        // Adjust polling interval
        const elapsed = Date.now() - startTime;
        const interval = elapsed > 60000 ? 10000 : elapsed > 30000 ? 5000 : 2000;
        
        clearInterval(pollInterval);
        pollInterval = setInterval(poll, interval);

      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setLoading(false);
        clearInterval(pollInterval);
        clearTimeout(timeout);
      }
    };

    // Initial poll
    setLoading(true);
    poll();

    // Set maximum timeout (e.g., 5 minutes)
    timeout = setTimeout(() => {
      clearInterval(pollInterval);
      setError('Course generation timed out');
      setLoading(false);
    }, 5 * 60 * 1000);

    return () => {
      clearInterval(pollInterval);
      clearTimeout(timeout);
    };
  }, [courseId]);

  return { status, loading, error };
}
```

## UI Flow Example

### Complete Flow

```typescript
async function generateCourse(query: string, hours: number) {
  try {
    // 1. Start course generation
    const startResponse = await fetch('/courses', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        hours,
        preferences: {}
      })
    });

    if (!startResponse.ok) {
      throw new Error(`Failed to start: ${startResponse.statusText}`);
    }

    const { course_id } = await startResponse.json();
    
    // 2. Show loading state with progress
    showLoadingState(course_id);
    
    // 3. Poll for status
    const finalStatus = await pollCourseStatus(course_id, (status) => {
      // Update UI with progress
      updateProgressBar(status.phase, status.progress);
      showStatusMessage(getPhaseMessage(status.phase));
    });

    // 4. Handle completion or error
    if (finalStatus.status === 'complete') {
      const finalCourseId = finalStatus.progress.course_id;
      const course = await fetchCourse(finalCourseId);
      showCourse(course);
    } else {
      showError(finalStatus.error || 'Course generation failed');
    }

  } catch (error) {
    showError(error.message);
  }
}
```

## Phase Messages for UI

```typescript
function getPhaseMessage(phase: string): string {
  const messages = {
    'initializing': 'Initializing course generation...',
    'searching_books': 'Searching for relevant books...',
    'generating_sections': 'Generating course sections...',
    'reviewing_outline': 'Reviewing and optimizing course outline...',
    'complete': 'Course generation complete!',
    'error': 'An error occurred during course generation.'
  };
  
  return messages[phase] || 'Processing...';
}
```

## Error Handling

### Common Errors

1. **404 Not Found** (course-status endpoint)
   - Course ID invalid or expired
   - State was cleaned up (TTL: 7 days)
   - **Action**: Show error, allow user to start new course

2. **500 Internal Server Error**
   - Server-side error
   - **Action**: Show error, log details, allow retry

3. **Status: "error"** (in status response)
   - Course generation failed
   - Check `error` field for details
   - **Action**: Show error message, allow user to try different query

### Error Recovery

```typescript
// If polling fails, implement exponential backoff
let retryCount = 0;
const maxRetries = 5;

async function pollWithRetry(courseId: string) {
  try {
    return await pollCourseStatus(courseId);
  } catch (error) {
    if (retryCount < maxRetries) {
      retryCount++;
      const delay = Math.min(1000 * Math.pow(2, retryCount), 30000);
      await new Promise(resolve => setTimeout(resolve, delay));
      return pollWithRetry(courseId);
    }
    throw error;
  }
}
```

## Best Practices

1. **Show Progress**: Display current phase and progress information
2. **Allow Cancellation**: Provide a way to cancel long-running requests
3. **Handle Timeouts**: Set maximum timeout (e.g., 5 minutes)
4. **Error Recovery**: Implement retry logic with exponential backoff
5. **User Feedback**: Show clear messages for each phase
6. **Optimistic UI**: Show course structure as soon as it's available

## Testing

### Test Course Generation

```bash
# 1. Start course generation
curl -X POST https://api.example.com/courses \
  -H "Content-Type: application/json" \
  -d '{"query": "Learn DCF valuation", "hours": 2.0}'

# Response: {"course_id": "uuid-here", "status": "processing", ...}

# 2. Poll status
curl https://api.example.com/course-status/uuid-here

# 3. When complete, retrieve course
curl "https://api.example.com/course?courseId=final-uuid"
```

## API Base URL

**Development**: `https://xp2vbfyu3f.execute-api.us-east-1.amazonaws.com/dev`

**Production**: (TBD - will be updated when production environment is created)

## Related Documentation

- [Async Course Generation Implementation](./Async_Course_Generation_Implementation.md) - Technical details
- [Course Storage Implementation](./Course_Storage_Implementation.md) - Database schema
- [API Contracts](../contracts/README.md) - Full API specification
