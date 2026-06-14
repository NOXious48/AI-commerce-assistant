import logging
import json
import os
from typing import Dict, Any, Tuple
from google import genai
from google.genai import types

from agents.models import AgentExecutionContext, DomainRecommendationWorkspace, DomainCartWorkspace
from agents.planning_agent import PlanningAgent
from agents.cart_planner import CartPlanner
from agents.recommendation_agent import RecommendationAgent
from agents.review_agent import ReviewAgent
from agents.cart_agent import CartAgent
from agents.conversation_agent import ConversationAgent

logger = logging.getLogger(__name__)

class OrchestratorAgent:
    """
    Central control flow for the multi-agent system.
    Parses intent, manages domain switching, and routes to appropriate sub-agents.
    """
    def __init__(self, retrieval_service, workspace_manager):
        self.retrieval_service = retrieval_service
        self.workspace_manager = workspace_manager
        
        self.planning_agent = PlanningAgent()
        self.cart_planner = CartPlanner()
        self.recommendation_agent = RecommendationAgent(retrieval_service)
        self.review_agent = ReviewAgent(retrieval_service)
        self.cart_agent = CartAgent()
        self.conversation_agent = ConversationAgent()
        
    def process_message(self, context: AgentExecutionContext, user_message: str) -> str:
        """
        Main entry point for processing a user turn.
        """
        context.action_history.clear()
        
        # 1. Parse Intent & Domain
        intent_info = self._parse_intent(user_message, context)
        domain = intent_info.get("domain", "general")
        action = intent_info.get("action", "converse")
        target_category = intent_info.get("target_category", "")
        
        # 2. Domain Initialization & Invalidation
        if intent_info.get("abandon_domain"):
            abandoned = intent_info["abandon_domain"]
            self.workspace_manager.invalidate_domain(context, abandoned)
            if domain == abandoned:
                domain = "general"
                
        if domain not in context.active_domains:
            context.active_domains.append(domain)
            
        if domain not in context.recommendation_workspaces:
            context.recommendation_workspaces[domain] = DomainRecommendationWorkspace()
            context.recommendation_workspaces[domain].recommendation_context.goal = domain
            
        if domain not in context.cart_workspaces:
            context.cart_workspaces[domain] = DomainCartWorkspace()

        # 3. Plan / Cart Plan
        if action in ["plan_event", "create_cart"]:
            plan_out = self.planning_agent.run(context)
            context.recommendation_workspaces[domain].recommendation_context.goal = plan_out.event
            context.action_history.append(f"Identified goal as {plan_out.event}")
            
            cart_plan = self.cart_planner.run(context, domain)
            target_categories = cart_plan.required_categories
            context.action_history.append(f"Planned cart categories: {target_categories}")
            
            # Retrieve for the initial categories
            self._run_recommendation_pipeline(context, domain, target_categories)
            
            # Add to cart
            for cat in target_categories:
                cart_out = self.cart_agent.run(context, domain, requested_action="add", requested_category=cat)
                if cart_out.cart_action == "add":
                    context.cart_workspaces[domain].cart_items = cart_out.cart_items
            context.action_history.append("Created initial cart with approved products.")
            
        # 4. Standard Cart Operations
        elif action in ["add_to_cart", "remove_from_cart", "clear_cart"]:
            cart_action_map = {"add_to_cart": "add", "remove_from_cart": "remove", "clear_cart": "clear"}
            req_action = cart_action_map[action]
            
            cart_out = self.cart_agent.run(context, domain, requested_action=req_action, requested_category=target_category)
            
            # Orchestrator Loop: Handle Missing Categories
            if req_action == "add" and cart_out.missing_categories:
                context.action_history.append(f"Needed to find {cart_out.missing_categories} first.")
                self._run_recommendation_pipeline(context, domain, cart_out.missing_categories)
                
                # Retry Cart Agent
                cart_out = self.cart_agent.run(context, domain, requested_action="add", requested_category=target_category)
            
            if cart_out.cart_action != "none":
                context.cart_workspaces[domain].cart_items = cart_out.cart_items
                context.action_history.append(f"Updated cart: {req_action} {target_category}")

        # 4.5 Recommend Products
        elif action == "recommend":
            if target_category:
                context.action_history.append(f"Retrieving recommendations for {target_category}")
                self._run_recommendation_pipeline(context, domain, [target_category])
            else:
                context.action_history.append("Retrieving general recommendations.")
                # Use domain as a fallback target
                fallback = domain.replace('_', ' ') if domain != "general" else "products"
                self._run_recommendation_pipeline(context, domain, [fallback])

        # 5. Conversation Generation
        conversation_out = self.conversation_agent.run(context)
        response_text = conversation_out.response
        
        # Merge updated state
        for key, value in conversation_out.updated_state.items():
            if value and hasattr(context.consultation_state, key):
                setattr(context.consultation_state, key, value)
                
        if conversation_out.goal_abandoned and conversation_out.abandoned_goal:
            self.workspace_manager.invalidate_domain(context, conversation_out.abandoned_goal)
        
        # Persist everything
        self.workspace_manager.persist_context(context)
        
        return response_text

    def _run_recommendation_pipeline(self, context: AgentExecutionContext, domain: str, target_categories: list):
        """Runs Recommendation -> Review -> Workspace flow."""
        rec_out = self.recommendation_agent.run(context, domain, target_categories)
        if rec_out.candidate_products:
            rev_out = self.review_agent.run(context, domain, rec_out.candidate_products)
            
            # Update workspace
            ws = context.recommendation_workspaces[domain]
            ws.candidate_products = rec_out.candidate_products
            
            # Merge approved, avoiding duplicates
            existing_asins = {p.parent_asin for p in ws.approved_products}
            for p in rev_out.approved_products:
                if p.parent_asin not in existing_asins:
                    ws.approved_products.append(p)
                    
            ws.rejected_products.extend(rev_out.rejected_products)
            ws.version += 1
            context.action_history.append(f"Retrieved and approved {len(rev_out.approved_products)} new products.")

    def _parse_intent(self, message: str, context: AgentExecutionContext) -> dict:
        """
        Uses an LLM to parse the exact required action, domain, and target category.
        """
        prompt = f"""
        You are the Intent Router for an AI Shopping Assistant.
        User message: "{message}"
        Active domains: {context.active_domains}
        
        Determine:
        1. Action: [converse, plan_event, add_to_cart, remove_from_cart, clear_cart, recommend]
        2. Domain: The specific goal/event (e.g. "movie_night", "gaming_laptop"). Use an existing one if it matches, or create a new short underscore_separated name.
        3. Target Category: If adding/removing, what is the item/category? (e.g. "biscuits", "monitor")
        4. Abandon Domain: If the user explicitly wants to forget/cancel a goal, list it here.
        
        Return JSON matching:
        {{
            "action": "string",
            "domain": "string",
            "target_category": "string",
            "abandon_domain": "string"
        }}
        """
        try:
            client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY_ORCHESTRATOR"))
            response = client.models.generate_content(
                model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Intent parsing failed: {e}")
            return {"action": "converse", "domain": "general"}
