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
from routers.recommendation_router import router as recommendation_router

app.include_router(auth_router)
app.include_router(user_router)
app.include_router(chat_router)
app.include_router(cart_router)
app.include_router(recommendation_router)


# ---------------------------------------------------------------------------
# Image Proxy (public — no auth required)
# ---------------------------------------------------------------------------

@app.get("/api/image-proxy")
async def image_proxy(url: str):
    """Proxy Amazon product images to bypass hotlink protection."""
    import httpx
    from fastapi.responses import Response

    if not url:
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
# Serve Frontend Static Build (production)
# ---------------------------------------------------------------------------

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")

if os.path.exists(FRONTEND_DIR):
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the React SPA for all non-API routes."""
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    print(f"\n[OK] Starting AI Commerce Assistant on http://localhost:8000")
    print(f"[OK] Auth: AWS Cognito | DB: DynamoDB | LLM: Google Gemini ({model})")
    print(f"[OK] Architecture: Google ADK Reasoning + Pure Python Recommendation Agent")
    uvicorn.run("chat_agent:app", host="0.0.0.0", port=8000, reload=False)
