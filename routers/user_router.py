"""
User Router — User Profile, Preferences, and Saved Products
=============================================================
All endpoints are protected. User identity comes from JWT sub only.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth.jwt_verifier import get_current_user
from db.dynamo_service import dynamo_service

router = APIRouter(prefix="/api/user", tags=["user"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PreferencesUpdate(BaseModel):
    dietary_preferences: List[str] = []
    favorite_categories: List[str] = []
    preferred_brands: List[str] = []
    allergens: List[str] = []
    price_range: Dict = {"min": 0, "max": 50}

class SaveProductRequest(BaseModel):
    parent_asin: str


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.get("/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    """Get current user's profile from DynamoDB."""
    profile = dynamo_service.get_user(user["sub"])
    if not profile:
        return {
            "user_id": user["sub"],
            "email": user.get("email", ""),
            "full_name": "",
            "preferences": {},
        }
    return profile


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

@router.get("/preferences")
async def get_preferences(user: dict = Depends(get_current_user)):
    """Get user preferences."""
    return dynamo_service.get_preferences(user["sub"])


@router.put("/preferences")
async def update_preferences(
    prefs: PreferencesUpdate,
    user: dict = Depends(get_current_user),
):
    """Update user preferences with validated schema."""
    return dynamo_service.update_preferences(user["sub"], prefs.model_dump())


# ---------------------------------------------------------------------------
# Saved Products
# ---------------------------------------------------------------------------

@router.get("/saved-products")
async def list_saved_products(user: dict = Depends(get_current_user)):
    """List all saved products for the current user."""
    return dynamo_service.list_saved_products(user["sub"])


@router.post("/saved-products", status_code=status.HTTP_201_CREATED)
async def save_product(
    req: SaveProductRequest,
    user: dict = Depends(get_current_user),
):
    """Save a product to the user's list."""
    return dynamo_service.save_product(user["sub"], req.parent_asin)


@router.delete("/saved-products/{parent_asin}")
async def unsave_product(
    parent_asin: str,
    user: dict = Depends(get_current_user),
):
    """Remove a product from the user's saved list."""
    return dynamo_service.unsave_product(user["sub"], parent_asin)

# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

class CompareProductRequest(BaseModel):
    parent_asin: str

@router.post("/compare")
async def add_to_compare(req: CompareProductRequest, user: dict = Depends(get_current_user)):
    """Add a product to comparison list (stored in memory for now)."""
    user_id = user["sub"]
    memory = dynamo_service.get_user_memory(user_id)
    comparisons = memory.get("comparisons", [])
    if req.parent_asin not in comparisons:
        comparisons.append(req.parent_asin)
        memory["comparisons"] = comparisons[-4:] # Keep last 4
        dynamo_service.update_user_memory(user_id, memory)
    return {"message": "Added to comparison", "comparisons": memory["comparisons"]}

@router.get("/compare")
async def get_comparisons(user: dict = Depends(get_current_user)):
    """Get the user's current comparison list."""
    user_id = user["sub"]
    memory = dynamo_service.get_user_memory(user_id)
    return {"comparisons": memory.get("comparisons", [])}
