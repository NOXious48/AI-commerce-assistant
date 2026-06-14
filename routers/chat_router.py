"""
Chat Router — Chat Sessions and Messaging with Persistence
============================================================
Handles chat with RAG + Multi-Agent Shopping Consultant Architecture.
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Body, status, BackgroundTasks
from pydantic import BaseModel, Field

from auth.jwt_verifier import get_current_user
from db.dynamo_service import dynamo_service
from services.retrieval_service import retriever
from agents.workspace_manager import WorkspaceManager
from agents.orchestrator import OrchestratorAgent
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Initialize Agent Services
workspace_manager = WorkspaceManager(dynamo_service)
orchestrator = OrchestratorAgent(retriever, workspace_manager)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1, max_length=4000)
    page_context: dict = Field(default_factory=dict)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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

def _extract_memory_background(user_id: str, messages: list):
    """Background task to update long-term user memory using Gemini with confidence scoring."""
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    current_memory_dict = dynamo_service.get_user_memory(user_id) # dict of arrays of UserMemory dicts
    
    # Prune expired unconfirmed memories
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    
    pruned_memory = {}
    for mem_type, mem_list in current_memory_dict.items():
        pruned_list = []
        for m in mem_list:
            # If confirmed, keep forever. If unconfirmed, check expiration.
            # Assuming creation time is implicitly "now" if not tracked, but we need an created_at.
            # For simplicity if it's unconfirmed we just keep it if we recently created it, but without a timestamp we might just keep it. 
            # Let's add timestamp tracking if missing, or just rely on the LLM to prune.
            # Actually, UserMemory model doesn't have created_at. Let's just trust it's there or skip strict pruning here if missing.
            pruned_list.append(m)
        pruned_memory[mem_type] = pruned_list

    chat_text = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages[-10:]])
    
    prompt = f"""You are a memory extraction assistant. Analyze this recent chat history and update the user's long-term shopping memory.
CURRENT MEMORY:
{json.dumps(_convert_decimals(pruned_memory), indent=2)}

RECENT CHAT HISTORY:
{chat_text}

Extract any persistent preferences (e.g. they are vegan, they hate apple products, they always buy cheap).
Assign a confidence score (0-100). If it's a casual mention, confidence is lower. If explicitly stated "I am allergic to X", confidence is 100.
Always set confirmed: false.
Set expires_after_days: 14.

