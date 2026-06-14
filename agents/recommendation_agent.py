import logging
from typing import List, Optional
from agents.models import AgentExecutionContext, RecommendationAgentOutput

logger = logging.getLogger(__name__)

class RecommendationAgent:
    """
    Recommendation Agent owns retrieval and candidate generation.
    It never writes to workspaces directly. It outputs candidate products.
    """
    
    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service
        
    def run(self, context: AgentExecutionContext, domain: str, target_categories: Optional[List[str]] = None) -> RecommendationAgentOutput:
        """
        Executes candidate retrieval for a given domain.
        
        Args:
            context: The shared execution context.
            domain: The active domain to retrieve for.
            target_categories: Optional list of specific categories to search.
        """
        if domain not in context.recommendation_workspaces:
            logger.warning(f"Domain {domain} not found in recommendation workspaces.")
            return RecommendationAgentOutput(candidate_products=[])
            
        rec_workspace = context.recommendation_workspaces[domain]
        rec_context = rec_workspace.recommendation_context
        
        # Build search query from context
        query_parts = []
        if rec_context.goal:
            query_parts.append(rec_context.goal)
        if rec_context.dietary_preferences:
            query_parts.extend(rec_context.dietary_preferences)
        if target_categories:
            query_parts.append(" ".join(target_categories))
            
        search_query = " ".join(query_parts)
        if not search_query.strip():
            search_query = "best products"  # Fallback
            
        logger.info(f"[RecommendationAgent] Running FAISS retrieval for domain: {domain}, query: '{search_query}'")
        
        # Execute retrieval
        # Retrieval service returns a list of dictionaries with 'parent_asin'
        raw_results = self.retrieval_service.search(query=search_query, top_k=20)
        
        candidate_asins = []
        for res in raw_results:
            asin = res.get("parent_asin")
            if asin:
                candidate_asins.append(asin)
                
        # Return strict output contract
        return RecommendationAgentOutput(candidate_products=candidate_asins)
