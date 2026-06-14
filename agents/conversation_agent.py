import os
import json
import logging
from typing import List, Dict, Any
from google import genai
from google.genai import types
from agents.models import AgentExecutionContext, ConversationAgentOutput

logger = logging.getLogger(__name__)

class ConversationAgent:
    """
    Conversation Agent is the last step in the pipeline.
    It explains actions, extracts state, detects goals, and answers questions.
    """
    
    def run(self, context: AgentExecutionContext) -> ConversationAgentOutput:
        messages = context.recent_messages[-5:]
        conversation_text = "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in messages])
        
        actions_taken = "\n".join([f"- {a}" for a in context.action_history])
        if not actions_taken:
            actions_taken = "- No background actions taken."
            
        prompt = f"""
        CRITICAL OUTPUT RULE: Return ONLY a valid JSON object.
        
        You are an expert AI Shopping Consultant, Lifestyle Assistant, and Personal Shopping Advisor.
        
        Recent Conversation:
        {conversation_text}
        
        Consultation State (Context):
        {context.consultation_state.model_dump_json()}
        
        Active Domains: {context.active_domains}
        
        Background Actions Performed by the System just now:
        {actions_taken}
        
        YOUR RESPONSIBILITIES

        You are NOT responsible for:
        - Retrieval
        - Recommendations
        - Product approval
        - Cart operations
        - Cart planning
        - Domain invalidation

        You ARE responsible for:
        - Understanding user intent
        - Extracting preferences
        - Extracting goals
        - Updating consultation state
        - Providing education
        - Answering questions
        - Explaining actions performed by other agents
        - Producing concise, natural responses
        
        MULTI-DOMAIN RULE
        Users may pursue multiple goals simultaneously.
        Examples:
        - Planning a movie night
        - Buying a gaming laptop
        Do NOT assume a new goal replaces an old goal.
        Only mark a goal as abandoned when the user explicitly states it.
        Example: "Forget movie night."
        In that case:
        goal_abandoned = true
        abandoned_goal = "movie_night"
        
        ACTION SUMMARY RULE
        You may receive actions already performed by other agents.
        Examples:
        - Cart Created
        - Cart Updated
        - Recommendations Refreshed
        - Products Removed
        Your responsibility is to explain those actions naturally to the user.
        Do NOT change, re-evaluate, or override those actions.
        
        OUTPUT SCHEMA:
        Return ONLY valid JSON matching exactly this structure:
        {{
          "intent": "string",
          "interaction_type": "string",
          "user_goal": "string",
          "goal_changed": false,
          "goal_abandoned": false,
          "abandoned_goal": null,
          "active_domains": [],
          "response": "string",
          "updated_state": {{
            "goal": null,
            "event_category": null,
            "event": null,
            "budget": null,
            "preferred_brands": [],
            "avoided_brands": [],
            "must_have_features": [],
            "nice_to_have_features": [],
            "dietary_preferences": [],
            "allergens": [],
            "usage_context": null,
            "people_count": null,
            "confidence_score": 0
          }}
        }}
        """
        
        try:
            client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY_CONVERSATION"))
            response = client.models.generate_content(
                model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                )
            )
            result = json.loads(response.text)
            
            return ConversationAgentOutput(
                intent=result.get("intent", ""),
                interaction_type=result.get("interaction_type", ""),
                user_goal=result.get("user_goal", ""),
                goal_changed=result.get("goal_changed", False),
                goal_abandoned=result.get("goal_abandoned", False),
                abandoned_goal=result.get("abandoned_goal"),
                active_domains=result.get("active_domains", []),
                response=result.get("response", "I'm having trouble phrasing my response right now."),
                updated_state=result.get("updated_state", {})
            )
            
        except Exception as e:
            logger.error(f"ConversationAgent failed: {e}")
            return ConversationAgentOutput(response="I'm having a little trouble connecting right now, but I'll get back to you shortly.")
