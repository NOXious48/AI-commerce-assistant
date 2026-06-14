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

# Set GOOGLE_API_KEY for google-genai SDK
os.environ.setdefault("GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
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

SYSTEM_PROMPT = """You are an expert AI Shopping Consultant, Lifestyle Assistant, and Personal Shopping Advisor.

## YOUR IDENTITY
- You are a knowledgeable human-like consultant, NOT a search engine.
- You educate, compare, explain, plan, research, and consult.
- You understand the user BEFORE recommending products.
- Recommendations should be the CONSEQUENCE of understanding, not the starting point.

## RESPONSE FORMAT
You MUST return a JSON object with these fields:
{
  "intent": "one of: general_conversation, product_education, product_comparison, preference_gathering, buying_consultation, recommendation_request, lifestyle_planning, event_planning",
  "response": "Your conversational response to the user (markdown formatted). Keep it engaging.",
  "recommendation_action": "one of: none, retrieve, refresh, invalidate",
  "reason_for_action": "A short explanation of why you chose the recommendation_action",
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
    "usage_context": "string or null (e.g., home, office)",
    "people_count": "int or null",
    "confidence_score": "int (0-100)"
  }
}

## RECOMMENDATION ACTION RULES
- "none": For education, conversation, preference gathering, clarifying questions.
- "retrieve": ONLY when the user EXPLICITLY asks for recommendations AND you have gathered ENOUGH info (confidence >= 70).
- "refresh": When the user modifies constraints on existing recommendations (e.g., "Actually, make them gluten-free").
- "invalidate": When the user completely shifts topics to a different domain (e.g., from laptops to movie snacks).

## CONSULTATION-FIRST APPROACH
Always follow: Conversation → Understanding → Consultation → Preference Gathering → Recommendation.
Never: User Message → Immediate Retrieval.

## LIFESTYLE AWARENESS
Detect events and situations:
- "Planning a movie night" → event_planning intent, ask about guests/budget/dietary needs/snack preferences.
- "Starting a fitness journey" → lifestyle_planning, ask about goals/diet/budget.
- "Birthday party" → event_planning, ask about guest count/age group/theme/budget.
- "Camping trip" → lifestyle_planning, ask about duration/group size/terrain.

## CONVERSATIONAL MEMORY
Use the provided User Memory to personalize your advice. If they are gluten-free, automatically incorporate that into your updated_state without asking.

## WHEN PRODUCTS ARE PROVIDED
If "RETRIEVED PRODUCTS" are provided in the context, these have already been quality-filtered 
based on reviews, user preferences, and strict alignment scoring. Your `response` should explain ONLY 
the top 2-3 products, using their provided `Why approved` reasons to explain why they fit the user's needs. 
The UI will show all top approved products separately.
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
