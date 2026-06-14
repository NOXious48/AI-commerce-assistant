import logging
from typing import List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from auth.jwt_verifier import get_current_user
from db.dynamo_service import dynamo_service
from services.retrieval_service import retriever

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])

@router.get("/home")
async def get_home_recommendations(user: dict = Depends(get_current_user)):
    """
    Home Recommendations Service:
    Populates 'Recommended For You' and 'Top Products' independently of active chat sessions.
    Sources: User memory, Saved products, Cart history, Recent domains.
    """
    user_id = user["sub"]
    
    # 1. Gather context
    user_memory = dynamo_service.get_user_memory(user_id)
    saved_products = dynamo_service.list_saved_products(user_id)
    # We could also look at recent chat sessions for active domains, but for now we'll do a basic retrieval
    
    # 2. Build a query based on memory or fall back to a generic query
    query = "popular electronics and home goods"
    if user_memory.get("favorite_categories"):
        query = " ".join(user_memory["favorite_categories"][:2])
    elif user_memory.get("other_preferences"):
        query = " ".join(user_memory["other_preferences"][:2])
    elif saved_products:
        # If they saved products, maybe recommend something similar (mock query for now)
        query = "products similar to saved items"

    # 3. Retrieve
    # For a real implementation, we would use a more sophisticated recommendation engine.
    # Here we just use the semantic search retriever.
    results = retriever.search(query, top_k=8)
    
    return {"recommendations": results}

@router.get("/similar/{parent_asin}")
async def get_similar_products(parent_asin: str, user: dict = Depends(get_current_user)):
    """
    Product Page Similar Shelf.
    """
    # Simply get product details, use its category or title to search
    details = retriever.get_product_details_index(parent_asin)
    if not details:
        raise HTTPException(status_code=404, detail="Product not found")
        
    category = details.get("metadata", {}).get("main_category", "")
    query = f"similar to {category}" if category else "popular items"
    
    results = retriever.search(query, top_k=8)
    
    products = []
    for r in results:
        if r.get("parent_asin") == parent_asin:
            continue # skip the item itself
        prod_dict = r.get("metadata", {})
        prod_dict["parent_asin"] = r.get("parent_asin")
        products.append(prod_dict)
        
    return {"similar_products": products[:6]}

@router.get("/search")
async def search_products(q: str, top_k: int = 20):
    """
    Standard Search Results Page.
    Fetches matching products from the vector database.
    """
    if not q:
        return {"products": []}
        
    results = retriever.search(q, top_k=top_k)
    
    products = []
    for r in results:
        prod_dict = r.get("metadata", {})
        prod_dict["parent_asin"] = r.get("parent_asin")
        prod_dict["similarity_score"] = r.get("score", 0)
            
        products.append(prod_dict)
        
    return {"products": products}

import time
_shelf_cache = {}
CACHE_TTL = 60

@router.get("/shelf")
async def get_shelf(domain: str, session_id: str, version: int = None, user: dict = Depends(get_current_user)):
    """
    Returns curated shelves for a specific domain and session.
    """
    user_id = user["sub"]
    cache_key = f"{session_id}_{domain}_{version}"
    
    if cache_key in _shelf_cache:
        data, expiry = _shelf_cache[cache_key]
        if time.time() < expiry:
            return data

    session = dynamo_service.get_session(user_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    rec_ws = session.get("recommendation_workspaces", {}).get(domain)
    if not rec_ws:
        # Empty state
        return {
            "shelf_type": "empty",
            "domain": domain,
            "recommendation_version": 0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "based_on": {},
            "products": []
        }
        
    # Handle versioning
    target_version_num = version if version else rec_ws.get("active_version", 1)
    versions = rec_ws.get("versions", {})
    
    target_version = versions.get(str(target_version_num))
    if not target_version:
        target_version = rec_ws # fallback to root if versions dict is missing
        
    approved = target_version.get("approved_products", [])
    
    products = []
    for p in approved[:12]: # Limit to 12
        asin = p.get("parent_asin") if isinstance(p, dict) else getattr(p, 'parent_asin', None)
        if not asin: continue
        
        prod_dict = p if isinstance(p, dict) else p.model_dump()
        details = retriever.get_product_details_index(asin)
        if details:
            meta = details.get("metadata", {})
            prod_dict.update(meta)
            
            # Format image_url for ProductCard
            if "images" in meta and meta["images"]:
                if isinstance(meta["images"][0], dict):
                    prod_dict["image_url"] = meta["images"][0].get("hi_res", "") or meta["images"][0].get("large", "")
                elif isinstance(meta["images"][0], str):
                    prod_dict["image_url"] = meta["images"][0]
                    
        products.append(prod_dict)

    # Extract based_on from consultation state
    state = session.get("consultation_state", {})
    based_on = {}
    if state.get("budget_preference"):
        based_on["budget"] = state.get("budget_preference")
    if state.get("dietary_preferences"):
        based_on["dietary_preferences"] = state.get("dietary_preferences")

    response = {
        "shelf_type": "current_plan",
        "domain": domain,
        "recommendation_version": target_version_num,
        "generated_at": target_version.get("generated_at", datetime.now(timezone.utc).isoformat()),
        "based_on": based_on,
        "products": products
    }
    
    _shelf_cache[cache_key] = (response, time.time() + CACHE_TTL)
    return response

def invalidate_shelf_cache(session_id: str, domain: str):
    """Helper to invalidate cache when recommendations change."""
    keys_to_delete = [k for k in _shelf_cache.keys() if k.startswith(f"{session_id}_{domain}")]
    for k in keys_to_delete:
        del _shelf_cache[k]
