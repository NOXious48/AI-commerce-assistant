import logging
import json
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class ConstraintResolverOutput(BaseModel):
    positive_constraints: List[str] = Field(default_factory=list)
    negative_constraints: List[str] = Field(default_factory=list)
    preferred_brands: List[str] = Field(default_factory=list)
    must_have_features: List[str] = Field(default_factory=list)
    nice_to_have_features: List[str] = Field(default_factory=list)
    price_range: Dict[str, Optional[float]] = Field(default_factory=dict) # e.g. {"min": 0, "max": 50}

class ConstraintResolver:
    """
    Centralizes the extraction and formatting of constraints (dietary, brand, budget, etc.)
    so that all downstream agents (Recommendation, Review) use a standard schema.
    """
    def __init__(self):
        self.model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    def resolve(self, consultation_state: Any, user_memory: Dict[str, Any], current_query: str) -> ConstraintResolverOutput:
        """
        Merges current consultation state, user memory, and the current query 
        into a definitive constraint snapshot.
        """
        # Gather context
        dietary = getattr(consultation_state, 'dietary_preferences', [])
        budget_str = getattr(consultation_state, 'budget_preference', "")
        fav_brands = getattr(consultation_state, 'favorite_brands', [])
        avoid_brands = getattr(consultation_state, 'avoided_brands', [])
        
        mem_dietary = user_memory.get("dietary_preferences", [])
        mem_fav_brands = user_memory.get("favorite_brands", [])
        mem_avoid_brands = user_memory.get("avoided_brands", [])

        # Build prompt
        prompt = f"""
        You are the Constraint Resolver for an AI Shopping Assistant.
        Your job is to normalize and extract explicit constraints for product retrieval and filtering.

        CURRENT SESSION STATE:
        Dietary: {dietary}
        Budget Pref: {budget_str}
        Favorite Brands: {fav_brands}
        Avoided Brands: {avoid_brands}

        LONG-TERM USER MEMORY:
        Dietary: {mem_dietary}
        Favorite Brands: {mem_fav_brands}
        Avoided Brands: {mem_avoid_brands}

        CURRENT USER QUERY:
        "{current_query}"

        Instructions:
        1. Extract positive_constraints (e.g., "vegan", "gluten-free", "organic", "wireless").
        2. Extract negative_constraints (e.g., "contains nuts", "dairy", "wired").
        3. Merge preferred_brands from state, memory, and query.
        4. Extract must_have_features and nice_to_have_features from the query.
        5. Extract price_range. If a budget is mentioned like "under $50", return {{"max": 50.0}}. If "between $20 and $40", return {{"min": 20.0, "max": 40.0}}. Otherwise return empty.

        Return ONLY a JSON matching this schema:
        {{
            "positive_constraints": ["str"],
            "negative_constraints": ["str"],
            "preferred_brands": ["str"],
            "must_have_features": ["str"],
            "nice_to_have_features": ["str"],
            "price_range": {{"min": null, "max": null}}
        }}
        """
        try:
            client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY_ORCHESTRATOR"))
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            data = json.loads(response.text)
            return ConstraintResolverOutput(**data)
        except Exception as e:
            logger.error(f"[ConstraintResolver] Failed to resolve constraints: {e}")
            # Fallback to simple mapping
            out = ConstraintResolverOutput()
            out.positive_constraints.extend(dietary)
            out.positive_constraints.extend(mem_dietary)
            out.preferred_brands.extend(fav_brands)
            out.preferred_brands.extend(mem_fav_brands)
            out.negative_constraints.extend(avoid_brands)
            out.negative_constraints.extend(mem_avoid_brands)
            
            # Parse "no X" patterns from dietary preferences into negative constraints
            for pref in (dietary + mem_dietary):
                if isinstance(pref, str):
                    pref_lower = pref.lower().strip()
                    if pref_lower.startswith("no "):
                        neg = pref_lower[3:].strip()
                        if neg and neg not in out.negative_constraints:
                            out.negative_constraints.append(neg)
                            # Remove from positive
                            if pref in out.positive_constraints:
                                out.positive_constraints.remove(pref)
            
            # Parse budget from consultation state
            if budget_str:
                import re
                match = re.search(r'\$?(\d+)', budget_str)
                if match:
                    out.price_range = {"max": float(match.group(1))}
            
            return out
