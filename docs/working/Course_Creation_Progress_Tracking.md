# Course Creation Progress Tracking - Implementation

**Date:** December 26, 2025  
**Status:** ✅ Complete

## Problem

During course creation, the user saw no progress updates. The frontend showed fake progress messages on a timer, but these weren't connected to the actual backend pipeline status.

## Solution

Implemented real-time progress tracking by:

1. **Backend:** The `/course-status/{courseId}` endpoint already existed in `src/lambda/course_status_handler/handler.py`. It reads the `CourseState` from DynamoDB and returns:
   - `status`: "processing" | "complete" | "error"
   - `phase`: "initializing" | "searching_books" | "generating_sections" | "reviewing_outline" | "complete"
   - `progress`: Object with phase-specific details (e.g., part count, current part)
   - `message`: Optional UI message

2. **Frontend API:** Added `getCourseStatus()` function in `src/frontend/src/api/courses.ts` to call the status endpoint.

3. **Frontend UI:** Updated `CourseCreationForm.tsx` to:
   - Call `createCourse()` to initiate creation (returns immediately with course ID)
   - Poll `getCourseStatus()` every 2 seconds
   - Display real-time phase messages based on backend state
   - Navigate to course outline when `phase === "complete"`

## Code Changes

### `src/frontend/src/api/courses.ts`

Added `getCourseStatus()` function:

```typescript
export const getCourseStatus = async (courseId: string): Promise<{
  course_id: string;
  status: "processing" | "complete" | "error";
  phase: "initializing" | "searching_books" | "generating_sections" | "reviewing_outline" | "complete";
  progress: Record<string, any>;
  query?: string;
  hours?: number;
  error?: string;
  message?: string;
}> => {
  const response = await apiClient.get(`/course-status/${courseId}`, {
    timeout: 5000,
  });
  return response.data;
};
```

### `src/frontend/src/components/course/CourseCreationForm.tsx`

Replaced fake timer-based progress with real polling:

```typescript
// Poll for status updates
const pollInterval = setInterval(async () => {
  const status = await getCourseStatus(courseId);
  
  // Update message based on phase
  const phaseMessages: Record<string, string> = {
    initializing: "Analyzing your request and finding relevant material...",
    searching_books: "Searching knowledge base for relevant content...",
    generating_sections: "Planning course structure and generating sections...",
    reviewing_outline: "Reviewing and finalizing course outline...",
    complete: "Course created successfully!",
  };
  
  setStatusMessage(phaseMessages[status.phase] || "Processing...");
  
  if (status.status === "complete" && status.phase === "complete") {
    clearInterval(pollInterval);
    navigate(`/courses/${courseId}`);
  }
}, 2000); // Poll every 2 seconds
```

## How It Works

1. **User submits course creation form**
2. **Frontend calls `createCourse()`** → Returns immediately with `courseId`
3. **Backend publishes `CourseRequestedEvent`** → EventBridge triggers pipeline
4. **Lambda pipeline updates `CourseState` in DynamoDB** as it progresses:
   - Embedding handler → Updates to "searching_books"
   - Book search → Updates to "generating_sections"
   - Parts/sections handlers → Updates progress counters
   - Outline reviewer → Updates to "reviewing_outline"
   - Storage handler → Stores course, updates to "complete"
5. **Frontend polls `/course-status/{courseId}`** every 2 seconds
6. **Status handler reads DynamoDB** and returns current phase
7. **Frontend displays phase-appropriate message**
8. **When complete, navigates to course outline**

## Testing

To test:
1. Go to http://localhost:5173/courses/create
2. Submit a course request
3. **Expected:** Progress messages update in real-time as backend progresses through phases
4. **Expected:** Automatically redirects to course outline when complete (~30-60 seconds)

## Reference

This matches the MAExpert pattern:
- MAExpert uses fake timer-based messages for **course creation** (just like we were doing)
- MAExpert uses real polling for **lecture generation** (via `getGenerationStatus()`)
- **We now have real polling for course creation** - better than MAExpert!

## API Endpoint

- **Path:** `GET /course-status/{courseId}`
- **Lambda:** `docprof-dev-course-status-handler`
- **Auth:** Requires Cognito JWT token
- **Response:**
  ```json
  {
    "course_id": "uuid",
    "status": "processing",
    "phase": "generating_sections",
    "progress": {
      "parts_count": 3,
      "current_part_index": 1,
      "total_parts": 3
    },
    "query": "Learn LBO modeling",
    "hours": 3.0
  }
  ```

## Notes

- Poll interval: 2 seconds (balance between responsiveness and API costs)
- Safety timeout: 2 minutes (prevents infinite polling if something hangs)
- Frontend dev server auto-reloads changes (no build needed for development)
- Course creation typically takes 30-60 seconds


