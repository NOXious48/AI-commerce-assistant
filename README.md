# Personal AI Commerce Assistant - FastAPI Backend

This is the self-contained, from-scratch Python **FastAPI Backend** for the next-generation **Personal AI Commerce Assistant** powered by **Google GenAI SDK** (Gemini).

It acts as a household commerce manager, automating product search, managing user profiles (allergies, fitness goals, green/healthy modes), keeping track of shopping carts across sessions, and simulating weather/calendar triggers for proactive refills.

---

## 🛠️ Tech Stack & Architecture

- **Web Framework**: FastAPI (Uvicorn server)
- **AI Orchestrator**: Google GenAI SDK (`google-generativeai`)
- **Model**: `gemini-1.5-flash` (supports native python function/tool calling)
- **Database**: File-based `products.json` compiled with 2,100+ items across 7 core categories. Carts and sessions are handled in-memory.
- **Search Engine**: `search.py` (Hybrid: local keyword TF-IDF indexing + allergy exclusion filters, with hooks for Amazon OpenSearch connection).

---

## 📂 Project Structure

```
backend/
├── main.py              # FastAPI server entrypoint (defines routes)
├── agent.py             # Gemini agent wrapper, registers and manages tool loop
├── database.py          # Catalog generator & in-memory session states (carts, profiles)
├── search.py            # Hybrid search engine (local search & OpenSearch integrations)
├── schemas.py           # Pydantic models for API request/response validation
├── requirements.txt     # Backend python dependencies
├── run.sh               # Shell script to install dependencies and run the server
└── test_agent_dryrun.py # CLI script to test agent and tool executions directly
```

---

## 🚀 Getting Started

### 1. Configure API Key
Create a `.env` file in this directory or export your Gemini API key:
```bash
export GEMINI_API_KEY="your-api-key-here"
```

### 2. Run the Server
Use the provided startup script:
```bash
chmod +x run.sh
./run.sh
```
The server will start at `http://localhost:8000`. You can access the auto-generated documentation and test page at `http://localhost:8000/docs`.

---

## 🧪 Testing the Agent via CLI

You can perform a dry-run test of the agent's tool execution from your terminal without starting the server:

```bash
python3 test_agent_dryrun.py --api-key "your-api-key" --query "Recommend some breakfast spreads. Make sure they are peanut-free."
```

---

## 🛰️ REST API Endpoints

### 💬 Chat / Agent
- **`POST /api/chat`**: Handles the conversation. Executes the Gemini reasoning loop and processes tool calls automatically.
  - **Headers**: `x-gemini-key: <api_key>` (optional if `GEMINI_API_KEY` environment variable is set)
  - **Body**:
    ```json
    {
      "message": "User query here",
      "session_id": "session-unique-id"
    }
    ```

### 📦 Product Catalog
- **`GET /api/products`**: Search and list items. Supports category filter and automatically excludes active user profile allergens.
- **`GET /api/products/{productId}`**: Retrieve full details of a specific item.

### 👤 Profile Management
- **`GET /api/profile?session_id=...`**: Fetch active household parameters.
- **`POST /api/profile?session_id=...`**: Update allergies, budget, workout goals, and green/healthy modes.

### 🛒 Cart & Checkout
- **`GET /api/cart?session_id=...`**: View current items, subtotal, and budget checkpoints.
- **`POST /api/cart?session_id=...`**: Add or remove quantities.
- **`POST /api/checkout?session_id=...`**: Place the order, deduct stock, and return receipt.

### 🌤️ Simulator Triggers
- **`GET /api/simulator/weather`** / **`POST /api/simulator/weather`**
- **`GET /api/simulator/events`** / **`POST /api/simulator/events`**
- **`GET /api/simulator/inventory`** / **`POST /api/simulator/inventory`**
