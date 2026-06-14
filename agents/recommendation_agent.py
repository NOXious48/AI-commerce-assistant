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
        from agents.models import CandidateRecord
        
        if domain not in context.recommendation_workspaces:
            logger.warning(f"Domain {domain} not found in recommendation workspaces.")
            return RecommendationAgentOutput()
            
        rec_workspace = context.recommendation_workspaces[domain]
        active_version_id = str(rec_workspace.active_version)
        
        if active_version_id not in rec_workspace.versions:
            return RecommendationAgentOutput()
            
        active_version = rec_workspace.versions[active_version_id]
        rec_context = active_version.recommendation_context
        
        # 1. Hard Constraint Validation
        budget_str = rec_context.budget
        # Check if budget is somehow completely missing or 0 (if numeric could be parsed here, but we will rely on Orchestrator setting it correctly).
        # For this demonstration, if the category is totally unspecified in a specific refinement, we might ask clarification.
        if not rec_context.goal and not target_categories:
            return RecommendationAgentOutput(clarification_required=True)
            
        # 5-step workflow
        # 1. Check active domain approved_products & candidate_pool
        existing_approved = active_version.approved_products
        candidate_pool = active_version.candidate_pool
        
        if candidate_pool and len(candidate_pool) > 0:
            is_general_refinement = not target_categories or (len(target_categories) == 1 and target_categories[0] == domain.replace('_', ' '))
            
            # Check if the target categories match what was previously retrieved
            # If user is asking for something different, do fresh retrieval
            prev_query = active_version.retrieval_query.lower() if active_version.retrieval_query else ""
            categories_match_prev = all(
                cat.lower() in prev_query or cat.lower() == domain.replace('_', ' ')
                for cat in (target_categories or [])
            ) if target_categories else True
            
            if is_general_refinement and categories_match_prev:
                # 2. Re-rank (Mock re-rank by returning pool sorted by rank)
                logger.info(f"[RecommendationAgent] Reusing {len(candidate_pool)} existing candidates for refinement.")
                return RecommendationAgentOutput(
                    candidate_pool=candidate_pool,
                    retrieval_query="refinement_reuse",
                    source="workspace_pool",
                    latency_ms=1
                )
        
        # 5. Execute new FAISS Retrieval
        query_parts = []
        if rec_context.goal:
            query_parts.append(rec_context.goal)
        
        constraints = active_version.constraint_snapshot
        if constraints:
            query_parts.extend(constraints.get("positive_constraints", []))
            query_parts.extend(constraints.get("preferred_brands", []))
            query_parts.extend(constraints.get("must_have_features", []))
            
        if target_categories:
            query_parts.append(" ".join(target_categories))
            
        search_query = " ".join(query_parts)
        if not search_query.strip():
            search_query = "best products"  # Fallback
            
        logger.info(f"[RecommendationAgent] Running FAISS retrieval for domain: {domain}, query: '{search_query}'")
        
        import time
        start_t = time.time()
        raw_results = self.retrieval_service.search(query=search_query, top_k=100) # Retrieve 100 max
        latency_ms = int((time.time() - start_t) * 1000)
        
        candidate_records = []
        rank = 1
        for res in raw_results:
            asin = res.get("parent_asin")
            score = float(res.get("similarity_score", res.get("score", 0.0)))
            if asin:
                candidate_records.append(CandidateRecord(
                    asin=asin,
                    retrieval_score=score,
                    retrieval_rank=rank
                ))
                rank += 1
                
        return RecommendationAgentOutput(
            candidate_pool=candidate_records,
            retrieval_query=search_query,
            source="faiss",
            latency_ms=latency_ms
        )
