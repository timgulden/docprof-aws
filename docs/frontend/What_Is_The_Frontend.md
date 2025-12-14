# What Is The Frontend?

## Quick Answer

**Yes, it's a graphical web UI that runs in your browser!** It's a modern React web application with a full user interface - not command line tools.

## Where Does It Run?

### Development (Right Now)
- **Runs on your local machine** (your laptop)
- You start it with `npm run dev` in the `src/frontend/` directory
- Opens in your browser at `http://localhost:5173`
- **Frontend code runs in your browser** (client-side)
- **Backend runs on AWS** (Lambda, API Gateway, Aurora)

### Production (Later)
- **Frontend code deployed to AWS S3** (static file storage)
- **Served via CloudFront** (AWS CDN - content delivery network)
- **Users access it via a URL** (like `https://docprof.example.com`)
- **Still runs in the user's browser** (client-side)
- **Backend still runs on AWS** (Lambda, API Gateway, Aurora)

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│  User's Browser (Chrome, Firefox, Safari, etc.)        │
│                                                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │  React Frontend Application                     │  │
│  │  - Login/Register forms                          │  │
│  │  - Chat interface                                │  │
│  │  - Course generation                            │  │
│  │  - Book upload                                  │  │
│  │  - PDF viewer                                   │  │
│  └─────────────────────────────────────────────────┘  │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ HTTPS Requests
                  │ (API calls with Cognito tokens)
                  ▼
┌─────────────────────────────────────────────────────────┐
│  AWS Cloud                                              │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐                 │
│  │ API Gateway  │───▶│   Lambda     │                 │
│  │ (REST API)   │    │  Functions   │                 │
│  └──────────────┘    └──────┬───────┘                 │
│                             │                          │
│                    ┌────────▼────────┐                 │
│                    │  Aurora DB      │                 │
│                    │  DynamoDB       │                 │
│                    │  Bedrock        │                 │
│                    │  S3             │                 │
│                    └─────────────────┘                 │
└─────────────────────────────────────────────────────────┘
```

## What Does It Look Like?

The frontend is a **modern web application** with:

### Main Features:
1. **Login/Register Pages** - Email/password authentication
2. **Sources View** - List of uploaded books, upload new books
3. **Chat Interface** - Conversational Q&A with the AI expert
4. **Courses** - Generate and view structured learning courses
5. **Lectures** - Audio lectures with PDF viewer
6. **Quizzes** - Interactive quizzes

### UI Components:
- **Navigation bar** at the top with logo and menu items
- **Sidebar** for chat sessions
- **PDF viewer** for viewing source documents
- **Message bubbles** for chat conversations
- **Forms** for course creation and book upload
- **Cards** for displaying books and courses

### Design:
- **Modern, clean interface** using Tailwind CSS
- **Dark mode support** (follows system preference)
- **Responsive design** (works on desktop and mobile)
- **Professional styling** with icons from Lucide React

## How To Run It (Development)

### Prerequisites:
1. **Deploy backend infrastructure** (Cognito, API Gateway, etc.)
   ```bash
   cd terraform/environments/dev
   terraform apply
   ```

2. **Get configuration values** from Terraform outputs
   ```bash
   terraform output cognito_user_pool_id
   terraform output cognito_user_pool_client_id
   terraform output api_gateway_url
   ```

3. **Create `.env` file** in `src/frontend/`
   ```bash
   cd src/frontend
   cp .env.example .env
   # Edit .env with values from Terraform
   ```

4. **Install dependencies**
   ```bash
   npm install
   ```

5. **Start development server**
   ```bash
   npm run dev
   ```

6. **Open browser**
   - Navigate to `http://localhost:5173`
   - You'll see the login page
   - Register a new account or login
   - Explore the interface!

## What Happens When You Run It?

1. **Vite dev server starts** on your machine (port 5173)
2. **React app loads** in your browser
3. **Amplify configures** Cognito authentication
4. **API client connects** to API Gateway (on AWS)
5. **You interact** with the UI in your browser
6. **API calls go** from your browser → API Gateway → Lambda → Database
7. **Responses come back** and update the UI

## Key Points

✅ **Graphical UI** - Full web application, not command line  
✅ **Runs in browser** - Client-side React application  
✅ **Development** - Runs locally, connects to AWS backend  
✅ **Production** - Deployed to S3+CloudFront, still runs in browser  
✅ **Backend on AWS** - Lambda, API Gateway, Aurora, etc.  
✅ **Real-time** - Updates as you interact with it  

## Current Status

**Frontend code is ready**, but you need to:
1. ✅ Deploy Cognito infrastructure (`terraform apply`)
2. ✅ Set up `.env` file with configuration
3. ✅ Install dependencies (`npm install`)
4. ✅ Start dev server (`npm run dev`)

Then you can **open it in your browser** and see the full UI!

## Example User Flow

1. **Open browser** → Navigate to `http://localhost:5173`
2. **See login page** → Beautiful form with email/password fields
3. **Register account** → Enter email, password, confirm password
4. **Login** → Enter credentials, get authenticated
5. **See main interface** → Navigation bar, sources view
6. **Upload book** → Click "Upload", select PDF file
7. **Chat with AI** → Click "Chat", ask questions
8. **Generate course** → Click "Courses", create new course
9. **View course** → See structured learning path

All of this happens in your **web browser** with a **graphical interface**!

