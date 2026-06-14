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
            context_dict = {
                "session_id": session_id,
                "user_id": user_id,
                "consultation_state": session_data.get("consultation_state", {}),
                "active_domains": session_data.get("active_domains", ["general"]),
                "recommendation_workspaces": session_data.get("recommendation_workspaces", {}),
                "cart_workspaces": session_data.get("cart_workspaces", {}),
                "recent_messages": recent_messages
            }
            
            # Fetch user memory separately if needed, or pass it in
            user_profile = self.db.get_user(user_id)
            if user_profile:
                context_dict["user_memory"] = user_profile.get("preferences", {})
                
            return AgentExecutionContext.model_validate(context_dict)
            
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
        # We only save the fields that belong in ChatSessions
        update_data = {
            "consultation_state": context.consultation_state.model_dump(),
            "active_domains": context.active_domains,
            "recommendation_workspaces": {
                k: v.model_dump() for k, v in context.recommendation_workspaces.items()
            },
            "cart_workspaces": {
                k: v.model_dump() for k, v in context.cart_workspaces.items()
            }
        }
        
        self.db.update_session_workspaces(
            user_id=context.user_id,
            session_id=context.session_id,
            workspaces=update_data
        )
        logger.info(f"Persisted workspaces for session {context.session_id}")

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
            context.action_history.append(f"Cleared cart items for {domain}")
