import logging
from typing import List
from agents.models import AgentExecutionContext, ReviewAgentOutput, ProductRecord

logger = logging.getLogger(__name__)

class ReviewAgent:
    """
    Review Agent evaluates candidate products and acts as the gatekeeper.
    It checks products against preferences, budget, and reviews.
    Only approved products are output.
    """
    
    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service
        self.threshold = 60
        self.max_approved = 30
        
    def run(self, context: AgentExecutionContext, domain: str, candidate_asins: List[str]) -> ReviewAgentOutput:
        if domain not in context.recommendation_workspaces:
            return ReviewAgentOutput()
            
        rec_context = context.recommendation_workspaces[domain].recommendation_context
        user_memory = context.user_memory
        consultation_state = context.consultation_state
        
        approved = []
        rejected = []
        
        avoided_brands = set(b.lower() for b in user_memory.get("avoided_brands", []) + consultation_state.avoided_brands)
        favorite_brands = set(b.lower() for b in user_memory.get("favorite_brands", []) + consultation_state.favorite_brands)
        dietary_prefs = set(d.lower() for d in user_memory.get("dietary_preferences", []) + consultation_state.dietary_preferences + rec_context.dietary_preferences)
        
        target_budget_str = rec_context.budget or consultation_state.budget_preference
        target_budget = self._parse_budget(target_budget_str)

        for asin in candidate_asins:
            # Check cache/index
            details = self.retrieval_service.get_product_details_index(asin)
            if not details:
                # If not cached, maybe skip or fetch full
                continue
                
            meta = details.get("metadata", {})
            reviews = details.get("reviews", {})
            
            brand = (meta.get("brand") or "").lower()
            price = meta.get("price", 0.0)
            category = meta.get("category") or ""
            
            score = 50 # Base score
            rejection_reasons = []
            approval_reasons = []
            is_rejected = False
            
            # Hard Rejection: Brand
            if brand and brand in avoided_brands:
                is_rejected = True
                rejection_reasons.append(f"Brand '{brand}' is in your avoided list.")
                
            # Dietary check (heuristic)
            if dietary_prefs:
                neg_highlights = " ".join(reviews.get("negative_highlights", [])).lower()
                for pref in dietary_prefs:
                    if "gluten_free" in pref and "gluten" in neg_highlights:
                        is_rejected = True
                        rejection_reasons.append("Reviews indicate this may contain gluten.")
                        break
                        
            if is_rejected:
                rejected.append(ProductRecord(
                    parent_asin=asin,
                    category=category,
                    rejection_reason=" ".join(rejection_reasons)
                ))
                continue
                
            # Scoring
            if brand and brand in favorite_brands:
                score += 15
                approval_reasons.append("One of your favorite brands.")
                
            if reviews.get("avg_rating", 0) >= 4.0:
                score += 15
                approval_reasons.append("Highly rated.")
            elif reviews.get("avg_rating", 0) < 3.5:
                score -= 15
                
            if reviews.get("positive_ratio", 0) > 0.7:
                score += 10
                
            # Budget scoring
            if target_budget and price > 0:
                if target_budget == "low" and price > 50:
                    score -= 10
                elif target_budget == "high" and price < 50:
                    score -= 5
                elif target_budget == "moderate":
                    if 20 <= price <= 100:
                        score += 10
                        approval_reasons.append("Fits your budget.")
                    elif price > 150:
                        score -= 10
            
            if score >= self.threshold:
                approved.append(ProductRecord(
                    parent_asin=asin,
                    category=category,
                    alignment_score=min(100, score),
                    approval_reason=" ".join(approval_reasons) or "Good match for your request."
                ))
            else:
                rejected.append(ProductRecord(
                    parent_asin=asin,
                    category=category,
                    rejection_reason="Did not meet quality or preference thresholds."
                ))
                
        # Sort approved by score
        approved.sort(key=lambda x: x.alignment_score, reverse=True)
        approved = approved[:self.max_approved]
        
        logger.info(f"[ReviewAgent] Evaluated {len(candidate_asins)} products. Approved {len(approved)}, Rejected {len(rejected)}")
        return ReviewAgentOutput(approved_products=approved, rejected_products=rejected)
        
    def _parse_budget(self, budget_str: str) -> str:
        if not budget_str:
            return ""
        b = budget_str.lower()
        if "cheap" in b or "low" in b or "under" in b:
            return "low"
        if "expensive" in b or "high" in b or "premium" in b:
            return "high"
        return "moderate"
