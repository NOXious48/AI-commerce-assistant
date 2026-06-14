import logging
from typing import Dict, Any
from agents.models import AgentExecutionContext

logger = logging.getLogger(__name__)

class ActionContextBuilder:
    """
    Summarizes the entire AgentExecutionContext into a compact dictionary
    that can be safely passed to the ConversationAgent's LLM prompt without
    causing context bloat.
    """
    
    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service
        
    def build_context(self, context: AgentExecutionContext) -> Dict[str, Any]:
        """
        Extracts and summarizes only the relevant portions of the workspace state.
        """
        # 1. Current Product Context (What the user is looking at right now)
        current_product = None
        if context.current_page_context and context.current_page_context.get("page_type") == "product":
            asin = context.current_page_context.get("product_id")
            if asin:
                details = self.retrieval_service.get_product_details_index(asin)
                if details:
                    meta = details.get("metadata", {})
                    current_product = {
                        "asin": asin,
                        "title": meta.get("title"),
                        "brand": meta.get("brand"),
                        "price": meta.get("price")
                    }
                    
        page_context = context.current_page_context

        # 2. Cart Summary (Merge all domain carts)
        cart_items = []
        estimated_total = 0.0
        for domain, cart_ws in context.cart_workspaces.items():
            for item in getattr(cart_ws, 'cart_items', []):
                details = self.retrieval_service.get_product_details_index(item.parent_asin)
                if details:
                    meta = details.get("metadata", {})
                    price = meta.get("price", 0.0)
                    estimated_total += price * item.quantity
                    cart_items.append({
                        "domain": domain,
                        "title": meta.get("title", item.parent_asin),
                        "price": price,
                        "quantity": item.quantity,
                        "category_target": item.category_target,
                        "added_by": getattr(item, 'added_by', 'ai')
                    })
        
        cart_summary = {
            "total_items": sum(item["quantity"] for item in cart_items),
            "estimated_total": round(estimated_total, 2),
            "items": cart_items
        }

        # 3. Recommendation Summary (Top 3 approved per domain from Active Version)
        recommendation_summary = {}
        for domain, rec_ws in context.recommendation_workspaces.items():
            top_products = []
            
            active_version_id = str(getattr(rec_ws, 'active_version', 1))
            if hasattr(rec_ws, 'versions') and active_version_id in rec_ws.versions:
                approved = rec_ws.versions[active_version_id].approved_products
            else:
                approved = getattr(rec_ws, 'approved_products', [])
                
            for p in approved[:3]: # Only take top 3
                details = self.retrieval_service.get_product_details_index(p.parent_asin)
                if details:
                    meta = details.get("metadata", {})
                    top_products.append({
                        "title": meta.get("title"),
                        "price": meta.get("price"),
                        "category": getattr(p, 'category', ''),
                        "why_approved": " ".join(getattr(p, 'approval_reasons', [])) or getattr(p, 'approval_reason', '')
                    })
            if top_products:
                recommendation_summary[domain] = top_products

        # 4. Plan Summary
        plan_summary = {}
        for domain, plan in getattr(context, 'planning_workspace', {}).items():
            plan_summary[domain] = {
                "event": plan.event,
                "strategy": plan.strategy,
                "assumptions": plan.assumptions,
                "status": plan.status
            }

        # 5. Recently Viewed
        recently_viewed = []
        for asin in context.shopping_profile.recently_viewed_products[:5]:
            details = self.retrieval_service.get_product_details_index(asin)
            if details:
                meta = details.get("metadata", {})
                recently_viewed.append({
                    "title": meta.get("title"),
                    "price": meta.get("price")
                })

        # 6. Action History
        actions = []
        for item in context.action_history:
            if hasattr(item, 'action'):
                actions.append(item.action)
            else:
                actions.append(str(item))

        # Build Final Payload
        # Include product_info_lookup if the orchestrator retrieved product details
        product_info_lookup = None
        if context.current_page_context and context.current_page_context.get("product_info_lookup"):
            lookup = context.current_page_context["product_info_lookup"]
            meta = lookup.get("metadata", {})
            reviews = lookup.get("reviews", {})
            raw_reviews = lookup.get("raw_reviews", [])
            
            # Format raw reviews for the LLM (top reviews with text)
            formatted_reviews = []
            for r in raw_reviews[:6]:
                formatted_reviews.append({
                    "rating": r.get("rating", 0),
                    "title": r.get("title", ""),
                    "text": r.get("text", "")[:300],
                    "verified": r.get("verified_purchase", False),
                    "helpful_votes": r.get("helpful_vote", 0)
                })
            
            product_info_lookup = {
                "title": meta.get("title", ""),
                "brand": meta.get("brand", ""),
                "price": meta.get("price", 0),
                "category": meta.get("category", ""),
                "description": meta.get("description", ""),
                "features": meta.get("features", [])[:10],
                "avg_rating": reviews.get("avg_rating", 0),
                "total_reviews": reviews.get("total_reviews", 0),
                "positive_highlights": reviews.get("positive_highlights", [])[:5],
                "negative_highlights": reviews.get("negative_highlights", [])[:5],
                "customer_reviews": formatted_reviews,
            }

        return {
            "active_domains": context.active_domains,
            "page_context": page_context,
            "current_product": current_product,
            "product_info_lookup": product_info_lookup,
            "cart_summary": cart_summary,
            "recommendation_summary": recommendation_summary,
            "plan_summary": plan_summary,
            "user_memory": context.user_memory,
            "recently_viewed_products": recently_viewed,
            "actions_taken": actions
        }
