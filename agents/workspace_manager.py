import logging
from typing import Dict, Any, List
from agents.models import AgentExecutionContext

logger = logging.getLogger(__name__)

class WorkspaceManager:
    """
    Manages loading, versioning, and persisting the AgentExecutionContext
    workspaces to/from DynamoDB.
    """
    
    def __init__(self, dynamo_service):
        self.db = dynamo_service
        
    def load_context(self, user_id: str, session_id: str, recent_messages: List[Dict[str, str]]) -> AgentExecutionContext:
        """
        Loads the entire execution context from DynamoDB.
        """
        session_data = self.db.get_session(user_id, session_id)
        if not session_data:
            logger.info(f"Creating new context for session {session_id}")
            return AgentExecutionContext(
                session_id=session_id,
                user_id=user_id,
                recent_messages=recent_messages
            )
            
        # Parse from DB state
        try:
            # We assume DynamoService returns dicts directly from the DB
            # We use Pydantic's model_validate to hydrate
            pw = session_data.get("planning_workspace", {})
            if "domains" in pw and isinstance(pw["domains"], dict) and not pw.get("plan_id"):
                pw = {}
                
            context_dict = {
                "session_id": session_id,
                "user_id": user_id,
                "consultation_state": session_data.get("consultation_state", {}),
                "active_domains": session_data.get("active_domains", ["general"]),
                "recommendation_workspaces": session_data.get("recommendation_workspaces", {}),
                "cart_workspaces": session_data.get("cart_workspaces", {}),
                "search_workspace": session_data.get("search_workspace", {}),
                "planning_workspace": pw,
                "comparison_workspace": session_data.get("comparison_workspace", {}), # legacy
                "product_interactions": session_data.get("product_interactions", {"clicked": [], "saved": [], "compared": []}),
                "shopping_profile": session_data.get("shopping_profile", {}),
                "recently_viewed_products": session_data.get("recently_viewed_products", []), # legacy migration
                "recent_messages": recent_messages
            }
            
            # Fetch user memory separately if needed, or pass it in
            user_profile = self.db.get_user(user_id)
            if user_profile:
                context_dict["user_memory"] = user_profile.get("preferences", {})
                
            context = AgentExecutionContext.model_validate(context_dict)
            self.validate_session(context)
            return context
            
        except Exception as e:
            logger.error(f"Failed to hydrate context from DB: {e}")
            # Fallback to fresh context on catastrophic schema failure
            return AgentExecutionContext(
                session_id=session_id,
                user_id=user_id,
                recent_messages=recent_messages
            )

    def persist_context(self, context: AgentExecutionContext):
        """
        Saves the workspaces and state back to DynamoDB.
        """
        self._gc_workspaces(context)
        
        # We only save the fields that belong in ChatSessions
        update_data = {
            "consultation_state": context.consultation_state.model_dump(),
            "active_domains": context.active_domains,
            "recommendation_workspaces": {
                k: v.model_dump() for k, v in context.recommendation_workspaces.items()
            },
            "cart_workspaces": {
                k: v.model_dump() for k, v in context.cart_workspaces.items()
            },
            "search_workspace": context.search_workspace,
            "planning_workspace": {
                k: v.model_dump() for k, v in context.planning_workspace.items()
            },
            "product_interactions": context.product_interactions,
            "shopping_profile": context.shopping_profile.model_dump(),
            "execution_audit_trail": [a.model_dump() for a in context.execution_audit_trail],
            "action_history": [a.model_dump() for a in context.action_history]
        }
        # Convert all floats to Decimal for DynamoDB
        import json
        from decimal import Decimal
        update_data = json.loads(json.dumps(update_data), parse_float=Decimal)
        
        self.db.update_session_workspaces(
            user_id=context.user_id,
            session_id=context.session_id,
            workspaces=update_data
        )
        logger.info(f"Persisted workspaces for session {context.session_id}")

    def _gc_workspaces(self, context: AgentExecutionContext):
        """
        Garbage Collection to prevent DynamoDB bloat.
        Keeps last 5 recommendation versions per domain and last 3 shopping plans overall.
        """
        # GC Recommendation Versions
        for domain, workspace in context.recommendation_workspaces.items():
            if len(workspace.versions) > 5:
                # Sort by version int and keep the top 5
                sorted_versions = sorted(workspace.versions.keys(), key=lambda k: int(k))
                to_delete = sorted_versions[:-5]
                for v in to_delete:
                    del workspace.versions[v]
                    
        # GC Shopping Plans
        if len(context.planning_workspace) > 3:
            # Keep the 3 most recently updated
            sorted_plans = sorted(context.planning_workspace.values(), key=lambda p: p.last_updated)
            to_delete = sorted_plans[:-3]
            for p in to_delete:
                del context.planning_workspace[p.plan_id]

    def invalidate_domain(self, context: AgentExecutionContext, domain: str):
        """
        Safely removes a domain and its associated data when a goal is abandoned.
        """
        if domain in context.active_domains:
            context.active_domains.remove(domain)
            
        if domain in context.recommendation_workspaces:
            # We could archive this instead of deleting, but for now we drop it
            del context.recommendation_workspaces[domain]
            context.action_history.append(f"Invalidated recommendations for {domain}")
            
        if domain in context.cart_workspaces:
            # We clear AI-added items from this domain, but maybe keep the workspace object
            # For strictness, if the domain is gone, we drop the workspace
            del context.cart_workspaces[domain]
            # Need to push to history as a dict since it's an ActionHistoryItem now
            # but action history gets cleared on each message. So just log it.
            logger.info(f"Cleared cart items for {domain}")

    def validate_session(self, context: AgentExecutionContext):
        """Ensures all required data structures exist after load."""
        if not hasattr(context, "shopping_profile") or not context.shopping_profile:
            from agents.models import ShoppingProfile
            context.shopping_profile = ShoppingProfile()
            
        # Migrate legacy recently_viewed_products if any
        if hasattr(context, "recently_viewed_products") and context.recently_viewed_products:
            for item in context.recently_viewed_products:
                if item not in context.shopping_profile.recently_viewed_products:
                    context.shopping_profile.recently_viewed_products.append(item)
            context.recently_viewed_products = [] # Clear legacy
            
    def ensure_domain(self, context: AgentExecutionContext, active_domain: str) -> str:
        """
        Guarantees that a domain and its associated workspaces exist.
        If domain is empty, fallbacks to 'general_shopping'.
        """
        if not active_domain:
            active_domain = "general_shopping"
            
        if active_domain not in context.active_domains:
            context.active_domains.append(active_domain)
            
        from agents.models import DomainRecommendationWorkspace, DomainCartWorkspace
        if active_domain not in context.recommendation_workspaces:
            ws = DomainRecommendationWorkspace()
            context.recommendation_workspaces[active_domain] = ws
            
        if active_domain not in context.cart_workspaces:
            context.cart_workspaces[active_domain] = DomainCartWorkspace()
            
        return active_domain

