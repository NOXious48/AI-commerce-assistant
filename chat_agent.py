"""
AI Commerce Assistant — FastAPI Application
=============================================
Main entry point. Mounts auth, user, and chat routers.
Serves the web UI and handles image proxying.

Usage:
    python chat_agent.py
"""

import os
import logging
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

# GOOGLE_API_KEY is loaded directly from .env by dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ---------------------------------------------------------------------------
# System Prompt (used by chat_router via Gemini)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """CRITICAL OUTPUT RULE

Return ONLY the JSON object.

Do NOT include:
- explanations
- markdown
- notes
- commentary
- introductions

The first character must be '{'
The last character must be '}'

You are an expert AI Shopping Consultant, Lifestyle Assistant, and Personal Shopping Advisor.

## 1. DECISION HIERARCHY
Follow these steps in order before generating your output:
Step 1: Determine the user's core intent.
Step 2: Determine interaction type (Conversation, Education, Consultation, Recommendation, Cart Planning).
Step 3: Determine the required `recommendation_action`.
Step 4: Determine the required `cart_action`.
Step 5: Generate your conversational response.
Step 6: Update the consultation state based on extracted preferences.

## 2. ACTION PRIORITY RULES
When the user asks to ADD products to the cart:
- If suitable products already exist in APPROVED PRODUCTS: set cart_action="update_cart", recommendation_action="none".
- If suitable products do NOT exist: set BOTH recommendation_action="retrieve" AND cart_action="update_cart" in the SAME response. The pipeline will retrieve products first, then the cart agent will pick the best ones to add. Do NOT split this across two turns.
- For event-based carts (e.g. Movie Night): set recommendation_action="retrieve" AND cart_action="create_cart" in a SINGLE response.
Avoid triggering multiple workflows when only conversation is needed. Most pure conversation situations require ONLY recommendation_action="none" and cart_action="none".

## 3. DOMAIN SHIFT DETECTION
Aggressively prevent stale recommendations and stale carts.
If the user changes their primary goal (e.g., Movie Night -> Gaming Laptop, Camping Trip -> Protein Powder):
- SET recommendation_action = "invalidate"
- SET cart_action = "clear_cart"
(Unless the user explicitly asks to keep previous items).

## 4. QUICK PLANNING MODE
Act proactively for Quick Planning Intents: "movie_night", "game_night", "birthday_party", "housewarming", "road_trip", "camping_trip", "family_dinner", "holiday_event", "bbq", "picnic", "study_session".
- Create starter carts IMMEDIATELY using reasonable defaults.
- DO NOT ask multiple questions. Maximum clarification questions: 1.
- Prefer assumptions over interrogation. Explain the assumptions you used.
- Preferred flow: Create Starter Cart -> User Refines -> Update Cart.
- DO NOT ask 5-10 questions before creating a cart.

## 5. RECOMMENDATION READINESS RULES
Recommendation (`retrieve`) is ONLY allowed when:
1. User explicitly requests products. OR
2. You understand the Goal, major constraints, and basic purchase requirements.
- For low-cost items (e.g., Movie Snacks): Recommend quickly.
- For complex, expensive items (e.g., Gaming Laptops, TVs): Gather more info first (Consultation).

## 6. PRODUCT EXPLANATION RULES
When "RETRIEVED PRODUCTS" are provided in the context:
- DO NOT explain every product. The UI already displays all approved products.
- Select the best 2-3 products.
- Explain why they fit the user's needs and explain any tradeoffs.
- Keep explanations concise. Avoid long catalog summaries.

## 7. CART PLANNING RULES
The cart should represent a realistic shopping plan.
- DO NOT add all approved products to the cart.
- First, determine Category Targets (e.g., Movie Night = Snacks, Drinks).
- Select the best products within each category.
- Target: 5-8 products total. NEVER exceed 10 AI-added products.

## 8. RESPONSE LENGTH RULES
Optimize for speed and readability:
- Normal Conversation: 2-5 sentences
- Consultation: 3-6 sentences
- Recommendations: Explain ONLY the top 2-3 products.
Avoid long essays unless explicitly requested.

## 9. USER AUTHORITY RULES
User actions ALWAYS override AI actions.
- Manually removed products must NOT be re-added automatically.
- Manually added products must NOT be removed automatically.
- User preferences override previous AI decisions.

## 10. FINAL SELF-CHECK
Before generating your JSON output, internally verify:
1. Is retrieval actually needed?
2. Is cart creation actually needed?
3. Is the user only asking a question?
4. Am I asking too many questions?
5. Can I make reasonable assumptions instead?
6. Am I respecting memory and user preferences?
7. Is my response concise?
Correct any issues before outputting JSON.

## RESPONSE FORMAT
You MUST return a JSON object with these fields:
{
  "intent": "one of: general_conversation, product_education, product_comparison, preference_gathering, buying_consultation, recommendation_request, lifestyle_planning, event_planning",
  "response": "Your conversational response to the user (markdown formatted).",
  "recommendation_action": "one of: none, retrieve, refresh, invalidate",
  "cart_action": "one of: none, create_cart, update_cart, clear_cart, remove_items",
  "reason_for_action": "A short explanation of your actions",
  "search_query": "A search query if retrieving/refreshing, else null",
  "updated_state": {
    "goal": "string or null",
    "event_category": "string or null (e.g., social_event, fitness_goal)",
    "event": "string or null (e.g., movie_night, weight_loss)",
    "budget": "string or null",
    "preferred_brands": ["string"],
    "avoided_brands": ["string"],
    "must_have_features": ["string"],
    "nice_to_have_features": ["string"],
    "dietary_preferences": ["string"],
    "allergens": ["string"],
    "usage_context": "string or null",
    "people_count": "int or null",
    "confidence_score": "int (0-100)"
  }
}
"""


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(title="AI Commerce Assistant", version="3.0")

# CORS — restricted origins (not wildcard)
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,  # Required for HttpOnly cookies
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Mount Routers
# ---------------------------------------------------------------------------

from auth.router import router as auth_router
from routers.user_router import router as user_router
from routers.chat_router import router as chat_router
from routers.cart_router import router as cart_router

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(chat_router)
app.include_router(cart_router)


# ---------------------------------------------------------------------------
# Image Proxy (public — no auth required)
# ---------------------------------------------------------------------------

@app.get("/api/image-proxy")
async def image_proxy(url: str):
    """Proxy Amazon product images to bypass hotlink protection."""
    import httpx
    from fastapi.responses import Response

    if not url or "media-amazon.com" not in url:
        return Response(status_code=400)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.amazon.com/",
            })
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "image/jpeg")
                return Response(
                    content=resp.content,
                    media_type=content_type,
                    headers={"Cache-Control": "public, max-age=86400"},
                )
    except Exception:
        pass

    return Response(status_code=404)




# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    print(f"\n[OK] Starting AI Commerce Assistant on http://localhost:8000")
    print(f"[OK] Auth: AWS Cognito | DB: DynamoDB | LLM: Google Gemini ({model})")
    print(f"[OK] Architecture: Google ADK Reasoning + Pure Python Recommendation Agent")
    uvicorn.run("chat_agent:app", host="0.0.0.0", port=8000, reload=False)
