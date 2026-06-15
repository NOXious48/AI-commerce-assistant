# System Architecture — AI Commerce Assistant

## Problem Statement

**Amazon Now – Reimagining Urgent Shopping**

Quick-commerce customers are fundamentally different from traditional e-commerce customers. They often arrive with an immediate need and expect to complete their purchase within seconds, yet today's shopping experiences still rely heavily on search, browsing, and manual decision-making.

**How might we help customers discover, decide, and purchase what they need in the fastest and most effortless way possible?**

---

## Our Solution

An AI-powered conversational shopping consultant (Rufus) that replaces the traditional "search → browse → decide → buy" loop with a single natural language conversation that understands your goal, asks the right questions, and builds a curated cart automatically.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React SPA)                      │
│  ┌──────────┐ ┌──────────────┐ ┌───────────┐ ┌──────────────┐  │
│  │  Header  │ │  AI Drawer   │ │  Product  │ │    Cart      │  │
│  │  Search  │ │  (Rufus)     │ │  Cards    │ │    Page      │  │
│  └──────────┘ └──────────────┘ └───────────┘ └──────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │           Recommendation Shelves (Dynamic)                │   │
│  │           "Why Recommended" Badges                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────┘
                              │ REST API
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND                               │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   ORCHESTRATOR AGENT                         │  │
│  │  • Intent Parsing (Gemini LLM)                              │  │
│  │  • Domain Management                                        │  │
│  │  • Pipeline Routing                                         │  │
│  │  • Fast-Intent Detection (regex, skips LLM)                 │  │
│  └────────────┬───────────────────────────────────┬───────────┘  │
│               │                                   │               │
│    ┌──────────▼──────────┐          ┌─────────────▼───────────┐  │
│    │   PLANNING PIPELINE  │          │  CONVERSATION PIPELINE   │  │
│    │                      │          │                          │  │
│    │  ┌────────────────┐  │          │  ┌────────────────────┐  │  │
│    │  │ Planning Agent │  │          │  │ Action Context     │  │  │
│    │  │ (Gemini LLM)   │  │          │  │ Builder            │  │  │
│    │  └───────┬────────┘  │          │  └─────────┬──────────┘  │  │
│    │          ▼           │          │            ▼              │  │
│    │  ┌────────────────┐  │          │  ┌────────────────────┐  │  │
│    │  │ Cart Planner   │  │          │  │ Conversation Agent │  │  │
│    │  │ (Gemini LLM)   │  │          │  │ (Gemini LLM)       │  │  │
│    │  └───────┬────────┘  │          │  └────────────────────┘  │  │
│    │          ▼           │          │                          │  │
│    │  Category Targets    │          └──────────────────────────┘  │
│    └──────────┬───────────┘                                       │
│               ▼                                                   │
│    ┌──────────────────────────────────────────────────────────┐  │
│    │              RECOMMENDATION PIPELINE                       │  │
│    │                                                            │  │
│    │  ┌─────────────────┐    ┌─────────────────────────────┐   │  │
│    │  │ Constraint      │    │ Recommendation Agent         │   │  │
│    │  │ Resolver        │    │ (FAISS Semantic Search)      │   │  │
│    │  │ (Gemini LLM)    │    │ • Embeds query via MiniLM    │   │  │
│    │  └────────┬────────┘    │ • Cosine similarity search   │   │  │
│    │           │             │ • Returns top-100 candidates  │   │  │
│    │           ▼             └──────────────┬──────────────┘   │  │
│    │  Constraint Snapshot                   │                   │  │
│    │  (budget, dietary,                     ▼                   │  │
│    │   brands, features)    ┌─────────────────────────────┐   │  │
│    │           │            │ Review Agent                  │   │  │
│    │           └───────────▶│ • Hard filtering (budget,     │   │  │
│    │                        │   dietary, brand avoidance)   │   │  │
│    │                        │ • Scoring & confidence        │   │  │
│    │                        │ • Diversity guard             │   │  │
│    │                        │ • Approval/rejection reasons  │   │  │
│    │                        └──────────────┬──────────────┘   │  │
│    │                                       ▼                   │  │
│    │                        ┌─────────────────────────────┐   │  │
│    │                        │ Approved Products            │   │  │
│    │                        │ (with explainable reasons)   │   │  │
│    │                        └──────────────┬──────────────┘   │  │
│    └───────────────────────────────────────┼──────────────────┘  │
│                                            ▼                      │
│    ┌──────────────────────────────────────────────────────────┐  │
│    │                    CART AGENT                              │  │
│    │  • Adds approved products to domain cart                  │  │
│    │  • Rigid skip rule (user-removed items never re-added)    │  │
│    │  • Remove by characteristic (natural language)            │  │
│    │  • Quantity management                                    │  │
│    └──────────────────────────────────────────────────────────┘  │
│                                                                   │
│    ┌──────────────────────────────────────────────────────────┐  │
│    │                 WORKSPACE MANAGER                          │  │
│    │  • Loads/persists AgentExecutionContext from DynamoDB      │  │
│    │  • Workspace versioning (keeps last 5 per domain)         │  │
│    │  • Garbage collection                                     │  │
│    │  • Domain invalidation                                    │  │
│    └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA & SERVICES LAYER                        │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │  DynamoDB   │  │  FAISS Index │  │  Product Data (Local)   │  │
│  │             │  │  (In-Memory) │  │                          │  │
│  │  • Users    │  │              │  │  • embeddings.npy        │  │
│  │  • Sessions │  │  2100 x 384  │  │  • products_catalog     │  │
│  │  • Messages │  │  float32     │  │  • products_metadata     │  │
│  │  • Saved    │  │  normalized  │  │  • review_summaries      │  │
│  │    Products │  │              │  │  • products_reviews      │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
│                                                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │  AWS        │  │  Google      │  │  SentenceTransformer    │  │
│  │  Cognito    │  │  Gemini      │  │  all-MiniLM-L6-v2       │  │
│  │  (Auth)     │  │  2.5 Flash   │  │  (Query Embedding)      │  │
│  └─────────────┘  └──────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Responsibilities (Strict Contracts)

