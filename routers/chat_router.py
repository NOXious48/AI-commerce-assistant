"""
Chat Router — Chat Sessions and Messaging with Persistence
============================================================
Handles chat with RAG + Google ADK (Gemini 2.5 Flash).
Persists messages to DynamoDB. All endpoints protected.
Identity from JWT sub only.

ADK is the REASONING LAYER ONLY.
DynamoDB is the SOURCE OF TRUTH for all persistence.
The Recommendation Agent is PURE PYTHON and the FINAL AUTHORITY.
"""

import os
import json
import logging
import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from decimal import Decimal

# Google ADK — Agent framework
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
import time

# --- Short-Term Decision Cache ---
# Stores { "session_id:message_hash": {"decision": dict, "expires_at": float} }
DECISION_CACHE = {}
DECISION_CACHE_TTL = 60  # seconds


# Google GenAI — used only for memory extraction (utility, not agent)
from google import genai
from google.genai import types

from fastapi import APIRouter, Depends, HTTPException, Body, status, BackgroundTasks
from pydantic import BaseModel, Field

from auth.jwt_verifier import get_current_user
from db.dynamo_service import dynamo_service
from schemas import ConsultationState, UserMemory, ConversationAgentOutput

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

def _get_filter_agent():
    from review_filter_agent import review_filter_agent
    return review_filter_agent

def _get_cart_planning_agent():
    from cart_planning_agent import cart_planning_agent
    return cart_planning_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def consultation_complete(state: dict) -> bool:
    """Check if we have enough info to trigger retrieval."""
    if not state.get("goal") and not state.get("event"):
        return False
    if state.get("confidence_score", 0) < 70:
        return False
    return True


def _convert_decimals(obj):
    """Recursively convert Decimal types to float/int for JSON serialization."""
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    return obj


def _compute_context_hash(state: dict) -> str:
    """Hash the recommendation-relevant fields for change detection."""
    relevant = {
        "goal": state.get("goal"),
        "event": state.get("event"),
        "budget": state.get("budget"),
        "dietary_preferences": sorted(state.get("dietary_preferences", [])),
        "preferred_brands": sorted(state.get("preferred_brands", [])),
        "people_count": state.get("people_count"),
    }
    return hashlib.md5(json.dumps(relevant, sort_keys=True).encode()).hexdigest()


def _recommendation_agent(action: str, new_state: dict, workspace: dict) -> dict:
    """Recommendation Agent: Decides retrieval actions (pure logic).
    
    IMPORTANT: This function is the FINAL AUTHORITY. Even if the LLM says "retrieve",
    it must validate against consultation_complete().
    """
    # 1. Domain Shift Detection
    new_domain = new_state.get("event") or new_state.get("goal")
    old_domain = workspace.get("active_domain")
    if old_domain and new_domain and new_domain != old_domain:
        action = "invalidate"
        
    if action == "invalidate":
        return {"action": "clear", "products": []}
    
    # 2. Validate Retrieval Request
    if action in ["retrieve", "refresh"]:
        if not consultation_complete(new_state):
            # Block premature retrieval
            return {"action": "keep", "products": workspace.get("retrieved_products", [])}
            
        new_hash = _compute_context_hash(new_state)
        old_hash = workspace.get("context_hash", "")
        
        if action == "retrieve" or (action == "refresh" and new_hash != old_hash):
            return {"action": "search", "hash": new_hash, "domain": new_domain}
    
    # Context unchanged, keep existing
    return {"action": "keep", "products": workspace.get("retrieved_products", [])}


# ---------------------------------------------------------------------------
# ADK Conversation Agent
# ---------------------------------------------------------------------------

def _build_workspace_summary(workspace: dict) -> dict:
    """Build a lightweight workspace summary for context injection.
    
    Injects summary instead of full product payloads to reduce token usage.
    """
    products = workspace.get("approved_products", workspace.get("retrieved_products", []))
    metrics = workspace.get("filtering_metadata", {})
    summary = {
        "active_domain": workspace.get("active_domain"),
        "workspace_version": workspace.get("version", 0),
        "products_count": len(products),
        "top_products": [p.get("title", "") for p in products[:3]],
    }
    if metrics:
        summary["filtering_metrics"] = metrics
    return summary


