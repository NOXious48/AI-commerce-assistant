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
    
    def run(self, context: AgentExecutionContext, domain: str, requested_action: str, requested_category: str = "", requested_product: str = "", source: str = "ai") -> CartAgentOutput:
        """
        Executes a cart operation.
        
        Args:
            requested_action: "add", "remove", "clear", "replace", "none"
            requested_category: the category being targeted (e.g. "snacks")
            requested_product: the ASIN being explicitly targeted (used mainly for direct "add"/"remove" by user or implicit intents)
            source: "user" or "ai"
        """
        if domain not in context.recommendation_workspaces:
            return CartAgentOutput(cart_action="none")
            
        rec_workspace = context.recommendation_workspaces[domain]
        cart_workspace = context.cart_workspaces.get(domain)
        
        current_items = cart_workspace.cart_items if cart_workspace else []
        
        # 1. Clear Cart
        if requested_action == "clear":
            # Keep manual additions if source is AI, otherwise full clear
            if source == "user":
                new_items = []
                cart_changes = [f"User cleared entire cart for {domain}"]
            else:
                new_items = [i for i in current_items if i.added_by == "user"]
                cart_changes = [f"Cleared all AI-added items for {domain}"]
                
            logger.info(f"[CartAgent] Cleared cart for {domain}")
            return CartAgentOutput(cart_action="clear", cart_items=new_items, cart_changes=cart_changes)
            
        # 2. Add to Cart
        if requested_action == "add":
            # If user explicitly specifies a product ASIN
            if requested_product:
                asin = requested_product
                # Find product in recommendations to get version, if it exists
                # It may not exist if user added a random product from search
                # But if it's there, grab the metadata
                version = rec_workspace.active_version if hasattr(rec_workspace, 'active_version') else 0
                
                new_item = CartItem(
                    parent_asin=asin,
                    quantity=1,
                    added_by=source,
                    domain=domain,
                    category_target=requested_category,
                    added_reason=f"Added explicitly by {source}",
                    recommendation_version=version
                )
                
                new_items = list(current_items)
                existing = next((i for i in new_items if i.parent_asin == asin), None)
                if existing:
                    existing.quantity += 1
                else:
                    new_items.append(new_item)
                    
                if source == "user" and asin not in cart_workspace.manually_added_items:
                    cart_workspace.manually_added_items.append(asin)
                    
                return CartAgentOutput(cart_action="add", cart_items=new_items, cart_changes=[f"Added product {asin} to cart"])

            # AI logic: picking a product by category
            if requested_category and source == "ai":
                # Ensure we have active_version
                active_version = rec_workspace.active_version if hasattr(rec_workspace, 'active_version') else 0
                if hasattr(rec_workspace, 'versions') and str(active_version) in rec_workspace.versions:
                    approved = rec_workspace.versions[str(active_version)].approved_products
                else:
                    approved = getattr(rec_workspace, 'approved_products', [])
                
                if not approved:
                    return CartAgentOutput(cart_action="none", missing_categories=[requested_category])
                    
                approved_for_cat = [p for p in approved if requested_category.lower() in p.category.lower() or not p.category]
                if not approved_for_cat:
                    approved_for_cat = approved
                    
                # Rigid Skip Rule check
                valid_candidates = [p for p in approved_for_cat if p.parent_asin not in cart_workspace.manually_removed_items]
                if not valid_candidates:
                    return CartAgentOutput(cart_action="none", cart_changes=[f"Skipped adding {requested_category} because all top recommendations were previously removed by user."])
                    
                best_product = valid_candidates[0]
                
                new_item = CartItem(
                    parent_asin=best_product.parent_asin,
                    quantity=1,
                    added_by="ai",
                    domain=domain,
                    category_target=requested_category,
                    added_reason=f"AI selected highest scoring approved product for {requested_category}",
                    recommendation_version=active_version
                )
                
                new_items = list(current_items)
                if not any(i.parent_asin == new_item.parent_asin for i in new_items):
                    new_items.append(new_item)
                    
                return CartAgentOutput(cart_action="add", cart_items=new_items, cart_changes=[f"Added {best_product.parent_asin} to cart for {requested_category}"])

        # 3. Remove from Cart
        if requested_action == "remove":
            new_items = list(current_items)
            changes = []
            if requested_product:
                # Remove specific product
                for i in new_items:
                    if i.parent_asin == requested_product:
                        i.quantity -= 1
                new_items = [i for i in new_items if i.quantity > 0]
                changes.append(f"Removed product {requested_product} from cart")
                
                if source == "user" and requested_product not in cart_workspace.manually_removed_items:
                    cart_workspace.manually_removed_items.append(requested_product)
            elif requested_category:
                # Remove by category
                removed = [i for i in new_items if i.category_target.lower() == requested_category.lower() and (source == "user" or i.added_by != "user")]
                new_items = [i for i in new_items if i not in removed]
                if removed:
                    changes.append(f"Removed {len(removed)} {requested_category} items from cart")
                    if source == "user":
                        for i in removed:
                            if i.parent_asin not in cart_workspace.manually_removed_items:
                                cart_workspace.manually_removed_items.append(i.parent_asin)
                                
            return CartAgentOutput(cart_action="remove", cart_items=new_items, cart_changes=changes)
            
        # 4. Replace Action (Atomic swap)
        if requested_action == "replace" and requested_category:
            # First remove old items for this category (AI added only if source is AI)
            old_items = [i for i in current_items if i.category_target.lower() == requested_category.lower() and (source == "user" or i.added_by != "user")]
            intermediate_items = [i for i in current_items if i not in old_items]
            
            # Then add new item
            active_version = rec_workspace.active_version if hasattr(rec_workspace, 'active_version') else 0
            if hasattr(rec_workspace, 'versions') and str(active_version) in rec_workspace.versions:
                approved = rec_workspace.versions[str(active_version)].approved_products
            else:
                approved = getattr(rec_workspace, 'approved_products', [])
                
            approved_for_cat = [p for p in approved if requested_category.lower() in p.category.lower() or not p.category]
            if not approved_for_cat:
                approved_for_cat = approved
                
            # Skip previously removed or currently removed ones
            removed_asins = set(cart_workspace.manually_removed_items + [i.parent_asin for i in old_items])
            valid_candidates = [p for p in approved_for_cat if p.parent_asin not in removed_asins]
            
            if not valid_candidates:
                return CartAgentOutput(cart_action="replace", cart_items=intermediate_items, cart_changes=[f"Removed {requested_category} but found no valid replacements."])
                
            best_product = valid_candidates[0]
            new_item = CartItem(
                parent_asin=best_product.parent_asin,
                quantity=1,
                added_by="ai",
                domain=domain,
                category_target=requested_category,
                added_reason=f"AI replaced {requested_category}",
                recommendation_version=active_version
            )
            intermediate_items.append(new_item)
            return CartAgentOutput(cart_action="replace", cart_items=intermediate_items, cart_changes=[f"Replaced {requested_category} with {best_product.parent_asin}"])

        return CartAgentOutput(cart_action="none", cart_items=current_items)
