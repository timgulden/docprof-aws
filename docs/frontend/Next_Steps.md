# Frontend Migration - Next Steps

## Immediate Next Steps

### 1. Deploy Cognito Infrastructure
```bash
cd terraform/environments/dev
terraform init
terraform plan  # Review changes
terraform apply  # Deploy Cognito
```

### 2. Get Configuration Values
After deploying, get the values needed for `.env`:
```bash
terraform output cognito_user_pool_id
terraform output cognito_user_pool_client_id
terraform output api_gateway_url
```

### 3. Create Frontend `.env` File
```bash
cd src/frontend
cp .env.example .env
# Edit .env with values from Terraform outputs
```

### 4. Install Dependencies
```bash
cd src/frontend
npm install
```

### 5. Test Authentication
```bash
npm run dev
# Open http://localhost:5173
# Try registering a new account
# Try logging in
```

## Remaining Work

### Course Generation Polling
The course generation uses an event-driven workflow. The frontend needs to:
1. Call `POST /courses` to start generation
2. Receive `course_id` in response
3. Poll `GET /course-status/{courseId}` until status is "complete"
4. Then fetch the full course with `GET /course/{courseId}`

**Files to update:**
- `src/components/course/CourseCreationForm.tsx` - Add polling logic
- `src/components/course/GenerationProgress.tsx` - Show real-time status

### Frontend Hosting
- Create CloudFront + S3 Terraform module
- Set up deployment script
- Configure custom domain (optional)

## Testing Checklist

- [ ] User can register new account
- [ ] User receives email verification (or auto-confirmed in dev)
- [ ] User can login with email/password
- [ ] Protected routes require authentication
- [ ] API calls include Cognito tokens automatically
- [ ] Token refresh works (handled by Amplify)
- [ ] User can logout
- [ ] Chat functionality works
- [ ] Course generation works (with polling)
- [ ] Book upload works

## Known Issues / Notes

1. **Email Verification**: In dev, Cognito can be configured to auto-confirm emails. In prod, users will need to verify their email.

2. **Custom Attributes**: The `playbackSpeed` user preference may need to be stored differently since Cognito custom attributes require schema changes. Consider storing in DynamoDB or localStorage as fallback.

3. **Error Handling**: Cognito errors are now properly mapped in `authExecutor.ts` with user-friendly messages.

4. **Session Management**: Cognito handles token refresh automatically via Amplify. No manual refresh logic needed.

5. **API Gateway**: All endpoints now require authentication. Make sure Cognito is deployed before testing API calls.

## Troubleshooting

### "VITE_COGNITO_USER_POOL_ID is not set"
- Make sure `.env` file exists in `src/frontend/`
- Check that environment variables are prefixed with `VITE_`
- Restart dev server after changing `.env`

### "Network error" when calling API
- Check that API Gateway URL is correct
- Verify Cognito is deployed and configured
- Check browser console for CORS errors
- Verify API Gateway has Cognito authorizer configured

### "User not found" on login
- Make sure user is registered first
- Check that email verification is complete (if required)
- Verify Cognito User Pool is configured correctly

### Protected routes redirecting to login
- Check browser console for auth errors
- Verify Cognito session is valid
- Check that `ProtectedRoute` is checking session correctly

