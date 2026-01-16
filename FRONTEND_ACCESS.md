# Frontend Access Guide

## 🎯 How to Access the Frontend

The DocProf frontend is **not deployed to S3/CloudFront** - it runs **locally** during development.

### ✅ Correct Way to Access

**Run the frontend locally:**

```bash
cd src/frontend
npm run dev
```

Then open: **http://localhost:5173**

---

## 📋 Environment Setup

Make sure `src/frontend/.env` has the correct configuration:

```bash
# API Gateway
VITE_API_GATEWAY_URL=https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev

# Cognito
VITE_COGNITO_USER_POOL_ID=us-east-1_JzXm5t3RT
VITE_COGNITO_USER_POOL_CLIENT_ID=547fdlbctm7ca93bcan5nlcc6o
VITE_COGNITO_REGION=us-east-1
```

---

## 🚀 Deployment Status

### Currently Deployed ✅
- **Backend:** Lambda functions + API Gateway
- **Database:** Aurora PostgreSQL with pgvector
- **Course Creation Fix:** Deployed (v38)

### Not Yet Deployed ⏳
- **Frontend to S3/CloudFront:** Still runs locally
- **Production frontend build:** Not configured yet

---

## 📦 S3 Frontend Bucket

The `docprof-dev-frontend` S3 bucket exists but:
- ❌ **Not publicly accessible** (by design for security)
- ❌ **No files deployed** (frontend runs locally)
- ❌ **No CloudFront distribution** (not set up yet)

**This is intentional** - the frontend is for local development only at this stage.

---

## 🔧 To Deploy Frontend to AWS (Future)

When ready to deploy the frontend to production:

1. **Build the frontend:**
   ```bash
   cd src/frontend
   npm run build
   ```

2. **Deploy to S3:**
   ```bash
   aws s3 sync dist/ s3://docprof-dev-frontend/
   ```

3. **Set up CloudFront** (recommended) or enable S3 website hosting

4. **Update CORS** in API Gateway to allow CloudFront domain

---

## 📝 Testing the Course Creation Fix

Since the backend fix is deployed, test it via the local frontend:

1. **Start the frontend:**
   ```bash
   cd src/frontend
   npm run dev
   ```

2. **Open:** http://localhost:5173

3. **Create a course** and verify:
   - Sections are created (check database)
   - Course title is correct
   - No errors in CloudWatch logs

---

## 🔍 Why the Confusion?

The S3 bucket URL `http://docprof-dev-frontend.s3-website-us-east-1.amazonaws.com` exists because:
- Terraform configured it for **website hosting**
- But it's **blocked from public access** (secure by default)
- And **no files were ever deployed** to it

The frontend has always been running on **localhost:5173** during development.

---

**Summary:** Use **http://localhost:5173** (after `npm run dev`) to access the frontend!

