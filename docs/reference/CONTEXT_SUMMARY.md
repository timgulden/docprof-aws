# DocProf AWS - Context Summary

_Last updated: 2025-12-26_

## Project Overview

**DocProf** is a Retrieval-Augmented Generation (RAG) platform that creates domain-specific expert systems by ingesting textbooks and educational materials. Each instance of DocProf is configured with a specific corpus to become an expert in that domain.

**This is the AWS-native serverless implementation** migrated from the local MAExpert codebase.

**M&A Expert** is this specific instance of DocProf, focused on teaching valuation and investment banking topics. The same DocProf platform can be loaded with different document sets to create other experts, such as:
- Computational Social Science Expert
- Data Visualization with Python Expert
- Or any other domain with appropriate textbooks

## Project Snapshot
- **Platform:** DocProf (RAG-based expert system framework)
- **Instance:** M&A Expert (valuation and investment banking focus)
- **Architecture:** AWS Serverless (Lambda, API Gateway, Aurora, Bedrock)
- **Goal:** Build a Retrieval-Augmented Generation (RAG) "M&A Expert" that teaches and quizzes users on valuation and investment banking topics using 3–5 core textbooks.
- **Modalities:** Conversational Q&A, adaptive courses (structured learning paths with sections), quizzes, and audio lectures (AI professor persona).
- **Initial Corpus:** Start with `source-docs/Valuation8thEd.pdf`; expand to additional textbooks after pipeline validation.
- **Data Store:** Aurora Serverless PostgreSQL with pgvector extension.

## Key Documents & Where to Start

### Essential Setup & Reference
| Purpose | Location | Notes |
|---------|----------|-------|
| **AWS Credentials Setup** | `docs/troubleshooting/AWS_Credentials_Troubleshooting.md` | Profile configuration, common issues, verification steps |
| **Frontend Access** | `FRONTEND_ACCESS.md` | How to run frontend locally, deployment strategy |
| **Quick Start** | `QUICK_START.md` | Essential documents, differences from MAExpert |

### Architecture & Design
| Purpose | Location | Notes |
|---------|----------|-------|
| Architecture principles (functional FP) | `docs/design-principles/functional-architecture-summary.md` | Defines pure logic layer, command/effect separation, interceptor usage |
| Interceptor reference | `docs/design-principles/interceptor-patterns.md` | Both stack-based and middleware-style patterns |
| FP to Serverless mapping | `docs/architecture/FP_to_Serverless_Mapping.md` | How MAExpert patterns map to AWS Lambda |

### Implementation Guides
| Purpose | Location | Notes |
|---------|----------|-------|
| MAExpert Reference | `../MAExpert/` | Working local implementation - DO NOT MODIFY |
| Course system | Event-driven Lambda architecture | See `docs/architecture/Course_Generator_Event_Driven_Plan.md` |

## Architecture at a Glance

### AWS Serverless Stack
- **Backend:** Lambda functions + API Gateway (replaces FastAPI)
- **Database:** Aurora Serverless PostgreSQL + pgvector (replaces local PostgreSQL)
- **LLM:** AWS Bedrock Claude (replaces Anthropic API)
- **Embeddings:** AWS Bedrock Titan (replaces OpenAI)
- **TTS:** AWS Polly Neural (replaces OpenAI TTS)
- **State:** DynamoDB for session/course state (replaces filesystem)
- **Storage:** S3 for documents (replaces local files)

### Functional Programming Patterns (Preserved from MAExpert)
- **Functional Core / Imperative Shell:** Logic layer returns `(new_state, commands)`; effects layer executes commands via Lambda
- **State Management:** Immutable Pydantic models (`model_copy`) for application state; no in-place mutation
- **Interceptors:** Middleware-style for command execution, stack-based for complex workflows
- **Storage:** Text/figure chunks with embeddings in Aurora pgvector; progress tracked in relational tables

## AWS Configuration

### Credentials & Access
- **AWS Profile:** `docprof-dev`
- **Region:** `us-east-1`
- **Account ID:** `176520790264`
- **Troubleshooting:** See `docs/troubleshooting/AWS_Credentials_Troubleshooting.md` for credential setup and common issues

**Quick setup:**
```bash
export AWS_PROFILE=docprof-dev
export AWS_DEFAULT_REGION=us-east-1
aws sts get-caller-identity  # Verify access
```

### Frontend Access Strategy

**Local Development (Current):**
- Frontend runs locally via `npm run dev` on **http://localhost:5173**
- Connects to AWS backend (API Gateway, Aurora, Bedrock)
- Configuration in `src/frontend/.env`

**AWS Deployment (Future):**
- S3 bucket `docprof-dev-frontend` exists but is currently empty
- CloudFront distribution not yet configured
- Will deploy when ready to share with external users

**To run frontend:**
```bash
cd src/frontend
npm run dev
# Open http://localhost:5173
```

### Backend Endpoints
- **API Gateway:** `https://evjgcsghvi.execute-api.us-east-1.amazonaws.com/dev`
- **Cognito Domain:** `https://docprof-dev-auth.auth.us-east-1.amazoncognito.com`
- **User Pool ID:** `us-east-1_JzXm5t3RT`
- **Client ID:** `547fdlbctm7ca93bcan5nlcc6o`

## Usage Tips for New Sessions
- Start by reading this document, then `docs/design-principles/functional-architecture-summary.md` to understand design constraints.
- When implementing features, align logic with the interceptor/command pattern; keep side effects confined to effects modules.
- The **MAExpert** codebase at `../MAExpert/` is the working reference implementation - DO NOT modify it.
- For AWS deployments, use the `docprof-dev` profile and refer to `AWS_Credentials_Troubleshooting.md` if issues arise.
- Frontend development: Run locally with `npm run dev`, connects to AWS backend automatically.
- Update the "Last updated" line whenever major context changes so future sessions know how fresh this summary is.

