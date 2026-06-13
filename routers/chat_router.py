"""
Chat Router — Chat Sessions and Messaging with Persistence
============================================================
Handles chat with RAG + Gemini, persists messages to DynamoDB.
All endpoints protected. Identity from JWT sub only.
"""

import os
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Body, status
from pydantic import BaseModel, Field

from auth.jwt_verifier import get_current_user
from db.dynamo_service import dynamo_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1, max_length=4000)


# ---------------------------------------------------------------------------
# Lazy imports (avoid circular imports)
# ---------------------------------------------------------------------------

def _get_retriever():
    from retrieval import retriever
    return retriever


def _get_chat_manager():
    from chat_agent import chat_manager, SYSTEM_PROMPT
    return chat_manager


def _should_search(message: str) -> bool:
    casual = {
        "hi", "hello", "hey", "thanks", "thank you", "bye", "goodbye",
        "how are you", "what can you do", "help", "who are you",
    }
    return message.strip().lower() not in casual and len(message.strip()) > 2


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/new-session")
async def new_session(user: dict = Depends(get_current_user)):
    """Create a new chat session. Returns the session_id (UUID)."""
    session = dynamo_service.create_session(user["sub"], title="New Chat")
    return session


@router.post("")
async def chat(req: ChatMessage, user: dict = Depends(get_current_user)):
    """
    Send a message in a chat session.
    1. Verify session belongs to user
    2. Save user message to DynamoDB
    3. Retrieve products + call Gemini
    4. Save AI response to DynamoDB
    5. Return response + products
    """
    user_id = user["sub"]
    session_id = req.session_id
    message = req.message

    # Verify session belongs to this user
    session = dynamo_service.get_session(user_id, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found.",
        )

    # Save user message
    dynamo_service.save_message(session_id, "user", message)

    # Product retrieval
    products = []
    retriever = _get_retriever()

    if _should_search(message):
        products = retriever.search(message, top_k=6, min_score=0.25)

        # Build context for LLM
        context_lines = [f"RETRIEVED PRODUCTS ({len(products)} results):"]
        for i, p in enumerate(products, 1):
            context_lines.append(
                f"\n[{i}] {p['title']} | ${p['price']:.2f} | {p['main_category']} | "
                f"Rating: {p['average_rating']} | Store: {p.get('store', 'N/A')} | "
                f"Score: {p['similarity_score']:.3f}"
            )
            feats = p.get("features", [])
            if feats:
                context_lines.append(f"    Key feature: {feats[0][:120]}")

        context = "\n".join(context_lines)
        augmented = f"User: {message}\n\n{context}\n\nRespond helpfully based on the products above."
    else:
        augmented = message

    # Send to LLM (Ollama)
    chat_manager = _get_chat_manager()
    try:
        chat_session = chat_manager.get_chat(f"{user_id}:{session_id}")
        response = chat_session.send_message(augmented)
        reply = response.text
    except Exception as e:
        logger.exception("Ollama error")
        reply = f"Sorry, I encountered an error generating a response. Please make sure Ollama is running and try again."

    # Sanitize products for response
    safe_products = []
    for p in products:
        safe_products.append({
            "parent_asin": p["parent_asin"],
            "title": p["title"],
            "price": p["price"],
            "main_category": p["main_category"],
            "average_rating": p["average_rating"],
            "store": p.get("store", ""),
            "features": p.get("features", [])[:3],
            "similarity_score": p["similarity_score"],
            "image_url": p.get("image_url", ""),
            "rating_number": p.get("rating_number", 0),
        })

    # Save AI response to DynamoDB
    dynamo_service.save_message(session_id, "assistant", reply, safe_products)

    # Update session timestamp and auto-title from first message
    dynamo_service.update_session_timestamp(user_id, session_id)
    if session.get("title") == "New Chat":
        # Auto-generate title from first message
        title = message[:50] + ("..." if len(message) > 50 else "")
        dynamo_service.update_session_title(user_id, session_id, title)

    return {"reply": reply, "products": safe_products}


@router.get("/history")
async def get_history(user: dict = Depends(get_current_user)):
    """List all chat sessions for the current user."""
    return dynamo_service.list_sessions(user["sub"])


@router.get("/session/{session_id}")
async def get_session_messages(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """Get all messages for a session. Enforces ownership."""
    # Verify ownership
    session = dynamo_service.get_session(user["sub"], session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    messages = dynamo_service.get_messages(session_id)
    return {"session": session, "messages": messages}


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a chat session and all its messages."""
    return dynamo_service.delete_session(user["sub"], session_id)


@router.post("/reset")
async def reset_session(
    session_id: str = Body(..., embed=True),
    user: dict = Depends(get_current_user),
):
    """Reset the in-memory Gemini chat for a session."""
    chat_manager = _get_chat_manager()
    chat_manager.reset_session(f"{user['sub']}:{session_id}")
    return {"message": "Chat session reset"}
