# Frontend Environment Variables Setup

## Required Environment Variables

Create a `.env` file in `src/frontend/` with the following variables:

```bash
VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
VITE_COGNITO_USER_POOL_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_API_GATEWAY_URL=https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/dev
VITE_AWS_REGION=us-east-1
```

## Getting Values from Terraform

After deploying the infrastructure, get the values:

```bash
cd terraform/environments/dev
terraform output cognito_user_pool_id
terraform output cognito_user_pool_client_id
terraform output api_gateway_url
```

Copy these values into your `.env` file.

## Important Notes

1. **VITE_ Prefix**: All environment variables must be prefixed with `VITE_` for Vite to expose them to the frontend code.

2. **Restart Dev Server**: After changing `.env`, restart the Vite dev server (`npm run dev`).

3. **Git Ignore**: The `.env` file should be in `.gitignore` (it contains sensitive values). Use `.env.example` as a template.

4. **Region**: Default is `us-east-1`. Change if your infrastructure is in a different region.

