from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Workspace & State Schemas
# ---------------------------------------------------------------------------

class ConsultationState(BaseModel):
    dietary_preferences: List[str] = Field(default_factory=list)
    budget_preference: str = ""
    favorite_brands: List[str] = Field(default_factory=list)
    avoided_brands: List[str] = Field(default_factory=list)
    other_notes: str = ""

class RecommendationContext(BaseModel):
    goal: str = ""
    budget: str = "moderate"
    people_count: int = 1
    dietary_preferences: List[str] = Field(default_factory=list)

class ProductRecord(BaseModel):
    parent_asin: str
    category: str = ""
    alignment_score: int = 0
    approval_reason: Optional[str] = None
    rejection_reason: Optional[str] = None

class DomainRecommendationWorkspace(BaseModel):
    version: int = 1
    recommendation_context: RecommendationContext = Field(default_factory=RecommendationContext)
    candidate_products: List[str] = Field(default_factory=list)  # ASINs
    approved_products: List[ProductRecord] = Field(default_factory=list)
    rejected_products: List[ProductRecord] = Field(default_factory=list)

class CartItem(BaseModel):
    parent_asin: str
    quantity: int = 1
    added_by: str = "ai"  # "ai" or "user"
    domain: str = "general"
    category_target: str = ""
    added_reason: str = ""

class DomainCartWorkspace(BaseModel):
    version: int = 1
    status: str = "active"
    cart_items: List[CartItem] = Field(default_factory=list)
    manually_removed_items: List[str] = Field(default_factory=list)
    manually_added_items: List[str] = Field(default_factory=list)

# ---------------------------------------------------------------------------
# Global Execution Context
# ---------------------------------------------------------------------------

class AgentExecutionContext(BaseModel):
    """
    Shared context object passed through the entire agent pipeline.
    Agents mutate this object in-memory. WorkspaceManager handles persistence.
    """
    session_id: str
    user_id: str
    
    # Core state
    consultation_state: ConsultationState = Field(default_factory=ConsultationState)
    user_memory: Dict[str, Any] = Field(default_factory=dict)
    
    # Workspaces
    active_domains: List[str] = Field(default_factory=lambda: ["general"])
    recommendation_workspaces: Dict[str, DomainRecommendationWorkspace] = Field(default_factory=dict)
    cart_workspaces: Dict[str, DomainCartWorkspace] = Field(default_factory=dict)
    
    # Request tracking
    recent_messages: List[Dict[str, str]] = Field(default_factory=list)
    action_history: List[str] = Field(default_factory=list)

# ---------------------------------------------------------------------------
# Strict Agent Output Contracts
# ---------------------------------------------------------------------------

class PlanningAgentOutput(BaseModel):
    event: str
    
class CartPlannerOutput(BaseModel):
    required_categories: List[str] = Field(default_factory=list)
    optional_categories: List[str] = Field(default_factory=list)

class RecommendationAgentOutput(BaseModel):
    candidate_products: List[str] = Field(default_factory=list)

class ReviewAgentOutput(BaseModel):
    approved_products: List[ProductRecord] = Field(default_factory=list)
    rejected_products: List[ProductRecord] = Field(default_factory=list)

class CartAgentOutput(BaseModel):
    cart_action: str  # "add", "remove", "clear", "none"
    cart_items: List[CartItem] = Field(default_factory=list)
    missing_categories: List[str] = Field(default_factory=list)

class ConversationAgentOutput(BaseModel):
    intent: str = ''
    interaction_type: str = ''
    user_goal: str = ''
    goal_changed: bool = False
    goal_abandoned: bool = False
    abandoned_goal: Optional[str] = None
    active_domains: List[str] = Field(default_factory=list)
    response: str = ''
    updated_state: Dict[str, Any] = Field(default_factory=dict)

