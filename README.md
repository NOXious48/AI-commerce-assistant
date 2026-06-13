# AI Commerce Assistant 🛍️🤖

A production-ready, full-stack AI shopping assistant that curates Amazon products using Retrieval-Augmented Generation (RAG). Built with a modern **React SPA** frontend and a **FastAPI** backend, backed by **AWS DynamoDB**, **AWS Cognito**, and **AWS S3**.

## 🏗️ Architecture

- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, React Router, React Query.
- **Backend**: FastAPI, Uvicorn, LangChain.
- **Authentication**: AWS Cognito (Secure HttpOnly cookies + JWT).
- **Database**: AWS DynamoDB (Users, ChatSessions, Messages, SavedProducts).
- **Storage**: AWS S3 (Product catalogs, Embeddings).
- **AI / RAG**: Local LLMs via Ollama, FAISS vector store.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.ai/) installed and running locally.
- AWS Account with IAM credentials.

### 2. AWS Setup
Ensure you have the following resources created in AWS:
- **Cognito User Pool** and App Client.
- **DynamoDB Tables**: `Users`, `ChatSessions`, `Messages`, `SavedProducts` (all with `id` or `session_id` partition keys).
- **S3 Bucket** containing your product data and `.npy` embeddings.
- **IAM User** with permissions for Cognito, DynamoDB, and S3.

### 3. Environment Variables
Create a `.env` file in the root directory:
```env
AWS_REGION="us-east-1"
AWS_ACCESS_KEY_ID="your-access-key"
AWS_SECRET_ACCESS_KEY="your-secret-key"

COGNITO_USER_POOL_ID="your-pool-id"
COGNITO_CLIENT_ID="your-client-id"
COGNITO_CLIENT_SECRET="your-client-secret"

DYNAMODB_USERS_TABLE="Users"
DYNAMODB_SESSIONS_TABLE="ChatSessions"
DYNAMODB_MESSAGES_TABLE="Messages"
DYNAMODB_SAVED_PRODUCTS_TABLE="SavedProducts"

OLLAMA_MODEL="qwen2.5:7b" # Or whichever model you are using
```

### 4. Running the Backend (FastAPI)
Open a terminal and run:
```bash
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Start the server (runs on http://localhost:8000)
python chat_agent.py
```

### 5. Running the Frontend (React)
Open a separate terminal and run:
```bash
cd frontend

# Install dependencies
npm install

# Start the Vite development server (runs on http://localhost:5173)
npm run dev
```

### 6. Running the Local LLM
Ensure Ollama is running in the background:
```bash
ollama serve
# Make sure you have pulled your target model:
# ollama pull qwen2.5:7b
```

---

## 💻 Features

- **Secure Authentication**: Full signup, login, and silent token refresh flows using AWS Cognito.
- **Persistent Chat History**: All conversations are stored in DynamoDB and grouped by session.
- **Smart Recommendations**: Uses FAISS vector search to find relevant products from S3 and feeds them to the LLM to generate contextual shopping advice.
- **Modern UI**: A responsive, dark-mode inspired chat interface with dedicated product display panels.
