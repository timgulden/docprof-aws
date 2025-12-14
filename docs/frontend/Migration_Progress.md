# Frontend Migration Progress

**Date**: January 2025  
**Status**: In Progress

## ✅ Completed

### 1. Infrastructure Setup
- ✅ Created Cognito User Pool Terraform module (`terraform/modules/cognito/`)
- ✅ Added Cognito to main Terraform configuration
- ✅ Updated API Gateway module to support Cognito authorizers
- ✅ Configured all API endpoints to require authentication (`require_auth = true`)
- ✅ Added Cognito outputs to Terraform outputs

### 2. Frontend Code Migration
- ✅ Copied MAExpert frontend to `src/frontend/`
- ✅ Added AWS Amplify dependency to `package.json`
- ✅ Created Amplify configuration (`src/config/amplify.ts`)
- ✅ Updated `main.tsx` to import Amplify config first
- ✅ Updated API client (`src/api/client.ts`) to use API Gateway and Cognito tokens
- ✅ Updated auth API (`src/api/auth.ts`) to use Cognito instead of custom JWT

## ✅ Completed (Continued)

### Auth Components & State Management
- ✅ Updated `LoginForm.tsx` to use email instead of username
- ✅ Updated `RegisterForm.tsx` to use email and handle Cognito registration
- ✅ Updated `ProtectedRoute.tsx` to check Cognito session
- ✅ Updated `authBootstrap.ts` to check Cognito session on startup
- ✅ Updated `authExecutor.ts` to handle Cognito-specific errors
- ✅ Created `.env.example` file with required configuration

## 🔄 In Progress

### Course Generation Polling
- Need to update course generation components to poll for status

## 📋 Next Steps

### Immediate (This Session)
1. **Update Auth Components**
   - Update `LoginForm.tsx` to use Cognito signIn
   - Update `RegisterForm.tsx` to use Cognito signUp
   - Handle email verification flow
   - Update `ProtectedRoute.tsx` to check Cognito session

2. **Update Auth State Management**
   - Update `authStore.ts` to work with Cognito
   - Update `authBootstrap.ts` to use Cognito
   - Remove old token-based auth logic

### Short Term
3. **Course Generation Polling**
   - Update `CourseCreationForm.tsx` to poll `/course-status/{courseId}`
   - Update `GenerationProgress.tsx` to show real-time status
   - Handle event-driven workflow completion

4. **Environment Variables**
   - Create `.env.example` file with required variables
   - Document how to get values from Terraform outputs
   - Update deployment docs

5. **Testing**
   - Test login flow
   - Test registration flow
   - Test API calls with authentication
   - Test course generation

### Medium Term
6. **Frontend Hosting**
   - Create CloudFront + S3 Terraform module
   - Set up deployment script
   - Configure custom domain (optional)

## Configuration Required

The frontend needs these environment variables (set in `.env` file):

```bash
VITE_COGNITO_USER_POOL_ID=<from-terraform-output>
VITE_COGNITO_USER_POOL_CLIENT_ID=<from-terraform-output>
VITE_API_GATEWAY_URL=<from-terraform-output>
VITE_AWS_REGION=us-east-1
```

To get these values after deploying Terraform:
```bash
cd terraform/environments/dev
terraform output cognito_user_pool_id
terraform output cognito_user_pool_client_id
terraform output api_gateway_url
```

## Key Changes Made

### API Client (`src/api/client.ts`)
- Changed from `VITE_API_URL` to `VITE_API_GATEWAY_URL`
- Removed localStorage token management
- Added Amplify `fetchAuthSession()` to get Cognito tokens
- Tokens automatically included in Authorization header

### Auth API (`src/api/auth.ts`)
- Replaced custom JWT endpoints with Cognito functions
- `loginUser()` → `signIn()` from Amplify
- `registerUser()` → `signUp()` from Amplify
- `getCurrentUser()` → `getCognitoUser()` from Amplify
- `logoutUser()` → `signOut()` from Amplify

### Amplify Config (`src/config/amplify.ts`)
- Configured Cognito User Pool
- Configured API Gateway REST API
- Environment variable-based configuration

## Notes

- All API endpoints now require authentication
- Cognito handles token refresh automatically
- Email verification is required (can be auto-confirmed in dev)
- Custom attributes (like playbackSpeed) may need to be added to Cognito User Pool schema

## Testing Checklist

- [ ] User can register new account
- [ ] User receives email verification code
- [ ] User can verify email and login
- [ ] User can login with existing account
- [ ] Protected routes require authentication
- [ ] API calls include Cognito tokens
- [ ] Token refresh works automatically
- [ ] User can logout

