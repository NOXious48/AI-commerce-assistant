import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.jwt_verifier import get_current_user
from db.dynamo_service import DynamoService
from services.retrieval_service import retriever


from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["cart", "products"])
dynamo_service = DynamoService()

class CartAddRequest(BaseModel):
    session_id: str
    product_id: str
    quantity: int = 1

class CartRemoveRequest(BaseModel):
    session_id: str
    product_id: str
    fully_remove: bool = False

class CartClearRequest(BaseModel):
    session_id: str

from agents.workspace_manager import WorkspaceManager
from agents.cart_agent import CartAgent

@router.post("/cart/add")
def add_to_cart(req: CartAddRequest, user: dict = Depends(get_current_user)):
    user_id = user["sub"]
    workspace_manager = WorkspaceManager(dynamo_service)
    context = workspace_manager.load_context(user_id, req.session_id, [])
    
    # Determine domain
    domain = "general_shopping"
    for d, ws in context.recommendation_workspaces.items():
        if hasattr(ws, 'versions'):
            for v in ws.versions.values():
                for p in getattr(v, 'approved_products', []):
                    if p.parent_asin == req.product_id:
                        domain = d
        else:
            for p in getattr(ws, 'approved_products', []):
                if p.parent_asin == req.product_id:
                    domain = d
                    
    workspace_manager.ensure_domain(context, domain)
    
    # Add the product with the requested quantity
    from agents.models import CartItem
    cart_ws = context.cart_workspaces[domain]
    existing = next((i for i in cart_ws.cart_items if i.parent_asin == req.product_id), None)
    if existing:
        existing.quantity += req.quantity
    else:
        new_item = CartItem(
            parent_asin=req.product_id,
            quantity=req.quantity,
            added_by="user",
            domain=domain,
            category_target="",
            added_reason="Added directly by user",
            recommendation_version=0
        )
        cart_ws.cart_items.append(new_item)
    
    if req.product_id not in cart_ws.manually_added_items:
        cart_ws.manually_added_items.append(req.product_id)
        
    workspace_manager.persist_context(context)
    
    # Build enriched response for the frontend
    cart_items_response = []
    for item in cart_ws.cart_items:
        item_dict = item.model_dump()
        details = retriever.get_product_details_index(item.parent_asin)
        if details:
            item_dict.update(details.get("metadata", {}))
        cart_items_response.append(item_dict)
    
    return {"message": "Added to cart", "cart_items": cart_items_response}

@router.post("/cart/remove")
def remove_from_cart(req: CartRemoveRequest, user: dict = Depends(get_current_user)):
    user_id = user["sub"]
    workspace_manager = WorkspaceManager(dynamo_service)
    context = workspace_manager.load_context(user_id, req.session_id, [])
    
    domain = "general_shopping"
    for d, ws in context.cart_workspaces.items():
        for i in getattr(ws, 'cart_items', []):
            if getattr(i, 'parent_asin', '') == req.product_id:
                domain = d
                break
                
    workspace_manager.ensure_domain(context, domain)
    cart_agent = CartAgent()
    out = cart_agent.run(context, domain, requested_action="remove", requested_product=req.product_id, source="user")
    
    if out.cart_action == "remove":
        context.cart_workspaces[domain].cart_items = out.cart_items
        
    workspace_manager.persist_context(context)
    
    # Build enriched response
    cart_items_response = []
    for item in context.cart_workspaces[domain].cart_items:
        item_dict = item.model_dump()
        details = retriever.get_product_details_index(item.parent_asin)
        if details:
            item_dict.update(details.get("metadata", {}))
        cart_items_response.append(item_dict)
    
    return {"message": "Cart updated", "cart_items": cart_items_response}

@router.post("/cart/clear")
def clear_cart(req: CartClearRequest, user: dict = Depends(get_current_user)):
    user_id = user["sub"]
    workspace_manager = WorkspaceManager(dynamo_service)
    context = workspace_manager.load_context(user_id, req.session_id, [])
    
    cart_agent = CartAgent()
    for domain in list(context.cart_workspaces.keys()):
        out = cart_agent.run(context, domain, requested_action="clear", source="user")
        if out.cart_action == "clear":
            context.cart_workspaces[domain].cart_items = out.cart_items
            
    workspace_manager.persist_context(context)
    return {"message": "Cart cleared", "cart_items": []}

@router.get("/products/{parent_asin}/details")
def get_product_details(parent_asin: str, session_id: str, user: dict = Depends(get_current_user)):
    user_id = user["sub"]
    
    # 1. Fetch precomputed details (O(1) lookup)
    precomputed = retriever.get_product_details_index(parent_asin)
    
    if not precomputed:
        raise HTTPException(status_code=404, detail="Product not found")

    # 2. Workspace Context (Why Recommended)
    alignment_score = None
    approval_reasons = []
    rejected_reasons = []
    
    session = dynamo_service.get_session(user_id, session_id)
    if session:
        workspace = session.get("recommendation_workspace", {})
        # Check approved
        for p in workspace.get("approved_products", []):
            if p.get("parent_asin") == parent_asin:
                alignment_score = p.get("alignment_score")
                approval_reasons = p.get("approval_reasons", [])
                break
        # Check rejected if not approved
        if alignment_score is None:
            for p in workspace.get("rejected_products", []):
                if p.get("parent_asin") == parent_asin:
                    rejected_reasons = p.get("rejected_reason", [])
                    break

    # 3. Generate AI Summary in background or skip to save latency
    # The user priority mentions caching at startup. For O(1) response, we return early
    # without doing the synchronous Gemini request! (Unless we absolutely need it).
    # Since we need sub-second latency, we'll omit the synchronous generation here.
    ai_summary = "AI Summary generation disabled for latency."

    # Build response using precomputed index
    return {
        "metadata": precomputed["metadata"],
        "reviews": precomputed["reviews"],
        "recommendation": {
            "alignment_score": alignment_score,
            "approval_reasons": approval_reasons,
            "rejected_reasons": rejected_reasons,
            "ai_summary": ai_summary
        }
    }