| Agent | Responsibility | NOT Responsible For |
|-------|---------------|---------------------|
| **Orchestrator** | Intent parsing, domain routing, pipeline coordination | Product retrieval, cart mutations, response generation |
| **Planning Agent** | Extract event/goal, generate strategy & assumptions | Retrieval, filtering, cart operations |
| **Cart Planner** | Generate category targets with budget allocation | Product selection, approval decisions |
| **Recommendation Agent** | FAISS semantic search, return candidate pool | Filtering, scoring, cart operations |
| **Constraint Resolver** | Normalize dietary/budget/brand constraints | Retrieval, approval decisions |
| **Review Agent** | Filter candidates, score, approve/reject with reasons | Retrieval, cart operations, response text |
| **Cart Agent** | Execute cart mutations (add/remove/clear/replace) | Retrieval, recommendations, response text |
| **Conversation Agent** | Generate natural response, extract preferences | Retrieval, cart operations, approval decisions |
| **Workspace Manager** | Load/persist context, versioning, garbage collection | Business logic, agent decisions |

---

## Data Flow Per Message

```
User Message
    │
    ▼
┌─── Parallel DB Load (messages + session) ───┐
│                                              │
▼                                              ▼
Messages                              Session State
    │                                      │
    └──────────┬───────────────────────────┘
               ▼
    AgentExecutionContext (hydrated)
               │
               ▼
    ┌─── Fast Intent Check ───┐
    │   (regex patterns)       │
    │   Greetings → converse   │
    │   "yes" → plan_event     │
    │   "clear cart" → clear   │
    └──────────┬───────────────┘
               │ (miss)
               ▼
    Gemini Intent Parser
    → action, domain, target_category
               │
               ▼
    ┌─── Action Router ────────────────────────┐
    │                                           │
    │  converse → ConversationAgent only        │
    │  recommend → Retrieve → Review → Cart     │
    │  plan_event → Plan → CartPlan → Full pipe │
    │  product_info → Lookup metadata+reviews   │
    │  add/remove/clear → CartAgent             │
    │                                           │
    └───────────────┬───────────────────────────┘
                    │
                    ▼
    ┌─── Post-Processing ──────────────────────┐
    │  • If converse + preferences + no products│
    │    → Auto-trigger plan_event pipeline     │
    │  • Merge updated_state                    │
    │  • Handle goal abandonment                │
    └───────────────┬───────────────────────────┘
                    │
                    ▼
    ConversationAgent (generates response)
                    │
                    ▼
    ┌─── Background Tasks ─────────────────────┐
    │  • Save messages (non-blocking)           │
    │  • Extract long-term memory               │
    │  • Update session title                   │
    └───────────────────────────────────────────┘
                    │
                    ▼
    JSON Response → Frontend
    (reply, products, cart_items, active_domains)
```

