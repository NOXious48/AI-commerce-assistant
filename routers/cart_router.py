import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.jwt_verifier import get_current_user
from db.dynamo_service import DynamoService
from retrieval import retriever
from review_filter_agent import review_data_index

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

@router.post("/cart/add")
def add_to_cart(req: CartAddRequest, user: dict = Depends(get_current_user)):
    user_id = user["sub"]
    session = dynamo_service.get_session(user_id, req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    cart_items = session.get("cart_items", [])
    
    # Check if exists
    found = False
    for item in cart_items:
        if item["product_id"] == req.product_id:
            item["quantity"] += req.quantity
            found = True
            break
            
    if not found:
        # Fetch metadata to populate cart item
        product_meta = retriever.metadata.get(req.product_id) or retriever.catalog.get(req.product_id)
        if not product_meta:
            raise HTTPException(status_code=404, detail="Product not found")
            
        cart_items.append({
            "product_id": req.product_id,
            "title": product_meta.get("title", "Unknown Product"),
            "price": product_meta.get("price", 0.0),
            "quantity": req.quantity,
            "image": product_meta.get("image_url", ""),
            "added_at": datetime.now(timezone.utc).isoformat(),
            "source_context": session.get("consultation_state", {}).get("goal", ""),
            "added_by": "user",
            "added_reason": "Manually added by user"
        })
        
    # Update manual adds in workspace
    workspace = session.get("cart_workspace", {})
    if req.product_id not in workspace.get("manually_added_asins", []):
        if "manually_added_asins" not in workspace:
            workspace["manually_added_asins"] = []
        workspace["manually_added_asins"].append(req.product_id)
        dynamo_service.update_cart_workspace(user_id, req.session_id, workspace)
        
    success = dynamo_service.update_cart_items(user_id, req.session_id, cart_items)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update cart")
        
    return {"message": "Added to cart", "cart_items": cart_items}

@router.post("/cart/remove")
def remove_from_cart(req: CartRemoveRequest, user: dict = Depends(get_current_user)):
    user_id = user["sub"]
    session = dynamo_service.get_session(user_id, req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    cart_items = session.get("cart_items", [])
    new_cart = []
    
    for item in cart_items:
        if item["product_id"] == req.product_id:
            if not req.fully_remove and item["quantity"] > 1:
                item["quantity"] -= 1
                new_cart.append(item)
        else:
            new_cart.append(item)
            
    # Update manual removes in workspace if fully removed
    if req.fully_remove:
        workspace = session.get("cart_workspace", {})
        if req.product_id not in workspace.get("manually_removed_asins", []):
            if "manually_removed_asins" not in workspace:
                workspace["manually_removed_asins"] = []
            workspace["manually_removed_asins"].append(req.product_id)
            dynamo_service.update_cart_workspace(user_id, req.session_id, workspace)
            
    success = dynamo_service.update_cart_items(user_id, req.session_id, new_cart)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update cart")
        
    return {"message": "Cart updated", "cart_items": new_cart}

@router.post("/cart/clear")
def clear_cart(req: CartClearRequest, user: dict = Depends(get_current_user)):
    user_id = user["sub"]
    session = dynamo_service.get_session(user_id, req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Full clear from UI
    success = dynamo_service.clear_cart(user_id, req.session_id, keep_user_items=False)
    
    # Archive workspace
    workspace = session.get("cart_workspace", {})
    if workspace:
        workspace["previous_version"] = workspace.get("version", 0)
        workspace["version"] = workspace.get("version", 0) + 1
        workspace["status"] = "archived"
        workspace["last_updated"] = datetime.now(timezone.utc).isoformat()
        workspace["update_reason"] = "User explicitly cleared entire cart."
        dynamo_service.update_cart_workspace(user_id, req.session_id, workspace)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear cart")
        
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
