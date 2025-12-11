# UI Setup Quick Start

**For new chat sessions focused on UI development**

## 🎯 Essential Documents (In Order)

1. **`docs/UI_Setup_Context.md`** ⭐ START HERE
   - Complete context for UI work
   - API endpoints, database schema, what's working
   - Code locations, priorities

2. **`docs/reference/CONTEXT_SUMMARY.md`**
   - Project overview
   - What DocProf is and how it works
   - Key features and goals

3. **`docs/architecture/FP_to_Serverless_Mapping.md`**
   - How backend architecture works
   - Understanding Lambda handlers and API Gateway
   - Effects layer patterns

4. **`docs/deployment/System_Ready.md`**
   - Current deployment status
   - What's working vs what's pending

## 🔗 Quick Reference

### API Gateway
- **Base URL**: Check `terraform/environments/dev/terraform.tfstate` or run:
  ```bash
  cd terraform/environments/dev
  terraform output api_gateway
  ```
- **Endpoints**: See `docs/UI_Setup_Context.md` for available endpoints

### Frontend Location
- **AWS Frontend**: `src/frontend/` (to be updated)
- **Reference**: `../MAExpert/mna-expert-frontend/` (original React app)

### Backend Status
- ✅ Infrastructure deployed
- ✅ Document ingestion working
- ✅ Database schema ready
- 🚧 Chat/Course APIs pending (need Lambda handlers)

## 📝 What to Tell the New Chat

> "I'm setting up the React frontend to work with the AWS backend. Please reference:
> 1. `docs/UI_Setup_Context.md` for complete context
> 2. `docs/reference/CONTEXT_SUMMARY.md` for project overview  
> 3. `docs/architecture/FP_to_Serverless_Mapping.md` for backend architecture
> 
> The backend infrastructure is deployed and ingestion is working. I need help connecting the React frontend to the API Gateway endpoints and implementing the chat/course features."

## 🚀 Current Status

- **Ingestion**: Running (Valuation book being processed)
- **Backend**: Ready (Lambda, API Gateway, Aurora)
- **Frontend**: Needs API integration

---

**Created**: December 11, 2025  
**Purpose**: Quick reference for starting UI work in new chat sessions