---

## Key Design Decisions

### 1. Consultation-First Approach
The system asks questions BEFORE recommending. When a user mentions an event or goal, the ConversationAgent gathers preferences (budget, dietary, brand) first. Only after the user provides context does the pipeline trigger.

### 2. Domain Isolation
Each shopping goal (movie night, gaming laptop) gets its own domain with independent:
- Recommendation workspace (versioned)
- Cart workspace
- Planning workspace

Multiple domains can coexist. Topic switches replace the shelf without destroying old workspace data.

### 3. Explainable Recommendations
Every approved product carries `approval_reasons` (e.g., "Fits your budget", "Highly rated") which are displayed as green badges on the UI. Users know WHY something was recommended.

### 4. Review Agent as Gatekeeper
Products must pass through the Review Agent before being shown. It enforces:
- Hard budget limits
- Dietary/allergen constraints
- Brand avoidance
- Diversity (max 3 products per brand)

### 5. Workspace Versioning
Each retrieval creates a new version. The system keeps the last 5 versions per domain and garbage-collects older ones to prevent DynamoDB bloat.

### 6. Rigid Skip Rule
If a user manually removes a product, the AI will never re-add it. This builds trust — the user's explicit choices always override AI decisions.

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS | Amazon-style SPA |
| API | FastAPI, Uvicorn | Async REST API |
| LLM | Google Gemini 2.5 Flash Lite | Intent parsing, planning, conversation |
| Embedding | SentenceTransformer (all-MiniLM-L6-v2) | Query embedding for search |
| Vector Search | NumPy cosine similarity (in-memory) | Semantic product retrieval |
| Database | AWS DynamoDB | Sessions, users, messages, preferences |
| Auth | AWS Cognito | JWT + HttpOnly cookies |
| Deployment | AWS EC2 (t3.micro) | Single-instance serving |

---

## Scalability Path

| Current (Prototype) | Production | Future |
|---------------------|-----------|--------|
| In-memory FAISS | OpenSearch Serverless | Distributed vector DB |
| Single process | Multi-worker Uvicorn | ECS/Fargate containers |
| No caching | Redis/ElastiCache | CDN + edge caching |
| Synchronous LLM | Streaming (SSE) | Async agent workers |
| Single DynamoDB table | DAX caching layer | Multi-region replication |
| 2,100 products | 100K+ products | Millions |

---

## Security

- JWT verification via Cognito JWKS (24h cache)
- Access tokens in memory (never localStorage)
- Refresh tokens in HttpOnly + Secure + SameSite=strict cookies
- All DB queries enforce user_id from verified JWT
- Rate limiting on auth endpoints
- Agent outputs restricted to structured JSON
- No user input ever used as code execution
