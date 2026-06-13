# Transformation Plan: Product Recommender → AI Shopping Consultant

## Current State Summary

The application currently has TWO parallel implementations:

1. **`main.py` (Gemini Agent)** — Uses Google Gemini with function-calling tools, in-memory product DB, static HTML
2. **`chat_agent.py` (Production)** — Uses Ollama (qwen2.5:7b) + RAG vector search + React frontend + Cognito auth + DynamoDB

**The production path (`chat_agent.py`)** is the one that needs transformation. It currently:
- Receives a user message
- Immediately performs semantic vector search (retrieval.py)
- Injects top-K products as context into the LLM prompt
- Returns products + AI response in one shot

**This is a "search engine with chat" — NOT a shopping consultant.**

---

## Problem Statement

The current flow is:
```
User: "I need a laptop"
→ Immediate vector search for "laptop"
→ Returns 6 products + generic LLM commentary
```

The desired flow is:
```
User: "I need a laptop"
→ AI: "What's your budget? Usage? Preferred OS?"
→ User: "Coding, $1500, Linux preferred"
→ AI: "Battery life important? Brand preferences?"
→ User: "Yes, no preference"
→ Confidence > threshold → THEN retrieve products
→ AI provides grounded, reasoned recommendations with trade-offs
```

---

## Architecture Changes Required

### Phase 1: Backend — Consultation Engine (Core)

#### 1.1 New File: `consultation_state.py`
Manages structured consultation state per session.

```python
# Consultation state schema
{
    "session_id": str,
    "user_id": str,
    "goal": str | None,
    "budget": {"min": float, "max": float} | None,
    "preferred_brands": [],
    "avoided_brands": [],
    "must_have_features": [],
    "nice_to_have_features": [],
    "dietary_preferences": [],
    "allergens": [],
    "usage_context": str | None,
    "target_audience": str | None,  # "for me", "gift for wife", "for kids"
    "urgency": str | None,          # "immediate", "researching", "comparing"
    "confidence_score": float,       # 0.0 - 1.0
    "mode": str,                     # "consultation", "retrieval", "comparison", "research"
    "retrieval_triggered": bool,
    "questions_asked": int,
    "consultation_history": []       # track what was asked/answered
}
```

#### 1.2 New File: `confidence_engine.py`
Evaluates whether enough info exists for quality recommendations.

```python
class ConfidenceEngine:
    def calculate_confidence(state: ConsultationState) -> float:
        """
        Scoring:
        - goal identified: +25%
        - budget specified: +20%
        - usage context clear: +20%
        - must-have features: +15%
        - audience clear: +10%
        - dietary/allergy noted (if food): +10%
        """
    
    def should_retrieve(state) -> bool:
        """Returns True if confidence >= threshold (default 0.70)"""
    
    def get_missing_info(state) -> List[str]:
        """Returns list of info gaps for the AI to ask about"""
```

#### 1.3 New File: `consultant_agent.py`
Replaces the current "dumb retrieval + LLM" pattern with a consultation-first agent.

```python
class ShoppingConsultant:
    """
    Orchestrates the consultation workflow:
    1. Analyze user message
    2. Update consultation state
    3. Evaluate confidence
    4. IF confidence < threshold: generate clarifying questions
    5. IF confidence >= threshold: trigger retrieval → generate recommendations
    """
    
    def process_message(self, session_id, user_id, message, history) -> ConsultantResponse:
        # 1. Load/create consultation state
        # 2. Classify intent (new query, answer to question, comparison request, research request)
        # 3. Extract structured info from message → update state
        # 4. Check confidence
        # 5. Choose action path
        pass
```

#### 1.4 Modify: `routers/chat_router.py`
Replace the current flow with consultation-first logic.

**Current:**
```python
message → vector_search → inject_products → LLM → response
```

**New:**
```python
message → consultant_agent.process(message, state)
  → IF consulting: return {reply: questions, products: [], state_update}
  → IF retrieving: return {reply: recommendations, products: [...], state_update}
  → IF comparing: return {reply: comparison, products: [A, B], state_update}
  → IF researching: return {reply: education, products: [], state_update}
```

#### 1.5 New File: `memory_service.py`
Handles personalization and learning across sessions.

```python
class MemoryService:
    """
    Stores and retrieves user preferences learned over time.
    Persisted in DynamoDB under user profile.
    """
    def get_learned_preferences(user_id) -> Dict
    def update_from_consultation(user_id, consultation_state) -> None
    def get_greeting_context(user_id) -> str  # "Last time you preferred gluten-free..."
```

---

### Phase 2: LLM Prompt Engineering

#### 2.1 New System Prompt (replaces current SYSTEM_PROMPT)

The new prompt instructs the LLM to:
- Act as a shopping consultant, NOT a search engine
- Ask clarifying questions before recommending
- Maintain consultation context
- Only recommend after sufficient information
- Explain trade-offs and reasoning
- Support comparison and research modes

#### 2.2 Mode-Specific Prompts

| Mode | Behavior |
|------|----------|
| `consultation` | Ask questions, gather requirements |
| `retrieval` | Products retrieved, provide grounded recommendations with reasoning |
| `comparison` | Side-by-side analysis with pros/cons/verdict |
| `research` | Educational content about product categories |

---

### Phase 3: Frontend — Three-Panel Layout Enhancement

