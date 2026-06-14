import logging
import json
import os
from typing import Dict, Any, Tuple, Optional, List
from google import genai
from google.genai import types

from agents.models import AgentExecutionContext, DomainRecommendationWorkspace, DomainCartWorkspace, ActionHistoryItem
from agents.planning_agent import PlanningAgent
from agents.cart_planner import CartPlanner
from agents.recommendation_agent import RecommendationAgent
from agents.review_agent import ReviewAgent
from agents.cart_agent import CartAgent
from agents.conversation_agent import ConversationAgent
from agents.action_context_builder import ActionContextBuilder
from services.constraint_resolver import ConstraintResolver

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
        self.action_context_builder = ActionContextBuilder(retrieval_service)
        self.constraint_resolver = ConstraintResolver()
        
    def process_message(self, context: AgentExecutionContext, user_message: str) -> str:
        """Main entry point for processing a user turn."""
        context.action_history.clear()
        
        # Track recently viewed via shopping_profile
        if context.current_page_context and context.current_page_context.get("page_type") == "product":
            asin = context.current_page_context.get("product_id")
            if asin:
                if asin in context.shopping_profile.recently_viewed_products:
                    context.shopping_profile.recently_viewed_products.remove(asin)
                context.shopping_profile.recently_viewed_products.insert(0, asin)
                if len(context.shopping_profile.recently_viewed_products) > 20:
                    context.shopping_profile.recently_viewed_products = context.shopping_profile.recently_viewed_products[:20]
        
        # FAST PATH: Check for obvious intents that don't need LLM parsing
        fast_action = self._fast_intent_check(user_message, context)
        if fast_action:
            intent_info = fast_action
        else:
            # 1. Parse Intent & Domain via Gemini
            intent_info = self._parse_intent(user_message, context)
        
        domain = intent_info.get("domain", "general_shopping")
        action = intent_info.get("action", "converse")
        target_category = intent_info.get("target_category", "")
        target_product_asin = intent_info.get("target_product_asin", "")
        
        # 2. Domain Initialization & Invalidation
        if intent_info.get("abandon_domain"):
            abandoned = intent_info["abandon_domain"]
            self.workspace_manager.invalidate_domain(context, abandoned)
            if domain == abandoned:
                domain = "general_shopping"
        
        # Handle topic switch — remove old domain from shelf when user pivots
        replace_domain = intent_info.get("replace_active_domain", "")
        if replace_domain and replace_domain in context.active_domains and replace_domain != domain:
            context.active_domains.remove(replace_domain)
                
        if domain not in context.active_domains:
            context.active_domains.append(domain)
            
        if domain not in context.recommendation_workspaces:
            workspace = DomainRecommendationWorkspace()
            from agents.models import RecommendationVersion
            workspace.versions["1"] = RecommendationVersion(version=1)
            workspace.versions["1"].recommendation_context.goal = domain.replace('_', ' ')
            context.recommendation_workspaces[domain] = workspace
            
        if domain not in context.cart_workspaces:
            context.cart_workspaces[domain] = DomainCartWorkspace()

        # 3. Priority Routing
        from datetime import datetime, timezone
        def _add_hist(act: str):
            context.action_history.append(ActionHistoryItem(
                timestamp=datetime.now(timezone.utc).isoformat(),
                agent="Orchestrator",
                action=act,
                domain=domain
            ))
        
        # === ACTION: Product Info Lookup ===
        if action == "product_info":
            product_details = self._lookup_product_info(context, target_product_asin, target_category, user_message)
            if product_details:
                _add_hist(f"Retrieved product details for: {product_details.get('title', target_product_asin)}")
            else:
                _add_hist("Could not find the requested product details.")
        
        # === ACTION: Cart Operations ===
        elif action in ["clear_cart", "remove_from_cart", "add_to_cart"]:
            cart_action_map = {"add_to_cart": "add", "remove_from_cart": "remove", "clear_cart": "clear"}
            req_action = cart_action_map[action]
            
            req_product = ""
            req_cat = ""
            
            if target_product_asin:
                req_product = target_product_asin
            elif target_category:
                if target_category.isalnum() and len(target_category) == 10:
                    req_product = target_category
                else:
                    # It's a characteristic/category — find matching cart item for removal
                    if req_action == "remove":
                        matched_asin = self._find_cart_item_by_description(context, domain, target_category)
                        if matched_asin:
                            req_product = matched_asin
                            _add_hist(f"Identified cart item matching '{target_category}': {matched_asin}")
                        else:
                            req_cat = target_category
                    else:
                        req_cat = target_category
            
            cart_out = self.cart_agent.run(context, domain, requested_action=req_action, requested_category=req_cat, requested_product=req_product, source="user")
            
            # Handle Missing Categories — retrieve first if needed
            if req_action == "add" and cart_out.missing_categories:
                _add_hist(f"Needed to find {cart_out.missing_categories} first.")
                self._run_recommendation_pipeline(context, domain, cart_out.missing_categories)
                cart_out = self.cart_agent.run(context, domain, requested_action="add", requested_category=req_cat, source="ai")
            
            if cart_out.cart_action != "none":
                context.cart_workspaces[domain].cart_items = cart_out.cart_items
                if cart_out.cart_changes:
                    for ch in cart_out.cart_changes:
                        _add_hist(ch)
                else:
                    _add_hist(f"Updated cart: {req_action} {target_category}")

        # === ACTION: Recommend ===
        elif action == "recommend":
            ws = context.recommendation_workspaces[domain]
            ver_str = str(ws.active_version)
            if ver_str in ws.versions:
                if not ws.versions[ver_str].recommendation_context.goal:
                    ws.versions[ver_str].recommendation_context.goal = domain.replace('_', ' ')
            
            if target_category:
                _add_hist(f"Retrieving recommendations for {target_category}")
                self._run_recommendation_pipeline(context, domain, [target_category])
            else:
                fallback = domain.replace('_', ' ') if domain != "general_shopping" else "products"
                _add_hist(f"Retrieving recommendations for {fallback}")
                self._run_recommendation_pipeline(context, domain, [fallback])
            
            # Auto-add top products to cart if we have approved products and cart is empty
            cart_ws = context.cart_workspaces.get(domain)
            if cart_ws and not cart_ws.cart_items:
                ws = context.recommendation_workspaces[domain]
                ver_str = str(ws.active_version)
                if ver_str in ws.versions:
                    approved = ws.versions[ver_str].approved_products
                    if approved:
                        # Add top 3-5 products to cart automatically
                        for p in approved[:5]:
                            cart_out = self.cart_agent.run(context, domain, requested_action="add", requested_product=p.parent_asin, source="ai")
                            if cart_out.cart_action == "add":
                                context.cart_workspaces[domain].cart_items = cart_out.cart_items
                        _add_hist(f"Added top {min(5, len(approved))} recommended products to cart.")
                
        # === ACTION: Plan Event / Create Cart ===
        elif action in ["plan_event", "create_cart"]:
            plan_out = self.planning_agent.run(context)
            context.planning_workspace[domain] = plan_out.shopping_plan
            
            ws = context.recommendation_workspaces[domain]
            ver_str = str(ws.active_version)
            if ver_str in ws.versions:
                ws.versions[ver_str].recommendation_context.goal = plan_out.shopping_plan.event
            
            _add_hist(f"Identified goal as {plan_out.shopping_plan.event}")
            
            cart_plan = self.cart_planner.run(context, domain)
            target_categories = [t.category for t in getattr(cart_plan, 'category_targets', [])]
            _add_hist(f"Planned cart categories: {target_categories}")
            
            # Build a richer search query from the conversation state
            # Include user preferences gathered during consultation
            state = context.consultation_state
            enrichment_parts = []
            if state.dietary_preferences:
                enrichment_parts.append(" ".join(state.dietary_preferences))
            if state.favorite_brands:
                enrichment_parts.append(" ".join(state.favorite_brands))
            if state.budget_preference:
                enrichment_parts.append(state.budget_preference)
            
            # Use each category + conversation context for targeted retrieval
            for cat in target_categories:
                search_terms = [plan_out.shopping_plan.event, cat] + enrichment_parts
                self._run_recommendation_pipeline(context, domain, search_terms)
            
            # If no categories were planned, use the event itself
            if not target_categories:
                self._run_recommendation_pipeline(context, domain, [plan_out.shopping_plan.event] + enrichment_parts)
            
            # Merge all approved products from all versions into active version for cart picking
            ws = context.recommendation_workspaces[domain]
            all_approved = []
            for ver_id, version in ws.versions.items():
                for p in version.approved_products:
                    if p not in all_approved:
                        all_approved.append(p)
            active_ver_str = str(ws.active_version)
            if active_ver_str in ws.versions:
                ws.versions[active_ver_str].approved_products = all_approved
            
            # Add best products to cart per category
            for cat in target_categories:
                cart_out = self.cart_agent.run(context, domain, requested_action="add", requested_category=cat, source="ai")
                if cart_out.cart_action == "add":
                    context.cart_workspaces[domain].cart_items = cart_out.cart_items
                    if cart_out.cart_changes:
                        for ch in cart_out.cart_changes:
                            _add_hist(ch)
            _add_hist("Created initial cart with approved products.")

        # === ACTION: Compare Product ===
        elif action == "compare_product":
            asin_to_compare = target_product_asin
            if not asin_to_compare:
                if target_category and len(target_category) == 10 and target_category.isalnum():
                    asin_to_compare = target_category
                elif context.current_page_context and context.current_page_context.get("page_type") == "product":
                    asin_to_compare = context.current_page_context.get("product_id")
                
            if asin_to_compare:
                ws = context.recommendation_workspaces[domain]
                ver_str = str(ws.active_version)
                if ver_str in ws.versions:
                    comp_ws = ws.versions[ver_str].comparison_workspace
                    if asin_to_compare not in comp_ws.selected_products:
                        comp_ws.selected_products.append(asin_to_compare)
                        _add_hist(f"Added product to comparison workspace.")

        # 5. Conversation Generation
        action_context = self.action_context_builder.build_context(context)
        conversation_out = self.conversation_agent.run(context, action_context)
        response_text = conversation_out.response
        
        # Merge updated state
        for key, value in conversation_out.updated_state.items():
            if value and hasattr(context.consultation_state, key):
                setattr(context.consultation_state, key, value)
                
        if conversation_out.goal_abandoned and conversation_out.abandoned_goal:
            self.workspace_manager.invalidate_domain(context, conversation_out.abandoned_goal)
        
        # POST-PROCESSING: Auto-trigger plan_event if user provided preferences
        # but no retrieval happened yet (intent parser said "converse" but user gave enough info)
        if action == "converse" and domain != "general_shopping":
            # Check if this domain has NO products yet
            ws = context.recommendation_workspaces.get(domain)
            has_products = False
            if ws:
                ver_str = str(ws.active_version)
                if ver_str in ws.versions and ws.versions[ver_str].approved_products:
                    has_products = True
            
            # Check if the consultation state now has meaningful preferences
            state = context.consultation_state
            has_preferences = bool(state.budget_preference or state.dietary_preferences or state.favorite_brands)
            
            if not has_products and has_preferences:
                # User gave preferences but we haven't retrieved yet — trigger the pipeline now
                _add_hist("User provided preferences — triggering recommendation pipeline")
                
                # Run the full plan_event flow
                plan_out = self.planning_agent.run(context)
                context.planning_workspace[domain] = plan_out.shopping_plan
                
                ws = context.recommendation_workspaces[domain]
                ver_str = str(ws.active_version)
                if ver_str in ws.versions:
                    ws.versions[ver_str].recommendation_context.goal = plan_out.shopping_plan.event
                
                cart_plan = self.cart_planner.run(context, domain)
                target_categories = [t.category for t in getattr(cart_plan, 'category_targets', [])]
                
                # Enrich with user preferences
                enrichment_parts = []
                if state.dietary_preferences:
                    enrichment_parts.append(" ".join(state.dietary_preferences))
                if state.budget_preference:
                    enrichment_parts.append(state.budget_preference)
                
                for cat in target_categories:
                    search_terms = [plan_out.shopping_plan.event, cat] + enrichment_parts
                    self._run_recommendation_pipeline(context, domain, search_terms)
                
                if not target_categories:
                    self._run_recommendation_pipeline(context, domain, [plan_out.shopping_plan.event] + enrichment_parts)
                
                # Add to cart — use each retrieval's version
                ws = context.recommendation_workspaces[domain]
                # Each category retrieval created a new version, so we need to iterate
                # Get all approved products across all versions for this domain
                all_approved = []
                for ver_id, version in ws.versions.items():
                    for p in version.approved_products:
                        if p not in all_approved:
                            all_approved.append(p)
                
                # Temporarily set all approved into the active version for CartAgent to pick from
                active_ver_str = str(ws.active_version)
                if active_ver_str in ws.versions:
                    ws.versions[active_ver_str].approved_products = all_approved
                
                for cat in target_categories:
                    cart_out = self.cart_agent.run(context, domain, requested_action="add", requested_category=cat, source="ai")
                    if cart_out.cart_action == "add":
                        context.cart_workspaces[domain].cart_items = cart_out.cart_items
                
                _add_hist(f"Built cart with {len(context.cart_workspaces[domain].cart_items)} items")
                
                # Re-persist since we modified workspaces
                self.workspace_manager.persist_context(context)
        
        # Enforce history caps
        if len(context.action_history) > 100:
            context.action_history = context.action_history[-100:]
        if len(context.execution_audit_trail) > 100:
            context.execution_audit_trail = context.execution_audit_trail[-100:]
            
        # Persist everything
        self.workspace_manager.persist_context(context)
        
        return response_text

    # ------------------------------------------------------------------
    # Fast Intent Check (skip Gemini for obvious patterns)
    # ------------------------------------------------------------------

    def _fast_intent_check(self, message: str, context: AgentExecutionContext) -> Optional[dict]:
        """
        Regex/keyword-based fast path for obvious intents.
        Returns intent dict if matched, None if LLM parsing is needed.
        Saves ~800ms per message for simple cases.
        """
        msg_lower = message.strip().lower()
        last_domain = context.active_domains[-1] if context.active_domains else "general_shopping"
        
        # Greetings / small talk → converse
        greetings = ["hi", "hello", "hey", "good morning", "good evening", "thanks", "thank you", "ok", "okay"]
        if msg_lower in greetings or len(msg_lower) < 4:
            return {"action": "converse", "domain": last_domain, "target_category": "", "target_product_asin": ""}
        
        # Affirmative after a question → plan_event (user is answering)
        affirmatives = ["yes", "yeah", "yep", "sure", "go ahead", "build it", "proceed", "do it", "sounds good", "let's do it", "build my cart", "create my cart"]
        if msg_lower in affirmatives:
            return {"action": "plan_event", "domain": last_domain, "target_category": "", "target_product_asin": ""}
        
        # Clear cart
        if "clear" in msg_lower and "cart" in msg_lower:
            return {"action": "clear_cart", "domain": last_domain, "target_category": "", "target_product_asin": ""}
        
        # Empty cart
        if "empty" in msg_lower and "cart" in msg_lower:
            return {"action": "clear_cart", "domain": last_domain, "target_category": "", "target_product_asin": ""}
        
        return None

    # ------------------------------------------------------------------
    # Product Info Lookup
    # ------------------------------------------------------------------

    def _lookup_product_info(self, context: AgentExecutionContext, asin: str, description: str, user_message: str) -> Optional[Dict[str, Any]]:
        """
        Looks up product metadata by ASIN or by searching for a match.
        Injects the product info + raw reviews into the action context so the ConversationAgent can use it.
        """
        found_asin = None
        
        # If we have a direct ASIN, use it
        if asin:
            found_asin = asin
        else:
            # Try to find the product from current recommendations
            for domain, ws in context.recommendation_workspaces.items():
                ver_str = str(ws.active_version)
                if ver_str in ws.versions:
                    for p in ws.versions[ver_str].approved_products:
                        details = self.retrieval_service.get_product_details_index(p.parent_asin)
                        if details:
                            title = details.get("metadata", {}).get("title", "").lower()
                            if description and (description.lower() in title or any(word in title for word in description.lower().split() if len(word) > 3)):
                                found_asin = p.parent_asin
                                break
                if found_asin:
                    break
            
            # Fallback: semantic search
            if not found_asin and description:
                results = self.retrieval_service.search(description, top_k=1)
                if results:
                    found_asin = results[0].get("parent_asin", "")
        
        if not found_asin:
            return None
        
        details = self.retrieval_service.get_product_details_index(found_asin)
        if not details:
            return None
        
        # Also fetch raw reviews (O(1) dict lookup)
        raw_reviews = self.retrieval_service.get_product_reviews(found_asin, limit=8)
        
        # Inject into context for ConversationAgent
        context.current_page_context["product_info_lookup"] = {
            **details,
            "raw_reviews": raw_reviews
        }
        
        return details.get("metadata", {})

    # ------------------------------------------------------------------
    # Find Cart Item by Description
    # ------------------------------------------------------------------

    def _find_cart_item_by_description(self, context: AgentExecutionContext, domain: str, description: str) -> Optional[str]:
        """
        Finds a cart item matching a user description (e.g., 'the expensive one', 'the dog biscuits').
        Returns the parent_asin if found.
        """
        cart_ws = context.cart_workspaces.get(domain)
        if not cart_ws or not cart_ws.cart_items:
            # Check all domains
            for d, cws in context.cart_workspaces.items():
                if cws.cart_items:
                    cart_ws = cws
                    break
        
        if not cart_ws or not cart_ws.cart_items:
            return None
        
        desc_lower = description.lower()
        best_match = None
        best_score = 0
        
        for item in cart_ws.cart_items:
            details = self.retrieval_service.get_product_details_index(item.parent_asin)
            if not details:
                continue
            
            meta = details.get("metadata", {})
            title = (meta.get("title", "") or "").lower()
            category = (meta.get("category", "") or "").lower()
            brand = (meta.get("brand", "") or "").lower()
            
            # Simple keyword matching
            score = 0
            for word in desc_lower.split():
                if len(word) > 2:
                    if word in title:
                        score += 3
                    if word in category:
                        score += 2
                    if word in brand:
                        score += 2
            
            # Check for price-based descriptions
            price = meta.get("price", 0)
            if "expensive" in desc_lower or "costly" in desc_lower:
                score += price * 0.01  # Higher price = better match for "expensive"
            elif "cheap" in desc_lower or "affordable" in desc_lower:
                score += (100 - price) * 0.01  # Lower price = better match
            
            if score > best_score:
                best_score = score
                best_match = item.parent_asin
        
        return best_match if best_score > 0 else None

    # ------------------------------------------------------------------
    # Recommendation Pipeline
    # ------------------------------------------------------------------

    def _run_recommendation_pipeline(self, context: AgentExecutionContext, domain: str, target_categories: list):
        """Runs Recommendation -> Review -> Workspace flow."""
        rec_out = self.recommendation_agent.run(context, domain, target_categories)
        
        from datetime import datetime, timezone
        from agents.models import AuditTrailItem, RecommendationVersion
        import uuid
        
        if getattr(rec_out, 'clarification_required', False):
            context.action_history.append(ActionHistoryItem(
                timestamp=datetime.now(timezone.utc).isoformat(),
                agent="RecommendationAgent",
                action="Requires clarification for missing constraints.",
                domain=domain
            ))
            return

        if rec_out.candidate_pool:
            # Resolve constraints from consultation state + user memory
            constraint_output = self.constraint_resolver.resolve(
                context.consultation_state,
                context.user_memory,
                " ".join(target_categories)
            )
            constraint_snapshot = constraint_output.model_dump()
            
            # Store constraints in the active version so ReviewAgent can use them
            ws = context.recommendation_workspaces[domain]
            ver_str = str(ws.active_version)
            if ver_str in ws.versions:
                ws.versions[ver_str].constraint_snapshot = constraint_snapshot
            
            rev_out = self.review_agent.run(context, domain, candidates=rec_out.candidate_pool)
            
            ws = context.recommendation_workspaces[domain]
            new_version_num = ws.active_version + 1 if ws.versions else 1
            ws.active_version = new_version_num
            
            # Inherit context
            prev_context = None
            if str(new_version_num - 1) in ws.versions:
                prev_context = ws.versions[str(new_version_num - 1)].recommendation_context
                ws.versions[str(new_version_num - 1)].status = "stale"
                
            now_iso = datetime.now(timezone.utc).isoformat()
            
            for p in rev_out.approved_products:
                p.retrieval_query = rec_out.retrieval_query
            
            new_version = RecommendationVersion(
                workspace_id=str(uuid.uuid4()),
                version=new_version_num,
                domain=domain,
                status="active",
                created_at=now_iso,
                last_updated=now_iso,
                retrieval_query=rec_out.retrieval_query,
                retrieval_timestamp=now_iso,
                retrieval_source=rec_out.source,
                candidate_pool=rec_out.candidate_pool,
                approved_products=rev_out.approved_products,
                rejected_products=rev_out.rejected_products
            )
            if prev_context:
                new_version.recommendation_context = prev_context
                
            ws.versions[str(new_version_num)] = new_version
            
            # Execution Audit
            retrieved_count = len(rec_out.candidate_pool)
            approved_count = len(rev_out.approved_products)
            rejected_count = len(rev_out.rejected_products)
            approval_rate = int((approved_count / retrieved_count * 100)) if retrieved_count > 0 else 0
            
            context.execution_audit_trail.append(AuditTrailItem(
                timestamp=now_iso,
                agent="RecommendationAgent",
                domain=domain,
                workspace_version=new_version_num,
                source=rec_out.source,
                latency_ms=rec_out.latency_ms,
                result=f"Approved {approved_count} out of {retrieved_count}",
                summary=f"Query: {rec_out.retrieval_query}",
                retrieved=retrieved_count,
                approved=approved_count,
                rejected=rejected_count,
                approval_rate=approval_rate
            ))
            
            context.action_history.append(ActionHistoryItem(
                timestamp=now_iso,
                agent="Orchestrator",
                action=f"Retrieved and approved {approved_count} new products.",
                domain=domain
            ))

    # ------------------------------------------------------------------
    # Intent Parser
    # ------------------------------------------------------------------

    def _parse_intent(self, message: str, context: AgentExecutionContext) -> dict:
        """
        Uses Gemini to parse intent, domain, and routing instructions.
        Detects topic switches, product info requests, and cart operations by characteristic.
        """
        # Build a compact cart summary for the LLM to reference
        cart_summary = []
        for d, cws in context.cart_workspaces.items():
            for item in getattr(cws, 'cart_items', []):
                details = self.retrieval_service.get_product_details_index(item.parent_asin)
                title = details.get("metadata", {}).get("title", item.parent_asin) if details else item.parent_asin
                cart_summary.append(f"[{d}] {title} (ASIN: {item.parent_asin})")
        
        cart_str = "\n".join(cart_summary[:10]) if cart_summary else "Cart is empty."
        
        # Recent conversation for context (so LLM knows if this is first or follow-up)
        recent_msgs = context.recent_messages[-4:]
        convo_str = "\n".join([f"{m.get('role','user')}: {m.get('content','')[:100]}" for m in recent_msgs])

        prompt = f"""You are the Intent Router for an AI Shopping Assistant.

USER MESSAGE: "{message}"
ACTIVE DOMAINS: {context.active_domains}
CURRENT PAGE CONTEXT: {json.dumps(context.current_page_context)}
RECENT CONVERSATION:
{convo_str}
CURRENT CART:
{cart_str}

ACTIONS (pick exactly one):
- "converse": General conversation, consultation, asking questions, greeting, OR when user mentions a goal/event but hasn't asked for recommendations yet. USE THIS when the user is DESCRIBING what they want — the system should ask clarifying questions first before recommending.
- "recommend": User EXPLICITLY asks to see/suggest products NOW (e.g., "show me options", "suggest some", "what do you have")
- "product_info": User asks about a SPECIFIC product's details, features, specs
- "add_to_cart": User wants to add something to cart
- "remove_from_cart": User wants to remove something from cart (can be by name/characteristic)
- "clear_cart": User wants to empty the entire cart
- "plan_event": User has ALREADY discussed preferences and NOW explicitly asks to BUILD the cart or PROCEED (e.g., "go ahead", "build my cart", "create the cart", "let's do it"). Do NOT use this on the FIRST message about an event — converse first!
- "compare_product": User wants to compare products

CRITICAL RULES:
1. If user asks for a NEW product category different from active domains:
   - action = "recommend", domain = NEW topic, replace_active_domain = OLD domain
   - EXCEPTION: If user says "also", "as well", "in addition", "I also need" → do NOT replace. Leave replace_active_domain empty so both domains coexist.
2. If user says "suggest", "recommend", "show me", "what do you have" → action = "recommend"
3. If user asks "tell me more about X", "what are the features of X", "is X good?" → action = "product_info"
4. If user says "remove the dog one" or "take out the expensive item" → action = "remove_from_cart", target_category = description
5. EVENT/GOAL FLOW:
   - If user FIRST mentions an event ("I'm planning a movie night") AND there is NO prior conversation about it → action = "converse" (ask 1 quick question)
   - If user provides preferences/details in RESPONSE to a question (budget, people, snack types, etc.) → action = "plan_event" (they've given enough info, proceed to build)
   - If user says "go ahead", "build it", "yes", "sounds good", "proceed" → action = "plan_event"
6. If user is just greeting or making small talk → action = "converse"
7. If user says "just recommend" or "no questions, just show me" → action = "recommend"
8. DOMAIN RULE: Keep the domain consistent with the ongoing conversation. If user is talking about movie night and mentions "soda" or "popcorn", the domain stays "movie_night" — those are subcategories, NOT new domains.

OUTPUT JSON:
{{
    "action": "string",
    "domain": "string (underscore_separated, e.g. coffee, gaming_laptop, movie_night)",
    "target_category": "string (product category or description for cart ops)",
    "target_product_asin": "string (ASIN if user refers to a specific product, empty otherwise)",
    "budget_limit": 0.0,
    "abandon_domain": "",
    "replace_active_domain": ""
}}"""

        try:
            client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY_ORCHESTRATOR"))
            response = client.models.generate_content(
                model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
            )
            result = json.loads(response.text)
            
            # Deterministic Domain Resolution
            parsed_domain = result.get("domain", "")
            final_domain = "general_shopping"
            
            if parsed_domain and parsed_domain not in ("general", ""):
                final_domain = parsed_domain
            elif context.current_page_context and context.current_page_context.get("page_type") == "product":
                if len(context.active_domains) > 0:
                    final_domain = context.active_domains[-1]
            elif len(context.active_domains) > 0:
                final_domain = context.active_domains[-1]
                
            if final_domain == "general":
                final_domain = "general_shopping"
            result["domain"] = final_domain
            
            # Save budget
            b = result.get("budget_limit")
            if b:
                context.consultation_state.budget_preference = f"under ${b}"
                
            return result
        except Exception as e:
            logger.error(f"Intent parsing failed: {e}")
            final_domain = context.active_domains[-1] if context.active_domains else "general_shopping"
            return {"action": "converse", "domain": final_domain}
