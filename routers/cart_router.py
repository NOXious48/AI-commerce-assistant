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
            "source_context": session.get("consultation_state", {}).get("goal", "")
        })
        
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
        
    success = dynamo_service.clear_cart(user_id, req.session_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear cart")
        
    return {"message": "Cart cleared", "cart_items": []}

@router.get("/products/{parent_asin}/details")
def get_product_details(parent_asin: str, session_id: str, user: dict = Depends(get_current_user)):
    user_id = user["sub"]
    
    # 1. Base Metadata
    product_meta = retriever.metadata.get(parent_asin) or retriever.catalog.get(parent_asin)
    if not product_meta:
        raise HTTPException(status_code=404, detail="Product not found")
        
    # 2. Review Summary
    review_summary = review_data_index.get_summary(parent_asin)
    
    # 3. Workspace Context (Why Recommended)
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

    # 4. Generate AI Summary (Cached/Stored dynamically or generated on the fly)
    # Using Gemini for quick generation
    ai_summary = "AI Summary not available."
    try:
        client = genai.Client()
        prompt = (
            f"Write a concise, 2-sentence highly positive shopping summary for the product '{product_meta.get('title')}'.\n"
            f"Consider its features: {product_meta.get('features', [])}\n"
        )
        if approval_reasons:
            prompt += f"Why it was recommended to the user: {approval_reasons}\n"
        if review_summary.get("top_praises"):
            prompt += f"Top review praises: {review_summary.get('top_praises')}\n"
            
        prompt += "\nOutput just the summary, no intro."
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        if response.text:
            ai_summary = response.text.strip()
    except Exception as e:
        logger.warning(f"Failed to generate AI summary: {e}")

    # Build response
    return {
        "metadata": {
            "title": product_meta.get("title", ""),
            "brand": product_meta.get("store", product_meta.get("brand", "")),
            "category": product_meta.get("main_category", ""),
            "price": product_meta.get("price", 0.0),
            "description": product_meta.get("description", ""),
            "features": product_meta.get("features", []),
            "images": product_meta.get("images", [product_meta.get("image_url")]) if "images" in product_meta else [product_meta.get("image_url")],
        },
        "reviews": {
            "avg_rating": review_summary.get("avg_rating", product_meta.get("average_rating", 0)),
            "total_reviews": review_summary.get("total_reviews", product_meta.get("rating_number", 0)),
            "positive_ratio": review_summary.get("positive_ratio", 0),
            "negative_ratio": review_summary.get("negative_ratio", 0),
            "verified_ratio": review_summary.get("verified_ratio", 0),
            "positive_highlights": review_summary.get("top_praises", []),
            "negative_highlights": review_summary.get("top_complaints", []),
        },
        "recommendation": {
            "alignment_score": alignment_score,
            "approval_reasons": approval_reasons,
            "rejected_reasons": rejected_reasons,
            "ai_summary": ai_summary
        }
    }