async def _conversation_agent(message: str, state: dict, memory: dict, history: list, workspace: dict, user_id: str, session_id: str) -> dict:
    """Conversation Agent: Google ADK LlmAgent for reasoning.
    
    ADK is the REASONING LAYER ONLY.
    - No persistence in ADK (DynamoDB is the source of truth)
    - No memory storage in ADK (DynamoDB handles memory)
    - Session is ephemeral (created per-request, discarded after)
    
    Uses cognito_sub as user_id and chat_session_id as session_id
    for better debugging and observability.
    """
    from chat_agent import SYSTEM_PROMPT
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    
    # --- Context Injection ---
    # Load from DynamoDB and inject into system instruction
    workspace_summary = _build_workspace_summary(workspace)
    workspace_products = workspace.get("retrieved_products", [])
    
    context_lines = [
        f"USER MEMORY (Persistent Preferences):\n{json.dumps(_convert_decimals(memory), indent=2)}\n",
        f"CURRENT CONSULTATION STATE:\n{json.dumps(_convert_decimals(state), indent=2)}\n",
        f"RECOMMENDATION WORKSPACE SUMMARY:\n{json.dumps(_convert_decimals(workspace_summary), indent=2)}\n",
    ]
    
    # Include top products for LLM explanation (top 2-3 only)
    workspace_products = workspace.get("approved_products", workspace_products)
    if workspace_products:
        context_lines.append(f"RETRIEVED PRODUCTS (top {min(15, len(workspace_products))} of {len(workspace_products)}):")
        for i, p in enumerate(workspace_products[:15], 1):
            reasons = " ".join(p.get("approval_reasons", []))
            context_lines.append(
                f"[{i}] {p.get('title','')} | ${p.get('price',0)} | {p.get('main_category','')} | "
                f"Rating: {p.get('average_rating',0)} | Alignment: {p.get('alignment_score', 'N/A')}"
            )
            if reasons:
                context_lines.append(f"    Why approved: {reasons}")
            elif p.get('features'):
                context_lines.append(f"    Feature: {p['features'][0][:120]}")

    try:
        from services.gemini_client import generate_structured_output
        validated_output = await generate_structured_output(
            user_message=message,
            user_id=user_id,
            session_id=session_id,
            context_lines=context_lines
        )
        logger.info(f"ADK Agent: intent={validated_output.intent}, action={validated_output.recommendation_action}, reason={validated_output.reason_for_action}")
        return validated_output.model_dump()
        
    except Exception as e:
        logger.exception("Failed in _conversation_agent (ADK)")
        return {
            "intent": "general_conversation",
            "response": "Sorry, I encountered an error generating a response. Please try again.",
            "recommendation_action": "none",
            "reason_for_action": "Error fallback",
            "updated_state": state
        }


def _extract_memory_background(user_id: str, messages: list):
    """Background task to update long-term user memory using Gemini."""
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    current_memory = dynamo_service.get_user_memory(user_id)
    
    chat_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
    
    prompt = f"""You are a memory extraction assistant. Analyze this chat history and update the user's long-term shopping memory.
CURRENT MEMORY:
{json.dumps(_convert_decimals(current_memory), indent=2)}

RECENT CHAT HISTORY:
{chat_text}

Extract any persistent preferences (e.g. they are vegan, they hate apple products, they always buy cheap, etc).
Return ONLY a valid JSON object matching this schema:
{{
    "dietary_preferences": ["string"],
    "budget_preferences": ["string"],
    "favorite_brands": ["string"],
    "avoided_brands": ["string"],
    "other_preferences": ["string"]
}}
"""
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            )
        )
        new_memory = json.loads(response.text)
        dynamo_service.update_user_memory(user_id, new_memory)
        logger.info(f"Updated user memory for {user_id}")
    except Exception as e:
        logger.exception("Failed to extract memory (Gemini)")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/new-session")