#### 3.1 Modify: `Dashboard.tsx`
Add dynamic consultation state panel above products.

#### 3.2 New Component: `ConsultationPanel.tsx`
Shows discovered preferences dynamically:
```
┌─────────────────────────────────┐
│ 🎯 Goal: Gaming Laptop          │
│ 💰 Budget: $1200-$1500          │
│ ✓ Must: RTX 4060+, 16GB RAM     │
│ ✓ Nice: RGB keyboard            │
│ ✗ Avoid: Lenovo                  │
│ 📊 Confidence: 78%              │
└─────────────────────────────────┘
```

#### 3.3 Modify: `ProductPanel.tsx`
- Products only appear AFTER retrieval is triggered
- Show "AI is gathering your requirements..." state
- Support comparison view (side-by-side cards)

#### 3.4 Modify: `ChatPanel.tsx`
- Add quick-reply buttons for common answers (budget ranges, use cases)
- Show consultation progress indicator
- Support research mode (educational content without products)

---

### Phase 4: API Contract Changes

#### New Response Shape:
```json
{
  "reply": "string (AI message)",
  "products": [...],
  "consultation_state": {
    "goal": "Gaming laptop",
    "budget": {"min": 1200, "max": 1500},
    "must_have_features": ["RTX 4060+"],
    "confidence_score": 0.78,
    "mode": "consultation"
  },
  "suggested_replies": [
    "Under $1000",
    "$1000-$1500", 
    "$1500-$2000",
    "No budget limit"
  ],
  "retrieval_triggered": false
}
```

---

### Phase 5: Comparison & Research Modes

#### 5.1 Comparison Mode
Triggered by: "Compare X and Y", "Which is better, A or B?"

Response includes:
- Feature-by-feature comparison table
- Pros/cons for each
- Review sentiment differences
- Value analysis
- Final recommendation based on user's stated needs

#### 5.2 Research Mode
Triggered by: "What should I know about...", "Explain the difference between..."

Response includes:
- Educational content
- Key considerations before buying
- Common pitfalls
- No product retrieval (or optional "show me examples" after education)

---

## Implementation Order (Priority)

| # | Task | Files | Effort |
|---|------|-------|--------|
| 1 | Create `consultation_state.py` | New file | Small |
| 2 | Create `confidence_engine.py` | New file | Medium |
| 3 | Create `consultant_agent.py` | New file | Large |
| 4 | Create new system prompt | In consultant_agent.py | Medium |
| 5 | Modify `chat_router.py` | Existing | Medium |
| 6 | Create `memory_service.py` | New file | Medium |
| 7 | Add `ConsultationPanel.tsx` | New component | Small |
| 8 | Modify `Dashboard.tsx` | Existing | Small |
| 9 | Modify `ChatPanel.tsx` (quick replies) | Existing | Medium |
| 10 | Modify `ProductPanel.tsx` (states) | Existing | Small |
| 11 | Add comparison mode logic | consultant_agent.py | Medium |
| 12 | Add research mode logic | consultant_agent.py | Medium |
| 13 | DynamoDB persistence for consultation state | dynamo_service.py | Medium |

---

## Key Design Decisions

### 1. Where does confidence evaluation happen?
**Decision:** Server-side in `consultant_agent.py`. The LLM helps extract structured data from free-text, but the confidence score is computed deterministically by `confidence_engine.py`.

### 2. Which LLM handles consultation?
**Decision:** Keep using the current LLM (Ollama/Gemini). The system prompt changes, and the orchestration layer decides when to inject product context vs. ask questions. The LLM itself doesn't decide when to search — the confidence engine does.

### 3. How is consultation state persisted?
**Decision:** 
- In-memory during active session (fast)
- Saved to DynamoDB on each turn (persistence)
- Loaded from DynamoDB when session resumes

### 4. How does memory/personalization work across sessions?
**Decision:** After each completed consultation (retrieval triggered), extract learned preferences and store in user profile. On next session, load these as context: "Based on your past preferences: gluten-free, budget-conscious, prefers organic."

### 5. What's the confidence threshold?
**Decision:** Default 0.70 (70%). Configurable. Below this, the AI asks questions. Above this, retrieval begins.

---

## File Dependency Graph

```
chat_router.py
  └── consultant_agent.py (NEW - replaces direct retrieval call)
        ├── consultation_state.py (NEW - state management)
        ├── confidence_engine.py (NEW - readiness evaluation)
        ├── retrieval.py (EXISTING - semantic search, called only when ready)
        ├── memory_service.py (NEW - cross-session learning)
        └── LLM (Ollama/Gemini - prompt depends on mode)
```

---

## What Does NOT Change

- `auth/` — Authentication system remains identical
- `retrieval.py` — Vector search logic stays, just called later
- `db/dynamo_service.py` — Extended but not broken
- `frontend/src/context/AuthContext.tsx` — No change
- `frontend/src/pages/Login.tsx`, `Signup.tsx`, etc. — No change
- Product data and embeddings — No change
- CORS, middleware, image proxy — No change

---

## Success Metric

> "Users should feel that the assistant understands their needs before recommending products."

**Measurable:**
- Average messages before first product retrieval: target 3-5 (currently 1)
- Consultation state completeness at retrieval time: target >70%
- User does NOT see products until assistant has gathered context
- Products panel shows "gathering requirements" state during consultation
