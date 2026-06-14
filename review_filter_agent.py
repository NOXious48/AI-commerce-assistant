import os
import json
import logging
import math
from typing import List, Dict, Any, Tuple
from schemas import ReviewFilterResult

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SUMMARIES_PATH = os.path.join(DATA_DIR, "products_reviews", "review_summaries.json")


class ReviewDataIndex:
    """Pre-computed review summaries loaded into memory at startup."""
    def __init__(self):
        self.summaries: Dict[str, Dict[str, Any]] = {}
        self._load_data()

    def _load_data(self):
        if not os.path.exists(SUMMARIES_PATH):
            logger.warning(f"Review summaries not found at {SUMMARIES_PATH}. Filtering will run without reviews.")
            return
            
        try:
            with open(SUMMARIES_PATH, "r", encoding="utf-8") as f:
                self.summaries = json.load(f)
            logger.info(f"Loaded {len(self.summaries)} review summaries.")
        except Exception as e:
            logger.exception(f"Failed to load review summaries: {e}")

    def get_summary(self, parent_asin: str) -> Dict[str, Any]:
        return self.summaries.get(parent_asin, {})


# Global singleton instance loaded once
review_data_index = ReviewDataIndex()


class ReviewFilterAgent:
    """
    Quality-control layer that filters and ranks products based on:
    - Requirement Match (25%)
    - Review Sentiment (20%)
    - User Preference Match (20%)
    - User Memory Match (10%)
    - Budget Compatibility (15%)
    - Consultation Context (10%)
    """

    def __init__(self):
        self.threshold = 60
        self.max_approved = 30

    def filter_products(
        self,
        retrieved_products: List[dict],
        consultation_state: dict,
        user_memory: dict,
        conversation_summary: str = "",
    ) -> ReviewFilterResult:
        """Score, filter, and sort products."""
        
        approved = []
        rejected = []
        filtering_reasons = {}
        approval_reasons = {}

        # Safe parsing of constraints
        avoided_brands = set([b.lower() for b in user_memory.get("avoided_brands", [])] + 
                             [b.lower() for b in consultation_state.get("avoided_brands", [])])
        
        favorite_brands = set([b.lower() for b in user_memory.get("favorite_brands", [])] + 
                              [b.lower() for b in consultation_state.get("preferred_brands", [])])
                              
        dietary_prefs = set([d.lower() for d in user_memory.get("dietary_preferences", [])] + 
                            [d.lower() for d in consultation_state.get("dietary_preferences", [])])
                            
        target_budget = self._parse_budget(consultation_state.get("budget"))

        for product in retrieved_products:
            asin = product.get("parent_asin", "")
            brand = product.get("store", "").lower() or product.get("brand", "").lower()
            
            summary = review_data_index.get_summary(asin)
            score = 0
            reasons = []
            a_reasons = []

            # ==========================================
            # 1. HARD REJECTION RULES
            # ==========================================
            is_rejected = False
            
            if brand and brand in avoided_brands:
                is_rejected = True
                reasons.append(f"Brand '{brand}' is in your avoided list.")

            # Dietary check (heuristic) - If user is GF and top complaints mention gluten
            if dietary_prefs:
                complaints = " ".join(summary.get("top_complaints", [])).lower()
                for d in dietary_prefs:
                    if d in ["gluten free", "gluten_free", "gf"] and "gluten" in complaints:
                        is_rejected = True
                        reasons.append("Reviews indicate product may contain gluten.")
                    if d in ["vegan", "plant based"] and any(x in complaints for x in ["dairy", "meat", "milk"]):
                        is_rejected = True
                        reasons.append(f"Reviews indicate product may not be {d}.")

            # Extreme negative reviews
            if summary and summary.get("negative_ratio", 0) > 0.4:
                is_rejected = True
                reasons.append("Unusually high number of negative reviews (over 40%).")

            if is_rejected:
                filtering_reasons[asin] = reasons
                rejected.append(product)
                continue

            # ==========================================
            # 2. SCORING (Max 100)
            # ==========================================
            
            # A. Requirement Match (25 pts)
            # Uses similarity_score from the retrieval engine as a base proxy
            sim_score = product.get("similarity_score", 0.0)
            req_score = min(25, max(0, int((sim_score + 0.5) * 25))) # Normalizing -1 to 1 around 0->25 loosely
            if sim_score > 0.6: 
                a_reasons.append("Strongly matches your requested features.")
            score += req_score

            # B. Review Sentiment (20 pts)
            if summary:
                pos_ratio = summary.get("positive_ratio", 0.5)
                avg_rating = summary.get("avg_rating", 3.0)
                
                # Formula: (pos_ratio * 10) + ((avg_rating/5) * 10)
                rev_score = (pos_ratio * 10) + ((avg_rating / 5.0) * 10)
                score += rev_score
                
                if pos_ratio > 0.8 and avg_rating >= 4.3:
                    a_reasons.append("Excellent customer satisfaction and high ratings.")
                elif pos_ratio < 0.5:
                    reasons.append("Mixed or poor review sentiment.")
            else:
                score += 10 # Default average if no reviews

            # C. User Preference Match (20 pts)
            pref_score = 10 # Base
            if brand and brand in favorite_brands:
                pref_score += 10
                a_reasons.append(f"Matches your preferred brand ({brand.title()}).")
            score += pref_score

            # D. User Memory Match (10 pts)
            mem_score = 5
            # Simplified: bump if there's any active memory state interacting
            if len(user_memory) > 0 and dict(user_memory) != {}:
                mem_score += 5
                if not any("preferred brand" in r for r in a_reasons):
                    a_reasons.append("Aligns with your saved long-term preferences.")
            score += mem_score

            # E. Budget Compatibility (15 pts)
            budget_score = 15
            price = product.get("price", 0)
            if target_budget and price > 0:
                if price <= target_budget:
                    a_reasons.append("Fits well within your stated budget.")
                else:
                    # Sigmoid penalty if it exceeds budget
                    overage_pct = (price - target_budget) / target_budget
                    # 10% over -> ~ -3 pts, 50% over -> ~ -10 pts, 100% over -> -15 pts
                    penalty = min(15, int(15 * (overage_pct / (overage_pct + 0.5))))
                    budget_score -= penalty
                    reasons.append(f"Price (${price}) exceeds your target budget (${target_budget}).")
            score += budget_score

            # F. Consultation Context (10 pts)
            ctx_score = 10
            # If a goal is specified, we check if it aligns well (already captured in requirement match mostly)
            # Give a free bump if they have an active event
            if consultation_state.get("event"):
                a_reasons.append("Highly relevant for your planned event.")
            score += ctx_score

            # Total Score
            final_score = min(100, max(0, int(score)))

            # Threshold check
            if final_score >= self.threshold:
                # Add score and reasons to product dict
                p_copy = dict(product)
                p_copy["alignment_score"] = final_score
                p_copy["approval_reasons"] = a_reasons[:3] # Keep top 3 reasons
                if not a_reasons:
                    p_copy["approval_reasons"] = ["Solid overall match for your request."]
                    
                approved.append(p_copy)
                approval_reasons[asin] = p_copy["approval_reasons"]
            else:
                if not reasons:
                    reasons.append("Did not meet the minimum quality alignment threshold.")
                filtering_reasons[asin] = reasons
                
                # INJECT rejected_reason for transparency
                p_copy = dict(product)
                p_copy["rejected_reason"] = reasons
                rejected.append(p_copy)

        # Sort approved by alignment_score DESC
        approved.sort(key=lambda x: x.get("alignment_score", 0), reverse=True)
        
        # Keep Top 30
        final_approved = approved[:self.max_approved]
        
        # Any that got sliced off go to rejected
        for sliced_off in approved[self.max_approved:]:
            asin = sliced_off.get("parent_asin")
            sliced_copy = dict(sliced_off)
            sliced_copy["rejected_reason"] = ["Exceeded the maximum display limit (top 30 only)."]
            rejected.append(sliced_copy)
            filtering_reasons[asin] = ["Exceeded the maximum display limit (top 30 only)."]

        avg_score = sum(p.get("alignment_score", 0) for p in final_approved) / len(final_approved) if final_approved else 0

        # Aggregate top rejection reasons
        all_reasons = []
        for r_list in filtering_reasons.values():
            all_reasons.extend(r_list)
        from collections import Counter
        top_rejections = [item[0] for item in Counter(all_reasons).most_common(3)]

        metrics = {
            "retrieved_count": len(retrieved_products),
            "approved_count": len(final_approved),
            "rejected_count": len(rejected),
            "average_alignment_score": round(avg_score, 1),
            "top_rejection_reasons": top_rejections
        }

        return ReviewFilterResult(
            approved_products=final_approved,
            rejected_products=rejected,
            filtering_reasons=filtering_reasons,
            approval_reasons=approval_reasons,
            metrics=metrics
        )

    def _parse_budget(self, budget_val: Any) -> float:
        """Extremely simple parser for '$20', 'under 30', '50.00'."""
        if not budget_val:
            return 0.0
        if isinstance(budget_val, (int, float)):
            return float(budget_val)
        
        s = str(budget_val).lower().replace('$', '').replace(',', '')
        words = s.split()
        for w in words:
            try:
                return float(w)
            except ValueError:
                pass
        return 0.0

# Export a default instance
review_filter_agent = ReviewFilterAgent()