async def new_session(user: dict = Depends(get_current_user)):
    """Create a new chat session. Returns the session_id (UUID)."""
    session = dynamo_service.create_session(user["sub"], title="New Chat")
    return session


@router.post("")
async def chat(req: ChatMessage, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    """
    Send a message in a chat session.
    """
    user_id = user["sub"]
    session_id = req.session_id
    message = req.message

    # 1. Parallel Load Session, Memory, Messages
    session, user_mem, all_messages = await asyncio.gather(
        asyncio.to_thread(dynamo_service.get_session, user_id, session_id),
        asyncio.to_thread(dynamo_service.get_user_memory, user_id),
        asyncio.to_thread(dynamo_service.get_messages, session_id, 12)
    )

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")

    # 2. Save user message synchronously (as requested)
    dynamo_service.save_message(session_id, "user", message)
    
    # 3. Request Context Preparation
    # Append the user's message manually to the list since we loaded it concurrently before saving
    all_messages.append({"role": "user", "content": message, "timestamp": datetime.now(timezone.utc).isoformat()})
    
    state = session.get("consultation_state", {})
    workspace = session.get("recommendation_workspace", {})
    
    # --- Check Short-Term Decision Cache ---
    msg_hash = hashlib.md5(message.encode()).hexdigest()
    cache_key = f"{session_id}:{msg_hash}"
    now = time.time()
    
    # Cleanup expired cache entries (lazy cleanup)
    expired_keys = [k for k, v in DECISION_CACHE.items() if v["expires_at"] < now]
    for k in expired_keys:
        del DECISION_CACHE[k]
        
    if cache_key in DECISION_CACHE:
        decision = DECISION_CACHE[cache_key]["decision"]
        logger.info(f"Using cached decision for {cache_key}")
    else:
        # 4. CONVERSATION AGENT (ADK) — single LlmAgent call
        decision = await _conversation_agent(message, state, user_mem, all_messages, workspace, user_id, session_id)
        DECISION_CACHE[cache_key] = {"decision": decision, "expires_at": now + DECISION_CACHE_TTL}

    reply = decision.get("response", "I'm not sure how to answer that.")
    intent = decision.get("intent", "general_conversation")
    new_state = decision.get("updated_state", state)
    action = decision.get("recommendation_action", "none")
    cart_action = decision.get("cart_action", "none")
    reason = decision.get("reason_for_action", "")
    search_query = decision.get("search_query", "")

    # 5. RECOMMENDATION AGENT — ONLY called when orchestrator requests it
    safe_products = workspace.get("approved_products", workspace.get("retrieved_products", []))  # default: keep existing
    
    if action != "none":
        rec_decision = _recommendation_agent(action, new_state, workspace)
        
        if rec_decision["action"] == "search" and search_query:
            retriever = _get_retriever()
            filter_agent = _get_filter_agent()
            
            # Retrieve Top 100 for internal workspace
            products = retriever.search(search_query, top_k=100, min_score=0.15)
            
            # Sanitize
            sanitized = []
            for p in products:
                sanitized.append({
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
                
            # Filter
            chat_context = "\n".join([f"{m['role']}: {m['content']}" for m in all_messages])
            filter_result = filter_agent.filter_products(
                retrieved_products=sanitized,
                consultation_state=new_state,
                user_memory=user_mem,
                conversation_summary=chat_context
            )
                
            workspace = {
                "context_hash": rec_decision["hash"],
                "active_domain": rec_decision.get("domain", new_state.get("event") or new_state.get("goal")),
                "retrieved_products": sanitized,
                "approved_products": filter_result.approved_products,
                "rejected_products": filter_result.rejected_products,
                "filtering_metadata": filter_result.metrics,
                "version": workspace.get("version", 0) + 1,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "reason_for_generation": reason
            }
            safe_products = filter_result.approved_products
        elif rec_decision["action"] == "clear":
            workspace = {
                "context_hash": "",
                "active_domain": None,
                "retrieved_products": [],
                "approved_products": [],
                "rejected_products": [],
                "filtering_metadata": {},
                "version": workspace.get("version", 0) + 1
            }
            safe_products = []
        else:
            safe_products = rec_decision.get("products", [])

    # 6. CART PLANNING AGENT
    cart_workspace = session.get("cart_workspace", {})
    current_cart = session.get("cart_items", [])
    
    if cart_action != "none":
        cart_agent = _get_cart_planning_agent()
        cart_result = cart_agent.plan_cart(
            action=cart_action,
            current_cart=current_cart,
            cart_workspace=cart_workspace,
            consultation_state=new_state,
            approved_products=safe_products,
            user_memory=user_mem,
            intent=intent
        )
        
        new_cart = cart_result.get("new_cart", current_cart)
        new_cart_workspace = cart_result.get("new_workspace", cart_workspace)
        sys_msg = cart_result.get("system_message", None)
        
        # Save updates
        background_tasks.add_task(dynamo_service.update_cart_items, user_id, session_id, new_cart)
        background_tasks.add_task(dynamo_service.update_cart_workspace, user_id, session_id, new_cart_workspace)
        
        if sys_msg:
            dynamo_service.save_message(
                session_id=session_id,
                role=sys_msg["role"],
                content=sys_msg["message"],
                msg_type=sys_msg["type"],
                event_metadata={
                    "event_type": sys_msg["event_type"],
                    "cart_version": sys_msg["cart_version"]
                }
            )

    # 7. Save new state, workspace, and assistant reply to DB
    # We display Top 30 in UI, so only pass top 30 to save_message if you want to limit DB size for messages
    background_tasks.add_task(dynamo_service.update_consultation_state, user_id, session_id, new_state, safe_products[:30], workspace)
        
    dynamo_service.save_message(session_id, "assistant", reply, safe_products[:30])

    # Update session title if it's new
    if session.get("title") == "New Chat":
        title = message[:30] + ("..." if len(message) > 30 else "")
        background_tasks.add_task(dynamo_service.update_session_title, user_id, session_id, title)
    else:
        background_tasks.add_task(dynamo_service.update_session_timestamp, user_id, session_id)

    # 8. Memory Extraction (Background)
    if len(all_messages) % 5 == 0:
        background_tasks.add_task(_extract_memory_background, user_id, all_messages)

    response_data = {
        "reply": reply,
        "products": _convert_decimals(safe_products[:30]),  # Display top 30
        "state": _convert_decimals(new_state),
        "intent": intent,
        "recommendation_action": action,
        "reason_for_action": reason,
        "filtering_metadata": workspace.get("filtering_metadata", {}),
        "cart_items": _convert_decimals(current_cart) if cart_action == "none" else _convert_decimals(cart_result.get("new_cart", [])),
        "cart_workspace": _convert_decimals(cart_workspace) if cart_action == "none" else _convert_decimals(cart_result.get("new_workspace", {}))
    }
    logger.info(f"Returning {len(response_data['products'])} products, {len(response_data['cart_items'])} cart items. action={action}, cart_action={cart_action}")
    return response_data


@router.get("/history")
async def get_history(user: dict = Depends(get_current_user)):
    """List all chat sessions for the current user."""
    return dynamo_service.list_sessions(user["sub"])


@router.get("/session/{session_id}")
async def get_session_messages(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """Get all messages and state for a session. Enforces ownership."""
    session = dynamo_service.get_session(user["sub"], session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    messages = dynamo_service.get_messages(session_id)
    return {
        "session": _convert_decimals(session), 
        "messages": _convert_decimals(messages),
        "state": _convert_decimals(session.get("consultation_state", {})),
        "products": _convert_decimals(session.get("last_retrieved_products", [])),
        "cart_items": _convert_decimals(session.get("cart_items", [])),
        "cart_workspace": _convert_decimals(session.get("cart_workspace", {}))
    }


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a chat session and all its messages."""
    return dynamo_service.delete_session(user["sub"], session_id)


@router.put("/session/{session_id}/title")
async def rename_session(
    session_id: str,
    title: str = Body(..., embed=True),
    user: dict = Depends(get_current_user),
):
    """Rename a chat session."""
    dynamo_service.update_session_title(user["sub"], session_id, title)
    return {"message": "Title updated"}
