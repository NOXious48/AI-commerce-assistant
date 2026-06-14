import os
import json
import logging
from google import genai
from google.genai import types
from agents.models import AgentExecutionContext, CartPlannerOutput

logger = logging.getLogger(__name__)

class CartPlanner:
    """
    Cart Planner generates the category targets for a given event.
    """
    
    def run(self, context: AgentExecutionContext, domain: str) -> CartPlannerOutput:
        """
        Creates category targets for the cart design.
        """
        import copy
        from agents.models import CategoryTarget

        if domain not in context.planning_workspace:
            return CartPlannerOutput()
            
        plan = context.planning_workspace[domain]
        event = plan.event
        
        if not event or event == "General Shopping":
            return CartPlannerOutput()
            
        budget = plan.assumptions.get("budget", "moderate")
        people_count = plan.assumptions.get("people_count", 1)
        strategy = plan.strategy
            
        prompt = f"""
        You are the Cart Planner for an AI Shopping Assistant.
        The user is planning for the following event/goal: "{event}".
        Strategy: {strategy}
        Budget preference: {budget}
        People count: {people_count}
        
        Determine the logical category targets for a shopping cart. 
        Keep categories generic and broad (e.g. "snacks", "drinks", "decorations", "electronics").
        You must also allocate a "budget_share" for each category (a float between 0.0 and 1.0 representing the percentage of total budget). The total budget_share must sum to 1.0.
        Provide a suggested quantity for each category slot based on the people_count and strategy.
        
        Return ONLY a valid JSON object matching this schema:
        {{
            "category_targets": [
                {{
                    "category": "string",
                    "quantity": 1,
                    "budget_share": 0.5
                }}
            ]
        }}
        """
        
        try:
            client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY_CART_PLANNER"))
            response = client.models.generate_content(
                model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                )
            )
            result = json.loads(response.text)
            
            targets = []
            for t in result.get("category_targets", []):
                targets.append(CategoryTarget(
                    category=t.get("category", ""),
                    quantity=t.get("quantity", 1),
                    budget_share=t.get("budget_share", 0.0)
                ))
            
            return CartPlannerOutput(category_targets=targets)
            
        except Exception as e:
            logger.error(f"CartPlanner failed: {e}")
            return CartPlannerOutput()
