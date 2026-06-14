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
        if domain not in context.recommendation_workspaces:
            return CartPlannerOutput()
            
        rec_context = context.recommendation_workspaces[domain].recommendation_context
        event = rec_context.goal
        
        if not event or event == "General Shopping":
            return CartPlannerOutput()
            
        prompt = f"""
        You are the Cart Planner for an AI Shopping Assistant.
        The user is planning for the following event/goal: "{event}".
        Budget preference: {rec_context.budget}
        People count: {rec_context.people_count}
        
        Determine the logical category targets for a shopping cart. 
        Keep categories generic and broad (e.g. "snacks", "drinks", "decorations", "electronics").
        
        Return ONLY a valid JSON object matching this schema:
        {{
            "required_categories": ["string"],
            "optional_categories": ["string"]
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
            
            return CartPlannerOutput(
                required_categories=result.get("required_categories", []),
                optional_categories=result.get("optional_categories", [])
            )
            
        except Exception as e:
            logger.error(f"CartPlanner failed: {e}")
            return CartPlannerOutput()
