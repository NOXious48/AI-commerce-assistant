from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Literal
from enum import Enum

class IntentType(str, Enum):
    GENERAL_CONVERSATION = "general_conversation"
    PRODUCT_EDUCATION = "product_education"
    PRODUCT_COMPARISON = "product_comparison"
    PREFERENCE_GATHERING = "preference_gathering"
    BUYING_CONSULTATION = "buying_consultation"
    RECOMMENDATION_REQUEST = "recommendation_request"
    LIFESTYLE_PLANNING = "lifestyle_planning"
    EVENT_PLANNING = "event_planning"

class RecommendationAction(str, Enum):
    NONE = "none"           # No retrieval needed
    RETRIEVE = "retrieve"   # Fresh retrieval
    REFRESH = "refresh"     # Re-retrieve due to context change
    INVALIDATE = "invalidate"  # Clear products, context shifted domains

class ChatRequest(BaseModel):
    message: str
    session_id: str

class ChatResponse(BaseModel):
    response: str
    thoughts: str
    success: bool

class ProductSchema(BaseModel):
    product_id: str
    title: str
    brand: str
    category: str
    subcategory: str
    price: float
    average_rating: float
    rating_count: int
    description: str
    features: List[str]
    image_url: str
    pros: List[str]
    cons: List[str]
    tags: List[str]
    stock: int
    delivery_time: str
    discount: int
    availability: bool
    popularity_score: float

class ProfileSchema(BaseModel):
    first_name: str
    last_name: str
    email: str
    address: str
    age: int
    allergies: List[str]
    budget: float
    healthy_mode: bool
    green_mode: bool
    workout_goals: str
    strava_stats: str

class CartItemSchema(BaseModel):
    product_id: str
    title: str
    price: float
    quantity: int = 1
    image: Optional[str] = None
    added_at: Optional[str] = None
    source_context: Optional[str] = None

class OrderItemSchema(BaseModel):
    product_id: str
    title: str
    price: float
    quantity: int

class OrderDetailsSchema(BaseModel):
    order_id: str
    email: str
    address: str
    items: List[OrderItemSchema]
    total: float

class ConsultationState(BaseModel):
    goal: Optional[str] = None
    event_category: Optional[str] = None
    event: Optional[str] = None
    budget: Optional[str] = None
    preferred_brands: List[str] = []
    avoided_brands: List[str] = []
    must_have_features: List[str] = []
    nice_to_have_features: List[str] = []
    dietary_preferences: List[str] = []
    allergens: List[str] = []
    usage_context: Optional[str] = None
    people_count: Optional[int] = None
    confidence_score: int = 0

class RecommendationWorkspace(BaseModel):
    """Versioned recommendation context stored in ChatSession."""
    context_hash: str = ""
    active_domain: Optional[str] = None    # "gaming_laptop", "movie_night_snacks"
    retrieved_products: List[dict] = []
    approved_products: List[dict] = []
    rejected_products: List[dict] = []
    filtering_metadata: dict = {}
    version: int = 0
    generated_at: Optional[str] = None
    reason_for_generation: Optional[str] = None

class ReviewFilterResult(BaseModel):
    approved_products: List[dict]
    rejected_products: List[dict]
    filtering_reasons: Dict[str, List[str]]
    approval_reasons: Dict[str, List[str]]
    metrics: dict

class UserMemory(BaseModel):
    dietary_preferences: List[str] = []
    budget_preferences: List[str] = []
    favorite_brands: List[str] = []
    avoided_brands: List[str] = []
    other_preferences: List[str] = []


class ConversationAgentOutput(BaseModel):
    """Structured output schema for the ADK Conversation Agent.
    
    All ADK responses are validated against this model using
    ConversationAgentOutput.model_validate() before being accepted.
    """
    intent: str = "general_conversation"
    response: str = ""
    recommendation_action: Literal[
        "none",
        "retrieve",
        "refresh",
        "invalidate"
    ] = "none"
    reason_for_action: str = ""
    search_query: Optional[str] = None
    updated_state: dict = {}
