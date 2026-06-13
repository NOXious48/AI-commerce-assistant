import os
import logging
from typing import List, Dict, Any
from database import db

logger = logging.getLogger(__name__)

class HybridSearchEngine:
    def __init__(self):
        self.opensearch_client = None
        self.opensearch_endpoint = os.environ.get("OPENSEARCH_ENDPOINT")
        self.opensearch_index = os.environ.get("OPENSEARCH_INDEX", "product-catalog")
        if self.opensearch_endpoint:
            self.init_opensearch()

    def init_opensearch(self):
        try:
            import boto3
            from opensearchpy import OpenSearch, AWSV4SignerAuth, RequestsHttpConnection
            
            credentials = boto3.Session().get_credentials()
            region = os.environ.get("AWS_REGION", "us-east-1")
            auth = AWSV4SignerAuth(credentials, region, "aoss")
            host = self.opensearch_endpoint.replace("https://", "").replace("http://", "").split("/")[0]
            
            self.opensearch_client = OpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection
            )
            logger.info("Connected to Amazon OpenSearch Serverless")
        except Exception as e:
            logger.warning(f"Could not connect to OpenSearch: {e}. Running in local mode.")
            self.opensearch_client = None

    def search(self, query: str, category: str = None, limit: int = 8, session_id: str = None) -> List[Dict[str, Any]]:
        # Fetch session-specific user profile for allergies & preferences
        user_profile = None
        if session_id:
            user_profile = db.get_session_profile(session_id)
            
        if self.opensearch_client:
            try:
                body = {
                    "size": limit * 2,
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "multi_match": {
                                        "query": query,
                                        "fields": ["title^3", "brand^2", "description", "tags^2"]
                                    }
                                }
                            ]
                        }
                    }
                }
                if category:
                    body["query"]["bool"]["filter"] = [
                        {"term": {"category.keyword": category}}
                    ]
                
                response = self.opensearch_client.search(index=self.opensearch_index, body=body)
                hits = [hit["_source"] for hit in response["hits"]["hits"]]
                
                filtered_hits = self._apply_filters(hits, user_profile)[:limit]
                if filtered_hits:
                    return filtered_hits
            except Exception as e:
                logger.error(f"OpenSearch query failed: {e}. Falling back to local search.")

        return self._local_search(query, category, limit, user_profile)

    def _local_search(self, query: str, category: str = None, limit: int = 8, user_profile: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        query_words = [w.lower() for w in query.split()]
        scored_products = []
        
        healthy_mode = False
        green_mode = False
        if user_profile:
            healthy_mode = user_profile.get("healthy_mode", False)
            green_mode = user_profile.get("green_mode", False)

        for p in db.products:
            if category and p["category"].lower() != category.lower():
                continue
                
            score = 0
            title_lower = p["title"].lower()
            brand_lower = p["brand"].lower()
            desc_lower = p["description"].lower()
            tags_lower = [t.lower() for t in p["tags"]]
            sub_lower = p["subcategory"].lower()
            
            for word in query_words:
                if word in title_lower:
                    score += 15
                if word in brand_lower:
                    score += 10
                if word in sub_lower:
                    score += 12
                if word in desc_lower:
                    score += 2
                if word in tags_lower:
                    score += 6
            
            score += p.get("popularity_score", 0) * 0.5
            
            if healthy_mode and ("healthy" in tags_lower or "organic" in tags_lower or "vegan" in tags_lower):
                score += 15
                
            if green_mode and ("eco-friendly" in tags_lower or "biodegradable" in tags_lower or "recycled" in tags_lower):
                score += 15

            if score > 0 or not query_words:
                scored_products.append((p, score))
                
        scored_products.sort(key=lambda x: x[1], reverse=True)
        raw_results = [item[0] for item in scored_products]
        
        filtered_results = self._apply_filters(raw_results, user_profile)
        return filtered_results[:limit]

    def _apply_filters(self, items: List[Dict[str, Any]], user_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not user_profile:
            return items
            
        allergies = user_profile.get("allergies", [])
        if not allergies:
            return items
            
        filtered_items = []
        for item in items:
            title_lower = item["title"].lower()
            desc_lower = item["description"].lower()
            tags_lower = [t.lower() for t in item["tags"]]
            
            exclude = False
            for allergy in allergies:
                allergy_clean = allergy.lower().replace(" allergy", "").replace(" intolerance", "").strip()
                if (allergy_clean in title_lower or 
                    allergy_clean in desc_lower or 
                    any(allergy_clean in t for t in tags_lower)):
                    
                    free_keyword = f"{allergy_clean}-free"
                    free_keyword_space = f"{allergy_clean} free"
                    
                    if (free_keyword in title_lower or 
                        free_keyword_space in title_lower or 
                        "peanut-free" in tags_lower or
                        "lactose-free" in tags_lower or
                        "gluten-free" in tags_lower):
                        continue
                    else:
                        exclude = True
                        break
            
            if not exclude:
                filtered_items.append(item)
                
        return filtered_items

search_engine = HybridSearchEngine()
