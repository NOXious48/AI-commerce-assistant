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
    confidence: int = 0
    approval_reasons: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    rejection_reasons: List[str] = Field(default_factory=list)
    retrieval_query: Optional[str] = None

class CandidateRecord(BaseModel):
    asin: str
    retrieval_score: float = 0.0
    retrieval_rank: int = 0

class ComparisonWorkspace(BaseModel):
    selected_products: List[str] = Field(default_factory=list)

class RecommendationVersion(BaseModel):
    workspace_id: str = ""
    version: int = 1
    plan_id: Optional[str] = None
    domain: str = "general"
    status: str = "draft" # draft, active, stale, archived
    created_at: str = ""
    last_updated: str = ""
    stale_after_hours: int = 72
    refresh_reason: Optional[str] = None
    retrieval_query: str = ""
    retrieval_timestamp: str = ""
    retrieval_source: str = ""
    embedding_model: str = "amazon_titan_v2"
    retrieval_top_k: int = 20
    constraint_snapshot: Dict[str, Any] = Field(default_factory=dict)
    recommendation_context: RecommendationContext = Field(default_factory=RecommendationContext)
    candidate_pool: List[CandidateRecord] = Field(default_factory=list)
    approved_products: List[ProductRecord] = Field(default_factory=list)
    rejected_products: List[ProductRecord] = Field(default_factory=list)
    comparison_workspace: ComparisonWorkspace = Field(default_factory=ComparisonWorkspace)

class DomainRecommendationWorkspace(BaseModel):
    active_version: int = 1
    versions: Dict[str, RecommendationVersion] = Field(default_factory=dict)

class CartItem(BaseModel):
    parent_asin: str
    quantity: int = 1
    added_by: str = "ai"  # "ai" or "user"
    domain: str = "general"
    category_target: str = ""
    added_reason: str = ""
    recommendation_version: int = 0

class DomainCartWorkspace(BaseModel):
    version: int = 1
    status: str = "active"
    cart_items: List[CartItem] = Field(default_factory=list)
    manually_removed_items: List[str] = Field(default_factory=list)
    manually_added_items: List[str] = Field(default_factory=list)

class ActionHistoryItem(BaseModel):
    timestamp: str
    agent: str
    action: str
    domain: str

class AuditTrailItem(BaseModel):
    timestamp: str
    agent: str
    domain: str
    workspace_version: int = 0
    source: str = ""
    latency_ms: int = 0
    result: str = ""
    summary: str = ""
    retrieved: int = 0
    approved: int = 0
    rejected: int = 0
    approval_rate: int = 0

class ShoppingProfile(BaseModel):
    recently_viewed_products: List[str] = Field(default_factory=list)
    favorite_categories: List[str] = Field(default_factory=list)
    saved_products: List[str] = Field(default_factory=list)

# ---------------------------------------------------------------------------
# Global Execution Context
# ---------------------------------------------------------------------------

class UserMemory(BaseModel):
    memory_type: str = ""
    value: str = ""
    confidence: int = 0
    confirmed: bool = False
    expires_after_days: int = 14

class ShoppingPlan(BaseModel):
    plan_id: str
    version: int = 1
    domain: str = "general"
    status: str = "draft" # draft, active, completed, archived
    event: str = ""
    assumptions: Dict[str, Any] = Field(default_factory=dict)
    strategy: str = ""
    last_updated: str = ""

class AgentExecutionContext(BaseModel):
    """
    Shared context object passed through the entire agent pipeline.
    Agents mutate this object in-memory. WorkspaceManager handles persistence.
    """
    session_id: str
    user_id: str
    
    # Core state
    consultation_state: ConsultationState = Field(default_factory=ConsultationState)
    user_memory: Dict[str, Any] = Field(default_factory=dict) # Key: type, Value: List[UserMemory]
    
    # Workspaces
    active_domains: List[str] = Field(default_factory=lambda: ["general"])
    search_workspace: Dict[str, Any] = Field(default_factory=dict)
    planning_workspace: Dict[str, ShoppingPlan] = Field(default_factory=dict) # Key: plan_id
    recommendation_workspaces: Dict[str, DomainRecommendationWorkspace] = Field(default_factory=dict)
    cart_workspaces: Dict[str, DomainCartWorkspace] = Field(default_factory=dict)
    product_interactions: Dict[str, Any] = Field(default_factory=lambda: {"clicked": [], "saved": [], "compared": []})
    shopping_profile: ShoppingProfile = Field(default_factory=ShoppingProfile)
    
    # Request tracking
    recent_messages: List[Dict[str, str]] = Field(default_factory=list)
    action_history: List[ActionHistoryItem] = Field(default_factory=list)
    execution_audit_trail: List[AuditTrailItem] = Field(default_factory=list)
    current_page_context: Dict[str, Any] = Field(default_factory=dict)

# ---------------------------------------------------------------------------
# Strict Agent Output Contracts
# ---------------------------------------------------------------------------

class PlanningAgentOutput(BaseModel):
    shopping_plan: ShoppingPlan
    
class CategoryTarget(BaseModel):
    category: str
    quantity: int = 1
    budget_share: float = 0.0

class CartPlannerOutput(BaseModel):
    category_targets: List[CategoryTarget] = Field(default_factory=list)

class RecommendationAgentOutput(BaseModel):
    candidate_pool: List[CandidateRecord] = Field(default_factory=list)
    retrieval_query: str = ""
    source: str = ""
    latency_ms: int = 0
    clarification_required: bool = False

class ReviewAgentOutput(BaseModel):
    approved_products: List[ProductRecord] = Field(default_factory=list)
    rejected_products: List[ProductRecord] = Field(default_factory=list)

class CartAgentOutput(BaseModel):
    cart_action: str  # "add", "remove", "clear", "none"
    cart_items: List[CartItem] = Field(default_factory=list)
    missing_categories: List[str] = Field(default_factory=list)
    cart_changes: List[str] = Field(default_factory=list)

class ClarificationQuestion(BaseModel):
    question: str
    priority: int = 1
    question_type: str = "general" # budget, people_count, category, diet, brand, usage

class ConversationAgentOutput(BaseModel):
    response: str = ''
    updated_state: Dict[str, Any] = Field(default_factory=dict)
    goal_abandoned: bool = False
    abandoned_goal: Optional[str] = None

