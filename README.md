# Amazon AI Commerce Assistant 🛒🤖

> **Amazon HackOn 2025 — Reimagining Urgent Shopping**

---

## 📋 Problem Statement

**Amazon Now – Reimagining Urgent Shopping**

Quick-commerce customers are fundamentally different from traditional e-commerce customers. They often arrive with an immediate need and expect to complete their purchase within seconds, yet today's shopping experiences still rely heavily on search, browsing, and manual decision-making.

**How might we help customers discover, decide, and purchase what they need in the fastest and most effortless way possible?**

---

## 💡 Our Solution

A next-generation AI shopping consultant (Rufus) that replaces the traditional "search → browse → decide → buy" loop with a **single natural language conversation**. The user tells the AI what they need, the system consults, retrieves, filters, and builds a curated cart — all in seconds.

> *"I'm planning a movie night for 4 people, under $50, no nuts"*
> → AI asks 1 question → builds a cart with chips, chocolate, drinks — all nut-free, within budget, with explainable reasons.

---

## 🏗️ Architecture

- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, React Query.
- **Backend Orchestrator**: FastAPI, Uvicorn.
- **AI / Reasoning Layer**: Google ADK (`LlmAgent`) powered by **Google Gemini 2.5 Flash Lite**.
- **Specialized Agents**: 
  - **Cart Planning Agent**: Intelligently groups and constructs starter carts for events (e.g. Movie Nights, Camping Trips).
  - **Review Filter Agent**: Analyzes product review summaries to filter items based on nuanced user constraints (e.g., allergies, durability concerns).
  - **Recommendation Agent**: Pure Python rule-based system that maintains strict control over semantic retrieval actions.
- **Authentication**: AWS Cognito (Secure HttpOnly cookies + JWT).
- **Database**: AWS DynamoDB (Users, ChatSessions, Messages, Long-Term User Memory).
- **Retrieval System**: Pre-loaded metadata and embedding index for instant O(1) lookups and FAISS/Cosine similarity semantic search.

---

## 🚀 Key Features

### 1. Smart Conversational Commerce
Engage in natural, multi-turn conversations. The assistant understands broad goals ("I want to start running") and specific requests ("Find me a laptop under $800").

### 2. Intelligent Cart Planning
Simply say "I'm hosting a movie night for 4 people tonight", and the assistant will automatically generate a categorized starter cart (Snacks, Drinks, Accessories) matching your budget and dietary preferences. You can converse directly with the cart to refine it ("Remove anything over $40" or "Make sure everything is vegan").

### 3. Long-Term Memory
The assistant automatically extracts and remembers your persistent preferences across sessions. If you mention you are vegan or hate Apple products in one chat, it remembers that fact in all future sessions to proactively filter out irrelevant items.

### 4. Advanced Review Filtering
Instead of relying solely on tags, the assistant uses a dedicated Review Filter Agent to analyze thousands of summarized product reviews to ensure recommendations genuinely meet strict user constraints.

### 5. Latency Optimized
- **Parallel Context Loading**: DynamoDB state, memory, and chat history are loaded concurrently.
- **Pre-computed Metadata Index**: Eliminates the need for real-time S3 JSON parsing.
- **Decision Cache**: Redundant or identical queries bypass the LLM entirely, resulting in sub-second response times.
- **Asynchronous Persistence**: Database writes are offloaded to background tasks to return responses to the frontend instantly.
- **Robust JSON Parsing**: Regex-based extraction safely handles LLM formatting hallucinations and escape character typos.

---

## 🛠️ Quick Start Guide

### 1. Prerequisites
- Python 3.10+
- Node.js 18+
- [Google Gemini API Key](https://aistudio.google.com/)
- AWS Account with IAM credentials.

### 2. Environment Variables
Create a `.env` file in the root directory:
```env
# AWS Configuration
AWS_REGION="us-east-1"
AWS_ACCESS_KEY_ID="your-access-key"
AWS_SECRET_ACCESS_KEY="your-secret-key"

# Cognito Configuration
COGNITO_USER_POOL_ID="your-pool-id"
COGNITO_CLIENT_ID="your-client-id"
COGNITO_CLIENT_SECRET="your-client-secret"

# DynamoDB Tables
DYNAMODB_USERS_TABLE="Users"
DYNAMODB_SESSIONS_TABLE="ChatSessions"
DYNAMODB_MESSAGES_TABLE="Messages"
DYNAMODB_SAVED_PRODUCTS_TABLE="SavedProducts"

# Google AI
GOOGLE_API_KEY="your-gemini-api-key"
GEMINI_MODEL="gemini-2.5-flash-lite"
```

### 3. Running the Backend (FastAPI)
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

### 4. Running the Frontend (React)
Open a separate terminal and run:
```bash
cd frontend

# Install dependencies
npm install

# Start the Vite development server (runs on http://localhost:5173)
npm run dev
```

---

## 🔒 Security
- **JWT Verification**: Backend routes are strictly protected by Cognito JWT verification.
- **Data Isolation**: All DynamoDB queries enforce `user_id` validation so users can only access their own sessions and memory.
- **Agent Guardrails**: AI agents are isolated from executing system commands and restricted to structured JSON responses.
