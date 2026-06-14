import os
import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class CartPlanningAgent:
    def __init__(self):
        self.max_cart_items = 20
        self.max_ai_items = 10

    def _generate_category_targets(self, context: str) -> dict:
        """Use Gemini to determine category targets for the cart context."""
        try:
            client = genai.Client()
            prompt = f"Given the shopping context '{context}', determine the category targets for a shopping cart. Return ONLY a valid JSON object matching this schema: {{\n  \"required\": [\"string\"],\n  \"optional\": [\"string\"]\n}}"
            response = client.models.generate_content(
                model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                )
            )
            return json.loads(response.text)
        except Exception as e:
            logger.warning(f"Failed to generate category targets: {e}")
            return {"required": [], "optional": []}

    def _compute_context_hash(self, state: dict) -> str:
        relevant = {
            "goal": state.get("goal"),
            "event": state.get("event"),
            "budget": state.get("budget"),
            "dietary_preferences": sorted(state.get("dietary_preferences", [])),
            "preferred_brands": sorted(state.get("preferred_brands", [])),
        }
        return hashlib.md5(json.dumps(relevant, sort_keys=True).encode()).hexdigest()

    def _parse_budget(self, budget_val: Any) -> float:
        if not budget_val:
            return 0.0
        if isinstance(budget_val, (int, float)):
            return float(budget_val)
        s = str(budget_val).lower().replace('$', '').replace(',', '')
        for w in s.split():
            try:
                return float(w)
            except ValueError:
                pass
        return 0.0

    def plan_cart(
        self,
        action: str,
        current_cart: list,
        cart_workspace: dict,
        consultation_state: dict,
        approved_products: list,
        user_memory: dict,
        intent: str = "general_conversation"
    ) -> dict:
        """
        Executes cart planning logic.
        Returns:
            {
                "new_cart": list,
                "new_workspace": dict,
                "system_message": dict | None
            }
        """
        now = datetime.now(timezone.utc).isoformat()
        
        # Determine context
        context = consultation_state.get("event") or consultation_state.get("goal") or "General Shopping"
        context_hash = self._compute_context_hash(consultation_state)
        
        # Base workspace updates
        new_workspace = dict(cart_workspace)
        if not new_workspace.get("cart_context_hash"):
            new_workspace["version"] = 0
            new_workspace["previous_version"] = 0
            
        manually_removed = set(new_workspace.get("manually_removed_asins", []))
        manually_added = set(new_workspace.get("manually_added_asins", []))
        
        system_message = None

        if action == "clear_cart":
            # Keep user items, clear AI items
            new_cart = [item for item in current_cart if item.get("added_by") == "user"]
            
            new_workspace["previous_version"] = new_workspace["version"]
            new_workspace["version"] += 1
            new_workspace["status"] = "archived"
            new_workspace["last_updated"] = now
            new_workspace["update_reason"] = "User requested to clear AI cart items."
            
            system_message = {
                "role": "system",
                "type": "cart_update",
                "event_type": "cart_cleared",
                "message": "Cleared AI-added items from the cart.",
                "timestamp": now,
                "cart_version": new_workspace["version"]
            }
            return {"new_cart": new_cart, "new_workspace": new_workspace, "system_message": system_message}

        if action in ["create_cart", "update_cart", "remove_items"]:
            # Quick Planning Intents
            quick_planning_intents = [
                "movie_night", "game_night", "birthday_party", "housewarming", 
                "road_trip", "camping_trip", "family_dinner", "holiday_event", 
                "bbq", "picnic", "study_session"
            ]
            
            is_quick_planning = intent in quick_planning_intents
            
            # We must have enough confidence to build, UNLESS it's a Quick Planning intent or we're just removing items
            if action != "remove_items" and not is_quick_planning and consultation_state.get("confidence_score", 0) < 70:
                # Not enough confidence, do nothing
                return {"new_cart": current_cart, "new_workspace": cart_workspace, "system_message": None}
                
            # If context shifted, generate new targets
            if new_workspace.get("cart_context_hash") != context_hash or not new_workspace.get("category_targets"):
                new_workspace["category_targets"] = self._generate_category_targets(context)
                new_workspace["cart_context"] = context
                new_workspace["cart_context_hash"] = context_hash
                new_workspace["status"] = "building"
            
            # Identify existing items
            user_items = [item for item in current_cart if item.get("added_by") == "user"]
            ai_items = [item for item in current_cart if item.get("added_by") == "ai"]
            
            # Select products based on category targets
            selected_ai_items = []
            budget_limit = self._parse_budget(consultation_state.get("budget"))
            
            # If the user explicitly requested to remove items based on constraints (like price),
            # we apply the individual item budget constraint to user_items as well.
            if action in ["remove_items", "update_cart"] and budget_limit > 0:
                user_items = [u for u in user_items if u.get("price", 0) <= budget_limit]
                
            current_total = sum(item.get("price", 0) * item.get("quantity", 1) for item in user_items)
            
            # Group approved products by category loosely
            # Simple heuristic: we just pick top alignment score products, ensuring variety.
            # In a real system, we'd map required/optional to main_category.
            
            category_counts = {}
            for product in approved_products:
                asin = product.get("parent_asin")
                price = product.get("price", 0)
                category = product.get("main_category", "other")
                
                # Check constraints
                if asin in manually_removed:
                    continue # Respect user manual removal
                    
                # Skip if already in user items
                if any(u.get("product_id") == asin for u in user_items):
                    continue
                    
                # Item-level budget limit (if user requested removal/update constraints)
                if action in ["remove_items", "update_cart"] and budget_limit > 0 and price > budget_limit:
                    continue
                    
                # Check cart limits
                if len(selected_ai_items) >= self.max_ai_items:
                    break
                if len(selected_ai_items) + len(user_items) >= self.max_cart_items:
                    break
                    
                # Budget check
                if budget_limit > 0 and (current_total + price > budget_limit):
                    continue # Skip to avoid exceeding budget
                
                # Ensure we don't pick too many from one category (max 2 per category)
                if category_counts.get(category, 0) >= 2:
                    continue
                    
                # Add to cart
                selected_ai_items.append({
                    "product_id": asin,
                    "title": product.get("title", ""),
                    "price": price,
                    "quantity": 1,
                    "image": product.get("image_url", ""),
                    "added_at": now,
                    "source_context": context,
                    "added_by": "ai",
                    "added_reason": f"Recommended for {context}"
                })
                current_total += price
                category_counts[category] = category_counts.get(category, 0) + 1
            
            new_cart = user_items + selected_ai_items
            
            # Determine event message
            if action == "create_cart":
                msg = f"Created {context} cart with {len(selected_ai_items)} recommended products."
                if is_quick_planning:
                    msg = f"Created starter {context} cart for 4 people with a moderate budget using popular products."
                evt = "cart_created"
            elif action == "update_cart":
                msg = f"Updated cart for {context}. Added {len(selected_ai_items)} items."
                evt = "cart_updated"
            else:
                msg = f"Removed items violating constraints for {context}."
                evt = "cart_updated"
            
            new_workspace["previous_version"] = new_workspace["version"]
            new_workspace["version"] += 1
            new_workspace["status"] = "active"
            new_workspace["created_by_ai"] = True
            new_workspace["last_updated"] = now
            new_workspace["update_reason"] = msg
            new_workspace["consultation_snapshot"] = dict(consultation_state)
            
            system_message = {
                "role": "system",
                "type": "cart_update",
                "event_type": evt,
                "message": msg,
                "timestamp": now,
                "cart_version": new_workspace["version"]
            }
            
            return {"new_cart": new_cart, "new_workspace": new_workspace, "system_message": system_message}

        # none or unhandled
        return {"new_cart": current_cart, "new_workspace": cart_workspace, "system_message": None}

cart_planning_agent = CartPlanningAgent()
