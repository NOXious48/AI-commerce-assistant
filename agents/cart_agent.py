import logging
from typing import List
from agents.models import AgentExecutionContext, CartAgentOutput, CartItem

logger = logging.getLogger(__name__)

class CartAgent:
    """
    Cart Agent manages cart state using STRICTLY only products
    that are present in the RecommendationWorkspace.approved_products.
    It does not plan, it only executes.
    """
    
    def run(self, context: AgentExecutionContext, domain: str, requested_action: str, requested_category: str = "") -> CartAgentOutput:
        """
        Executes a cart operation.
        
        Args:
            requested_action: "add", "remove", "clear", "none"
            requested_category: the category being targeted (e.g. "snacks")
        """
        if domain not in context.recommendation_workspaces:
            return CartAgentOutput(cart_action="none")
            
        rec_workspace = context.recommendation_workspaces[domain]
        cart_workspace = context.cart_workspaces.get(domain)
        
        current_items = cart_workspace.cart_items if cart_workspace else []
        
        if requested_action == "clear":
            # Keep manual additions, clear AI
            new_items = [i for i in current_items if i.added_by == "user"]
            logger.info(f"[CartAgent] Cleared cart for {domain}")
            return CartAgentOutput(cart_action="clear", cart_items=new_items)
            
        if requested_action == "add" and requested_category:
            # Check if we have an approved product in this category
            approved_for_cat = [p for p in rec_workspace.approved_products 
                                if requested_category.lower() in p.category.lower() or 
                                not p.category] # Fallback if category missing
                                
            # Check if there are any approved products
            if not rec_workspace.approved_products:
                logger.info(f"[CartAgent] Missing products overall for {domain}")
                return CartAgentOutput(cart_action="none", missing_categories=[requested_category])
                
            if not approved_for_cat:
                # We have approved products, but none for this category. Fall back to best approved.
                # In a strict setting, we might request it. For now, try top approved.
                approved_for_cat = rec_workspace.approved_products
                
            best_product = approved_for_cat[0]
            
            # Add to cart
            new_item = CartItem(
                parent_asin=best_product.parent_asin,
                quantity=1,
                added_by="ai",
                domain=domain,
                category_target=requested_category,
                added_reason=f"Added highest scoring approved product for {requested_category}"
            )
            
            new_items = list(current_items)
            # Avoid duplicates
            if not any(i.parent_asin == new_item.parent_asin for i in new_items):
                new_items.append(new_item)
                
            logger.info(f"[CartAgent] Added {best_product.parent_asin} for {requested_category}")
            return CartAgentOutput(cart_action="add", cart_items=new_items)
            
        if requested_action == "remove" and requested_category:
            new_items = [i for i in current_items if i.category_target.lower() != requested_category.lower() and i.added_by != "user"]
            logger.info(f"[CartAgent] Removed items for {requested_category}")
            return CartAgentOutput(cart_action="remove", cart_items=new_items)
            
        return CartAgentOutput(cart_action="none", cart_items=current_items)
