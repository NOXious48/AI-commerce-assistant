import logging
from typing import List, Any
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
        
    def run(self, context: AgentExecutionContext, domain: str, candidates: List[Any] = None) -> ReviewAgentOutput:
        from agents.models import CandidateRecord
        
        if domain not in context.recommendation_workspaces:
            return ReviewAgentOutput()
            
        rec_workspace = context.recommendation_workspaces[domain]
        active_version_id = str(rec_workspace.active_version)
        if active_version_id not in rec_workspace.versions:
            return ReviewAgentOutput()
            
        active_version = rec_workspace.versions[active_version_id]
        candidate_pool = candidates if candidates is not None else active_version.candidate_pool
        constraints = active_version.constraint_snapshot
        
        if not candidate_pool:
            return ReviewAgentOutput()
            
        approved = []
        rejected = []
        
        negative_constraints = [c.lower() for c in constraints.get("negative_constraints", [])]
        positive_constraints = [c.lower() for c in constraints.get("positive_constraints", [])]
        preferred_brands = [b.lower() for b in constraints.get("preferred_brands", [])]
        price_range = constraints.get("price_range", {})
        min_price = price_range.get("min")
        max_price = price_range.get("max")
        
        # Diversity tracking
        brand_counts = {}

        for candidate in candidate_pool:
            asin = candidate.asin
            retrieval_score = candidate.retrieval_score
            
            # Check cache/index
            details = self.retrieval_service.get_product_details_index(asin)
            if not details:
                continue
                
            meta = details.get("metadata", {})
            reviews = details.get("reviews", {})
            
            brand = (meta.get("brand") or "").lower()
            price = meta.get("price", 0.0)
            category = meta.get("category") or ""
            
            score = 50 + int(retrieval_score * 10) # Incorporate retrieval score
            confidence = 50
            rejection_reasons = []
            approval_reasons = []
            risk_flags = []
            is_rejected = False
            
            # Stage 1: Hard Rejection (Negative Constraints)
            for neg in negative_constraints:
                if neg in brand or neg in category.lower() or neg in meta.get("title", "").lower():
                    is_rejected = True
                    rejection_reasons.append(f"Contains excluded constraint: {neg}")
                    
            if not is_rejected and negative_constraints:
                # Also check review negative highlights
                neg_highlights = " ".join(reviews.get("negative_highlights", [])).lower()
                for neg in negative_constraints:
                    if neg in neg_highlights:
                        is_rejected = True
                        rejection_reasons.append(f"Reviews indicate possible presence of {neg}")
                        break

            # Stage 1: Budget Filtering
            if price > 0:
                if max_price is not None and price > max_price:
                    is_rejected = True
                    rejection_reasons.append(f"Price (${price}) exceeds max budget (${max_price})")
                if min_price is not None and price < min_price:
                    is_rejected = True
                    rejection_reasons.append(f"Price (${price}) is below min budget (${min_price})")
                        
            if is_rejected:
                rejected.append(ProductRecord(
                    parent_asin=asin,
                    category=category,
                    rejection_reasons=rejection_reasons
                ))
                continue
                
            # Stage 2: Scoring
            if brand and brand in preferred_brands:
                score += 15
                confidence += 10
                approval_reasons.append("One of your preferred brands.")
                
            for pos in positive_constraints:
                if pos in meta.get("title", "").lower() or pos in category.lower():
                    score += 10
                    confidence += 5
                    approval_reasons.append(f"Matches preference: {pos}")
                
            avg_rating = reviews.get("avg_rating", 0)
            if avg_rating >= 4.0:
                score += 15
                confidence += 20
                approval_reasons.append("Highly rated.")
            elif avg_rating < 3.5:
                score -= 15
                risk_flags.append("Lower than average rating.")
                
            if reviews.get("positive_ratio", 0) > 0.7:
                score += 10
                
            if price > 0 and max_price is not None and price <= max_price:
                approval_reasons.append("Fits your budget.")
            
            # Stage 3: Diversity Guard
            if brand:
                if brand_counts.get(brand, 0) >= 3:
                    score -= 50 # Strongly penalize to enforce diversity
                    risk_flags.append("Too many products from this brand already.")
                
            if score >= self.threshold:
                if brand:
                    brand_counts[brand] = brand_counts.get(brand, 0) + 1
                    
                approved.append(ProductRecord(
                    parent_asin=asin,
                    category=category,
                    alignment_score=min(100, score),
                    confidence=min(100, confidence),
                    approval_reasons=approval_reasons,
                    risk_flags=risk_flags
                ))
            else:
                rejected.append(ProductRecord(
                    parent_asin=asin,
                    category=category,
                    rejection_reasons=["Did not meet alignment thresholds."]
                ))
                
        # Sort approved by score
        approved.sort(key=lambda x: x.alignment_score, reverse=True)
        approved = approved[:self.max_approved]
        
        logger.info(f"[ReviewAgent] Evaluated {len(candidate_pool)} candidates. Approved {len(approved)}, Rejected {len(rejected)}")
        return ReviewAgentOutput(approved_products=approved, rejected_products=rejected)
