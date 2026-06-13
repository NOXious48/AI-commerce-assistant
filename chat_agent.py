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

import ollama
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ---------------------------------------------------------------------------
# System Prompt (used by chat_router)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a friendly, knowledgeable AI shopping assistant for an e-commerce platform.

Your job is to help customers find the right products through natural conversation.
You have access to a product catalog of ~2100 real Amazon products.

RULES:
1. When a user asks about products, you will receive RETRIEVED PRODUCTS as context.
   Base your recommendations ONLY on these retrieved products. NEVER invent products.
2. For each recommendation, mention the product title, price, and why it matches.
   Keep it concise. The products are already displayed visually in the UI.
3. If no relevant products are found, say so honestly and suggest the user rephrase.
4. Be conversational, concise, and helpful. Highlight the top 2-3 picks and offer to show more.
5. You can answer general shopping questions, compare products, and give advice.
6. If the user's query is casual (greeting, general question), respond naturally
   without forcing product recommendations.
7. Use markdown formatting for better readability (bold, lists, etc).
8. Do NOT repeat the full feature lists - the user can see those in the product cards.
"""


# ---------------------------------------------------------------------------
# Chat Session Manager (used by chat_router)
# ---------------------------------------------------------------------------

class OllamaChatSession:
    """Wraps Ollama chat to mimic the Gemini send_message interface."""

    def __init__(self, model: str, system_prompt: str):
        self.model = model
        self.history: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

    def send_message(self, message: str):
        """Send a message and return response with a .text attribute."""
        self.history.append({"role": "user", "content": message})
        response = ollama.chat(model=self.model, messages=self.history)
        reply = response["message"]["content"]
        self.history.append({"role": "assistant", "content": reply})

        # Return an object with .text to match Gemini interface
        class _Response:
            def __init__(self, text):
                self.text = text
        return _Response(reply)


class ChatSessionManager:
    """Manages per-session Ollama chat instances."""

    def __init__(self):
        self.model_name = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
        self.sessions: Dict[str, Any] = {}
        print(f"[OK] Chat model initialized (Ollama: {self.model_name})")

    def get_chat(self, session_id: str):
        if session_id not in self.sessions:
            self.sessions[session_id] = OllamaChatSession(
                model=self.model_name,
                system_prompt=SYSTEM_PROMPT,
            )
        return self.sessions[session_id]

    def reset_session(self, session_id: str):
        self.sessions.pop(session_id, None)


chat_manager = ChatSessionManager()


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

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(chat_router)


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
    print("\n[OK] Starting AI Commerce Assistant on http://localhost:8000")
    print("[OK] Auth: AWS Cognito | DB: DynamoDB | LLM: Ollama (qwen2.5:7b)")
    uvicorn.run("chat_agent:app", host="0.0.0.0", port=8000, reload=False)
