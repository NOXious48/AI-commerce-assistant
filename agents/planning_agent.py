import os
import json
import logging
from google import genai
from google.genai import types
from agents.models import AgentExecutionContext, PlanningAgentOutput

logger = logging.getLogger(__name__)

class PlanningAgent:
    """
    Planning Agent analyzes the conversation to extract the primary goal/event
    and identify what categories might be needed.
    """
    
    def run(self, context: AgentExecutionContext) -> PlanningAgentOutput:
        """
        Extracts the event and category requirements.
        """
        # If we have recent messages, we can analyze the user's intent.
        messages = context.recent_messages[-5:]  # Look at recent context
        conversation_text = "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in messages])
        
        # We also pass the consultation state
        state_dump = context.consultation_state.model_dump_json()
        
        import uuid
        from datetime import datetime, timezone
        from agents.models import ShoppingPlan

        prompt = f"""
        You are the Planning Agent for an AI Shopping Assistant.
        Analyze the conversation and the current consultation state to determine the user's shopping goal.
        
        Current Consultation State:
        {state_dump}
        
        Recent Conversation:
        {conversation_text}
        
        Determine the primary shopping event or goal (e.g., "Movie Night", "Gaming Setup", "Weekly Groceries").
        If no clear event is stated, return "General Shopping".
        Determine the overarching shopping strategy.
        Determine any assumptions you are making (e.g., "people_count": 4, "budget": "moderate").
        
        Return ONLY a valid JSON object matching this schema:
        {{
            "event": "string",
            "strategy": "string",
            "assumptions": {{}}
        }}
        """
        
        now_iso = datetime.now(timezone.utc).isoformat()
        
        try:
            client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY_PLANNER"))
            response = client.models.generate_content(
                model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                )
            )
            result = json.loads(response.text)
            
            event = result.get("event", "General Shopping")
            if not event.strip():
                event = "General Shopping"
                
            plan = ShoppingPlan(
                plan_id=str(uuid.uuid4()),
                version=1,
                domain=event.lower().replace(" ", "_"),
                status="active",
                event=event,
                assumptions=result.get("assumptions", {}),
                strategy=result.get("strategy", ""),
                last_updated=now_iso
            )
                
            return PlanningAgentOutput(shopping_plan=plan)
            
        except Exception as e:
            logger.error(f"PlanningAgent failed: {e}")
            plan = ShoppingPlan(
                plan_id=str(uuid.uuid4()),
                event="General Shopping",
                last_updated=now_iso
            )
            return PlanningAgentOutput(shopping_plan=plan)
