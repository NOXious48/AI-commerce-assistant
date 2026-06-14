# AI Commerce Assistant - Technical Architecture & Overview

This document provides a comprehensive technical overview of the AI Commerce Assistant project. It is designed to share with AI agents (like ChatGPT) to quickly onboard them to the codebase structure, tech stack, and multi-agent architecture.

---

## 1. High-Level Tech Stack

### Backend
- **Framework**: FastAPI (Python)
- **Server**: Uvicorn
- **Database**: AWS DynamoDB (Boto3)
- **Authentication**: AWS Cognito (Boto3, python-jose for JWT validation)
- **Vector Search**: FAISS (Facebook AI Similarity Search)
- **Embeddings**: SentenceTransformers (`all-MiniLM-L6-v2`)

### AI & LLM Architecture
- **Model**: Google Gemini (`gemini-2.5-flash`)
- **SDKs**: `google-genai` and `google.adk` (Agent Development Kit)
- **Paradigm**: Multi-Agent Orchestration (Routing + Domain Agents)

### Frontend
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **Routing**: React Router DOM
- **State Management**: React Context (`AuthContext`)

---

## 2. Multi-Agent System Architecture

The core of the application relies on a multi-agent orchestration pattern where a central "Reasoning Agent" parses intent and delegates to specialized sub-agents.

### A. Conversation Agent (The Orchestrator)
- **Location**: `services/gemini_client.py`, triggered by `routers/chat_router.py`
- **Implementation**: Uses Google ADK (`LlmAgent`, `Runner`, `InMemorySessionService`).
- **Role**: Analyzes the user's input against the conversation history and user memory.
- **Output**: Returns a strict, robust JSON schema containing:
  - `intent`: (e.g., `recommendation_request`, `cart_planning`, `general_conversation`)
  - `response`: The conversational text for the user.
  - `recommendation_action`: `none`, `retrieve`, `refresh`, or `invalidate`.
  - `cart_action`: `none`, `create_cart`, `update_cart`, or `clear_cart`.
  - `updated_state`: A JSON object tracking goal, budget, dietary constraints, allergens, etc.

### B. Recommendation Agent
- **Location**: `recommendation_agent.py`
- **Implementation**: Pure Python (Non-LLM rule engine).
- **Role**: Analyzes the `updated_state` and decides exactly what parameters to send to the Retrieval Engine. Manages the "Recommendation Workspace".

### C. Retrieval Engine
- **Location**: `retrieval.py`
- **Role**: Performs fast vector similarity search using FAISS. Searches against a local catalog of ~2,100 pre-embedded Amazon products.

### D. Review Filter Agent
- **Location**: `review_filter_agent.py`
- **Implementation**: LLM-based (Gemini).
- **Role**: Takes the top 100 products from FAISS and strictly filters them against the user's hard constraints (e.g., budget limits, dietary preferences, allergens, avoided brands). It returns a list of `approved_products` and `rejected_products`.

### E. Cart Planning Agent
- **Location**: `cart_planning_agent.py`
- **Implementation**: LLM-based (Gemini).
- **Role**: Creates and manages intelligent shopping carts (e.g., "Movie Night Cart"). It evaluates the `approved_products` and intelligently selects 5-8 items across relevant categories (e.g., Snacks, Drinks) to build a cohesive cart.

---

## 3. Core Data Flow (The Chat Loop)

When a user sends a message via the UI (`POST /api/chat`):

1. **State Hydration**: FastAPI loads the user's long-term memory, current consultation state, and previous chat messages from DynamoDB.
2. **Intent Parsing**: The **Conversation Agent** processes the message and outputs a JSON decision routing matrix.
3. **Product Retrieval**: If the decision matrix includes `recommendation_action=retrieve`, the **Retrieval Engine** searches FAISS, and the **Review Filter Agent** sanitizes the results. The UI is updated with these approved products.
4. **Cart Operations**: If the decision matrix includes `cart_action=update_cart`, the **Cart Planning Agent** takes the newly approved products and adds the best matches to the user's cart.
5. **Database Persistence**: The new chat messages, updated state, and cart are saved back to DynamoDB asynchronously via FastAPI `BackgroundTasks`.
6. **Long-term Memory (Background)**: Every 5 messages, a background LLM task parses the history to extract persistent preferences (e.g., "User is vegan") and updates the DynamoDB User Profile.

---

## 4. Key Engineering & Reliability Features

### 1. Robust JSON Parsing & Circuit Breaker
Gemini structured outputs can occasionally fail or return wrapped markdown. `services/gemini_client.py` implements a highly robust 5-layer extraction system:
- **Layer 1**: Native ADK `.parsed` object.
- **Layer 2**: Direct `json.loads`.
- **Layer 3 & 4**: Regex extraction with automatic JSON escape-sequence fixing.
- **Layer 5**: Graceful Fallback (returns safe conversational defaults).
- **Circuit Breaker**: If the Gemini API fails entirely (e.g., rate limits, network failure), a circuit breaker opens and returns safe fallbacks to prevent cascading server crashes.

### 2. Security & Authentication
- **Cognito Integration**: Full flow including Signup, Login, Email Verification (`/confirm`), Forgot Password, and Resend Code.
- **JWT Handling**: Access Tokens are kept in memory on the React frontend.
- **Secure Refresh**: Refresh tokens are stored in `HttpOnly`, `Secure`, `SameSite=strict` cookies, protecting against XSS attacks. The `/api/auth/refresh` endpoint handles silent token renewals.

### 3. Image Proxying
- **Location**: `chat_agent.py` -> `/api/image-proxy`
- **Role**: Proxies Amazon product images to bypass browser CORS and hotlink protection, allowing the UI to display external product photos seamlessly.

---

## 5. File Structure Overview

### Backend (Root)
- `chat_agent.py` - The FastAPI entry point. Contains the massive `SYSTEM_PROMPT`.
- `schemas.py` - Pydantic models for the Conversation Agent output.
- `routers/`
  - `auth_router.py` - Handles Cognito authentication endpoints.
  - `chat_router.py` - Core chat loop, agent orchestration, background tasks.
  - `cart_router.py` - Manual cart manipulation endpoints.
  - `user_router.py` - User preference management endpoints.
- `services/`
  - `gemini_client.py` - Singleton wrapper for Google ADK and Circuit Breaker logic.
- `auth/`
  - `cognito_service.py` - AWS Cognito Boto3 wrapper.
  - `jwt_verifier.py` - Validates JWT signatures via JWKS.
- `db/`
  - `dynamo_service.py` - DynamoDB data access layer.

### Frontend (`frontend/src/`)
- `App.tsx` - Route definitions (`/login`, `/signup`, `/verify`, `/`).
- `context/AuthContext.tsx` - Manages auth state, tokens, and API calls.
- `pages/`
  - `Dashboard.tsx` - Main chat UI, product grid, and cart sidebar.
  - `Login.tsx` / `Signup.tsx` / `Verify.tsx` - Auth flow screens.

---

## 6. Known Database Tables (DynamoDB)
- **Users**: Stores `user_id` (partition key), `email`, `full_name`, and long-term `preferences`.
- **ChatSessions**: Stores `user_id` (PK) and `session_id` (SK) for chat histories.
- **Messages**: Stores individual chat turns. `session_id` (PK), `timestamp` (SK).
- **SavedProducts**: Tracks products the user has manually "liked" or saved.