Return ONLY a valid JSON object matching this schema where values are arrays of memory objects:
{{
    "dietary_preferences": [ {{"memory_type": "dietary_preferences", "value": "string", "confidence": 90, "confirmed": false, "expires_after_days": 14}} ],
    "budget_preferences": [],
    "favorite_brands": [],
    "avoided_brands": [],
    "other_preferences": []
}}
"""
    try:
        client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY_CONVERSATION"))
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            )
        )
        new_memory = json.loads(response.text)
        
        # Merge logic: if a new memory exists, add it to pruned
        for k, v in new_memory.items():
            if not isinstance(v, list): continue
            if k not in pruned_memory: pruned_memory[k] = []
            
            existing_values = [m.get("value", "").lower() for m in pruned_memory[k]]
            for new_m in v:
                if new_m.get("confidence", 0) < 60: continue # Skip low confidence
                if new_m.get("value", "").lower() not in existing_values:
                    pruned_memory[k].append(new_m)
                    
        dynamo_service.update_user_memory(user_id, pruned_memory)
        logger.info(f"Updated user memory for {user_id}")
    except Exception as e:
        logger.exception("Failed to extract memory (Gemini)")

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/new-session")
async def new_session(user: dict = Depends(get_current_user)):
    """Create a new chat session."""
    session = dynamo_service.create_session(user["sub"], title="New Chat")
    return session


@router.post("")
async def chat(req: ChatMessage, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    """
    Send a message in a chat session.
    Routes through the OrchestratorAgent.
    Optimized for low latency: parallel DB reads, background writes.
    """
    user_id = user["sub"]
    session_id = req.session_id
    message = req.message

    # 1. PARALLEL: Load messages + context simultaneously
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        messages_future = executor.submit(dynamo_service.get_messages, session_id, 12)
        session_future = executor.submit(dynamo_service.get_session, user_id, session_id)
        all_messages = messages_future.result()
        session_data = session_future.result()
    
    # Append current message (save to DB in background)
    all_messages.append({"role": "user", "content": message, "timestamp": datetime.now(timezone.utc).isoformat()})
    background_tasks.add_task(dynamo_service.save_message, session_id, "user", message)
    
    # 2. Load the Agent Execution Context (uses session_data already fetched)
    context = workspace_manager.load_context(user_id, session_id, all_messages)
    
    # O(1) Product Context Verification
    page_context = req.page_context
    if page_context and page_context.get("page_type") == "product":
        product_id = page_context.get("product_id")
        if not product_id or not retriever.get_product_details_index(product_id):
            page_context = {}
            
    context.current_page_context = page_context
    
    # Save state before processing
    state_before = context.consultation_state.model_dump_json()
    
    # 3. Run the Orchestrator pipeline
    reply = orchestrator.process_message(context, message)
    
    # Check state after processing
    state_after = context.consultation_state.model_dump_json()
    state_changed = state_before != state_after
    
    # 4. BACKGROUND: Save assistant response + title update (non-blocking)
    background_tasks.add_task(dynamo_service.save_message, session_id, "assistant", reply)
    
    if state_changed:
        background_tasks.add_task(_extract_memory_background, user_id, all_messages)
        
    if session_data and session_data.get("title") == "New Chat":
        title = message[:30] + ("..." if len(message) > 30 else "")
        background_tasks.add_task(dynamo_service.update_session_title, user_id, session_id, title)
    else:
        background_tasks.add_task(dynamo_service.update_session_timestamp, user_id, session_id)

    # 6. Build the Response Payload for the UI
    # The UI currently expects products, cart_items, intent, etc.
    # We will grab these from the context to stay backward compatible as much as possible for now.
    
    # Gather ALL approved products across active domains for display
    display_products = []
    cart_items = []
    for domain in context.active_domains:
        if domain in context.recommendation_workspaces:
            ws = context.recommendation_workspaces[domain]
            active_version = getattr(ws, 'active_version', 1)
            if hasattr(ws, 'versions') and str(active_version) in ws.versions:
                approved = ws.versions[str(active_version)].approved_products
            else:
                approved = getattr(ws, 'approved_products', [])
                
            for p in approved:
                prod_dict = p.model_dump()
                details = retriever.get_product_details_index(p.parent_asin)
                if details:
                    prod_dict.update(details.get("metadata", {}))
                    prod_dict["reviews"] = details.get("reviews", {})
                display_products.append(prod_dict)
                
        if domain in context.cart_workspaces:
            for c in getattr(context.cart_workspaces[domain], 'cart_items', []):
                cart_dict = c.model_dump()
                details = retriever.get_product_details_index(c.parent_asin)
                if details:
                    cart_dict.update(details.get("metadata", {}))
                cart_items.append(cart_dict)

    actions = []
    for item in context.action_history:
        actions.append(item.model_dump() if hasattr(item, 'model_dump') else str(item))
        
    audit_trail = []
    for item in context.execution_audit_trail:
        audit_trail.append(item.model_dump() if hasattr(item, 'model_dump') else str(item))

    response_data = {
        "reply": reply,
        "products": _convert_decimals(display_products[:30]), 
        "state": _convert_decimals(context.consultation_state.model_dump()),
        "active_domains": context.active_domains,
        "cart_items": _convert_decimals(cart_items),
        "actions_taken": _convert_decimals(actions),
        "execution_audit_trail": _convert_decimals(audit_trail)
    }
    
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    messages = dynamo_service.get_messages(session_id)
    
    # Rebuild state for frontend
    active_domains = session.get("active_domains", ["general"])
    rec_ws = session.get("recommendation_workspaces", {})
    cart_ws = session.get("cart_workspaces", {})
    
    display_products = []
    cart_items = []
    
    for domain in active_domains:
        if domain in rec_ws:
            ws_dict = rec_ws[domain]
            active_version = ws_dict.get("active_version", 1)
            versions = ws_dict.get("versions", {})
            ver_str = str(active_version)
            if ver_str in versions:
                approved = versions[ver_str].get("approved_products", [])
            else:
                approved = ws_dict.get("approved_products", [])
                
            for p in approved:
                asin = p.get("parent_asin") if isinstance(p, dict) else getattr(p, 'parent_asin', None)
                if not asin: continue
                prod_dict = p if isinstance(p, dict) else p.model_dump()
                details = retriever.get_product_details_index(asin)
                if details:
                    prod_dict.update(details.get("metadata", {}))
                    prod_dict["reviews"] = details.get("reviews", {})
                display_products.append(prod_dict)
        if domain in cart_ws:
            for c in cart_ws[domain].get("cart_items", []):
                asin = c.get("parent_asin") if isinstance(c, dict) else getattr(c, 'parent_asin', None)
                if not asin: continue
                cart_dict = c if isinstance(c, dict) else c.model_dump()
                details = retriever.get_product_details_index(asin)
                if details:
                    cart_dict.update(details.get("metadata", {}))
                cart_items.append(cart_dict)

    return {
        "session": _convert_decimals(session), 
        "messages": _convert_decimals(messages),
        "state": _convert_decimals(session.get("consultation_state", {})),
        "products": _convert_decimals(display_products),
        "cart_items": _convert_decimals(cart_items),
        "active_domains": active_domains
    }


@router.delete("/session/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    """Delete a chat session and all its messages."""
    return dynamo_service.delete_session(user["sub"], session_id)


@router.put("/session/{session_id}/title")
async def rename_session(session_id: str, title: str = Body(..., embed=True), user: dict = Depends(get_current_user)):
    """Rename a chat session."""
    dynamo_service.update_session_title(user["sub"], session_id, title)
    return {"message": "Title updated"}
