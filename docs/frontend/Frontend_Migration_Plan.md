# Frontend Migration Plan

**Date**: January 2025  
**Status**: In Progress  
**Priority**: High - Enables end-to-end testing

## Overview

Migrate the MAExpert React frontend to work with AWS backend, preserving design and functionality while adapting to AWS-native services (Cognito, API Gateway, S3/CloudFront).

## Goals

1. ✅ Preserve all UI/UX design work from MAExpert
2. ✅ Implement secure Cognito authentication early
3. ✅ Connect to API Gateway endpoints
4. ✅ Support event-driven course generation (polling)
5. ✅ Deploy to S3 + CloudFront

## Migration Strategy

### Phase 1: Infrastructure Setup ✅
- [x] Create Cognito User Pool and App Client
- [x] Configure API Gateway Cognito authorizer
- [x] Set up S3 bucket and CloudFront for frontend hosting

### Phase 2: Frontend Migration
- [ ] Copy MAExpert frontend to `src/frontend/`
- [ ] Install AWS Amplify for Cognito
- [ ] Update API client to use API Gateway
- [ ] Update auth components for Cognito
- [ ] Handle course generation polling

### Phase 3: Integration & Testing
- [ ] Test authentication flow
- [ ] Test chat functionality
- [ ] Test course generation
- [ ] Test book upload
- [ ] End-to-end user workflows

## Key Changes Required

### 1. Authentication
**Before (MAExpert)**:
- Custom JWT token stored in localStorage
- `/auth/login` and `/auth/register` endpoints
- Token validation via `/auth/me`

**After (AWS)**:
- AWS Cognito User Pool
- AWS Amplify Auth library
- JWT tokens managed by Cognito
- Token refresh handled automatically

### 2. API Client
**Before (MAExpert)**:
- `http://localhost:8000/api` base URL
- Axios with Bearer token in Authorization header
- Direct FastAPI endpoints

**After (AWS)**:
- API Gateway URL (from Terraform outputs)
- AWS Amplify API or fetch with Cognito tokens
- Same endpoint paths (preserved in API Gateway)

### 3. Course Generation
**Before (MAExpert)**:
- Synchronous course generation
- Single API call returns complete course

**After (AWS)**:
- Event-driven workflow
- Initial request returns `course_id`
- Poll `/course-status/{courseId}` for progress
- Course available when status is "complete"

### 4. File Upload
**Before (MAExpert)**:
- Direct upload to FastAPI endpoint

**After (AWS)**:
- Direct S3 upload (presigned URL or direct)
- Same UI component, different backend

## Implementation Steps

### Step 1: Cognito Infrastructure
1. Create `terraform/modules/cognito/` module
2. Add Cognito to `terraform/environments/dev/main.tf`
3. Update API Gateway to use Cognito authorizer
4. Deploy infrastructure

### Step 2: Frontend Setup
1. Copy MAExpert frontend to `src/frontend/`
2. Install dependencies: `npm install aws-amplify`
3. Create `.env` file with API Gateway URL
4. Update `package.json` if needed

### Step 3: Authentication Migration
1. Create `src/frontend/src/config/amplify.ts` for Amplify config
2. Update `src/frontend/src/api/auth.ts` to use Cognito
3. Update `src/frontend/src/components/auth/LoginForm.tsx`
4. Update `src/frontend/src/components/auth/RegisterForm.tsx`
5. Update `src/frontend/src/components/common/ProtectedRoute.tsx`

### Step 4: API Client Migration
1. Update `src/frontend/src/api/client.ts` to use API Gateway
2. Update all API functions to use Amplify API or fetch
3. Ensure CORS headers are handled correctly

### Step 5: Course Generation Updates
1. Update `src/frontend/src/components/course/CourseCreationForm.tsx`
2. Add polling logic for course status
3. Update `src/frontend/src/components/course/GenerationProgress.tsx`

### Step 6: Deployment
1. Create `scripts/deploy_frontend.sh`
2. Configure CloudFront distribution
3. Set up S3 bucket for static hosting
4. Test deployment

## File Mapping

| MAExpert Location | DocProf AWS Location | Changes |
|-------------------|---------------------|---------|
| `mna-expert-frontend/src/` | `src/frontend/src/` | API client, auth |
| `mna-expert-frontend/package.json` | `src/frontend/package.json` | Add Amplify |
| `mna-expert-frontend/vite.config.ts` | `src/frontend/vite.config.ts` | Update base URL |
| N/A | `src/frontend/src/config/amplify.ts` | New - Amplify config |

## Testing Checklist

- [ ] User can register new account
- [ ] User can login
- [ ] User can logout
- [ ] Protected routes require authentication
- [ ] Chat messages work
- [ ] Course generation works (with polling)
- [ ] Book upload works
- [ ] All UI components render correctly
- [ ] Dark mode works
- [ ] PDF viewer works
- [ ] Audio playback works (when implemented)

## Notes

- Preserve all Tailwind CSS styling
- Keep React Router structure
- Maintain Zustand state management
- Keep React Query for data fetching
- Preserve PDF viewer functionality
- Keep all component structure

## Next Steps

1. Create Cognito Terraform module
2. Copy frontend code
3. Update authentication
4. Update API client
5. Test end-to-end

