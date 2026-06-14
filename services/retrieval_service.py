"""
Retrieval System for Personal AI Commerce Assistant
====================================================
Loads real Amazon product embeddings and catalog data,
performs semantic vector search using cosine similarity.

Data sources (local, mirrored on S3 bucket: ai-commerce-assistant-data-2):
  - data/embedding/embeddings.npy       (2100 x 384, float32)
  - data/embedding/id_mapping.json      (index -> {parent_asin, title, price, main_category})
  - data/product-data/products_catalog.json  (full product metadata)
  - data/products_metadata/products_metadata.json  (detailed metadata)
  - data/products_reviews/products_reviews.json    (reviews, loaded on demand)
"""

import os
import json
import logging
import numpy as np
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Step back from services/
DATA_DIR = os.path.join(BASE_DIR, "data")

class ProductDetailsCache:
    """Cache layer for instant retrieval of pre-assembled product details and reviews."""
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        
    def get(self, asin: str) -> Optional[Dict[str, Any]]:
        return self.cache.get(asin)
        
    def set(self, asin: str, data: Dict[str, Any]):
        self.cache[asin] = data



class ProductRetriever:
    """
    Semantic product retrieval engine.
    
    Uses pre-computed SentenceTransformer embeddings (all-MiniLM-L6-v2, dim=384)
    and cosine similarity for fast in-memory vector search over ~2100 products.
    """

    def __init__(self):
        self.embeddings: Optional[np.ndarray] = None      # (N, 384)
        self.id_mapping: List[Dict[str, Any]] = []         # index -> {parent_asin, title, price, main_category}
        self.catalog: Dict[str, Dict[str, Any]] = {}       # parent_asin -> full product dict
        self.metadata: Dict[str, Dict[str, Any]] = {}      # parent_asin -> metadata dict
        self.reviews: Dict[str, List[Dict[str, Any]]] = {} # parent_asin -> list of review dicts
        self.details_cache = ProductDetailsCache()          # In-memory cache for fast modal loading
        self.model = None                                   # SentenceTransformer model (lazy loaded)
        self._loaded = False

        self._load_data()

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def _load_data(self):
        """Load embeddings, id mapping, and product catalog into memory."""
        try:
            # 1. Load embeddings
            emb_path = os.path.join(DATA_DIR, "embedding", "embeddings.npy")
            self.embeddings = np.load(emb_path).astype(np.float32)
            logger.info(f"Loaded embeddings: {self.embeddings.shape}")

            # 2. Load id mapping (index -> product summary)
            id_map_path = os.path.join(DATA_DIR, "embedding", "id_mapping.json")
            with open(id_map_path, "r", encoding="utf-8") as f:
                self.id_mapping = json.load(f)
            logger.info(f"Loaded id_mapping: {len(self.id_mapping)} entries")

            # 3. Load full product catalog and index by parent_asin
            catalog_path = os.path.join(DATA_DIR, "product-data", "products_catalog.json")
            with open(catalog_path, "r", encoding="utf-8") as f:
                catalog_raw = json.load(f)
            
            # Handle both formats: list or {"catalog": [...]}
            if isinstance(catalog_raw, dict) and "catalog" in catalog_raw:
                catalog_list = catalog_raw["catalog"]
            elif isinstance(catalog_raw, list):
                catalog_list = catalog_raw
            else:
                catalog_list = []
            
            for product in catalog_list:
                asin = product.get("parent_asin")
                if asin:
                    self.catalog[asin] = product
            logger.info(f"Loaded product catalog: {len(self.catalog)} products")

            # 4. Load detailed metadata (optional, may be large)
            meta_path = os.path.join(DATA_DIR, "products_metadata", "products_metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_raw = json.load(f)
                if isinstance(meta_raw, list):
                    for item in meta_raw:
                        asin = item.get("parent_asin")
                        if asin:
                            self.metadata[asin] = item
                elif isinstance(meta_raw, dict):
                    if "products" in meta_raw:
                        for item in meta_raw["products"]:
                            asin = item.get("parent_asin")
                            if asin:
                                self.metadata[asin] = item
                    else:
                        self.metadata = meta_raw
                logger.info(f"Loaded product metadata: {len(self.metadata)} entries")
                
            # 5. Build Startup Product Details Index
            review_summaries = {}
            summaries_path = os.path.join(DATA_DIR, "products_reviews", "review_summaries.json")
            if os.path.exists(summaries_path):
                try:
                    with open(summaries_path, "r", encoding="utf-8") as f:
                        review_summaries = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not load review summaries: {e}")

            for asin, meta_entry in self.metadata.items():
                review_summary = review_summaries.get(asin, {})
                meta_inner = meta_entry.get("metadata", meta_entry)
                self.details_cache.set(asin, {
                    "metadata": {
                        "title": meta_inner.get("title", ""),
                        "brand": meta_inner.get("store", meta_inner.get("brand", "")),
                        "category": meta_inner.get("main_category", ""),
                        "price": meta_inner.get("price", 0.0),
                        "description": meta_inner.get("description", ""),
                        "features": meta_inner.get("features", []),
                        "images": meta_inner.get("images", [meta_inner.get("image_url")]) if "images" in meta_inner else [meta_inner.get("image_url")],
                    },
                    "reviews": {
                        "avg_rating": review_summary.get("avg_rating", meta_inner.get("average_rating", 0)),
                        "total_reviews": review_summary.get("total_reviews", meta_inner.get("rating_number", 0)),
                        "positive_ratio": review_summary.get("positive_ratio", 0),
                        "negative_ratio": review_summary.get("negative_ratio", 0),
                        "verified_ratio": review_summary.get("verified_ratio", 0),
                        "positive_highlights": review_summary.get("top_praises", []),
                        "negative_highlights": review_summary.get("top_complaints", []),
                    }
                })
            logger.info(f"Built ProductDetailsCache: {len(self.details_cache.cache)} entries")

            # 6. Load raw product reviews (keyed by parent_asin for O(1) lookup)
            # Skip on memory-constrained servers (set SKIP_REVIEWS=true)
            if os.environ.get("SKIP_REVIEWS", "false").lower() != "true":
                reviews_path = os.path.join(DATA_DIR, "products_reviews", "products_reviews.json")
                if os.path.exists(reviews_path):
                    try:
                        with open(reviews_path, "r", encoding="utf-8") as f:
                            reviews_raw = json.load(f)
                        reviews_list = reviews_raw.get("reviews", [])
                        if isinstance(reviews_list, list):
                            for entry in reviews_list:
                                asin = entry.get("parent_asin")
                                if asin:
                                    self.reviews[asin] = entry.get("reviews", [])
                        logger.info(f"Loaded product reviews: {len(self.reviews)} products")
                    except Exception as e:
                        logger.warning(f"Could not load product reviews: {e}")
            else:
                logger.info("Skipping product reviews (SKIP_REVIEWS=true)")

            # Pre-normalize embeddings for fast cosine similarity
            norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1  # avoid division by zero
            self.embeddings = self.embeddings / norms

            self._loaded = True
            print(f"[OK] Retrieval system loaded: {self.embeddings.shape[0]} products, {self.embeddings.shape[1]}-dim embeddings")

        except Exception as e:
            logger.exception(f"Failed to load retrieval data: {e}")
            print(f"[ERROR] Retrieval system failed to load: {e}")
            self._loaded = False

    def _get_model(self):
        """Lazy-load the SentenceTransformer model (same one used to generate embeddings)."""
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            print("[OK] SentenceTransformer model loaded (all-MiniLM-L6-v2)")
        return self.model

    # ------------------------------------------------------------------
    # Core Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 10,
        category: str = None,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search over the product catalog.

        Args:
            query:      Natural language search query.
            top_k:      Number of results to return.
            category:   Optional category filter (e.g. "Grocery").
            min_score:  Minimum cosine similarity score threshold.

        Returns:
            List of product dicts with similarity scores, sorted by relevance.
        """
        if not self._loaded:
            logger.error("Retrieval system not loaded.")
            return []

        # Embed the query
        model = self._get_model()
        query_vec = model.encode(query, normalize_embeddings=True).astype(np.float32)

        # Cosine similarity (embeddings are already normalized)
        similarities = self.embeddings @ query_vec  # (N,)

        # Apply category filter if specified
        if category:
            cat_lower = category.lower()
            for i, mapping in enumerate(self.id_mapping):
                prod_cat = mapping.get("main_category", "").lower()
                if cat_lower not in prod_cat:
                    similarities[i] = -1.0

        # Get top-K indices
        top_indices = np.argsort(similarities)[::-1][:top_k * 2]  # get extra to filter

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score < min_score:
                continue

            idx = int(idx)
            if idx >= len(self.id_mapping):
                continue

            mapping = self.id_mapping[idx]
            asin = mapping.get("parent_asin", "")

            # Build result from catalog (rich data) falling back to id_mapping (lightweight)
            catalog_entry = self.catalog.get(asin, {})

            # Get image URL from metadata
            image_url = ""
            meta_entry = self.metadata.get(asin, {})
            meta_inner = meta_entry.get("metadata", meta_entry)
            images = meta_inner.get("images", [])
            if images:
                # Prefer hi_res MAIN image via proxy, fallback to large
                main_img = next((img for img in images if img.get("variant") == "MAIN"), images[0])
                image_url = main_img.get("hi_res") or main_img.get("large") or main_img.get("thumb", "")

            result = {
                "parent_asin": asin,
                "title": catalog_entry.get("title", mapping.get("title", "Unknown")),
                "price": catalog_entry.get("price", mapping.get("price", 0.0)),
                "main_category": catalog_entry.get("main_category", mapping.get("main_category", "")),
                "average_rating": catalog_entry.get("average_rating", 0.0),
                "store": catalog_entry.get("store", ""),
                "features": catalog_entry.get("features", []),
                "description": catalog_entry.get("description", []),
                "categories": catalog_entry.get("categories", []),
                "similarity_score": round(score, 4),
                "image_url": image_url,
                "rating_number": meta_inner.get("rating_number", 0),
            }
            results.append(result)

            if len(results) >= top_k:
                break

        return results

    def get_product_details(self, parent_asin: str) -> Optional[Dict[str, Any]]:
        """Get full product details by ASIN from the catalog."""
        return self.catalog.get(parent_asin)

    def get_product_metadata(self, parent_asin: str) -> Optional[Dict[str, Any]]:
        """Get detailed metadata by ASIN."""
        return self.metadata.get(parent_asin)
    def get_product_details_index(self, parent_asin: str) -> Optional[Dict[str, Any]]:
        """Get O(1) merged product details from the Cache."""
        return self.details_cache.get(parent_asin)

    def get_product_reviews(self, parent_asin: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get raw review texts for a product. O(1) lookup."""
        return self.reviews.get(parent_asin, [])[:limit]

    def get_categories(self) -> List[str]:
        """Get list of all unique main categories in the dataset."""
        cats = set()
        for m in self.id_mapping:
            cat = m.get("main_category", "")
            if cat:
                cats.add(cat)
        return sorted(cats)


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------
retriever = ProductRetriever()


# ------------------------------------------------------------------
# CLI Test Interface
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Product Retrieval System — Interactive Test")
    print("=" * 60)
    print(f"  Products loaded: {len(retriever.id_mapping)}")
    print(f"  Categories: {', '.join(retriever.get_categories())}")
    print("=" * 60)
    print("  Type a query to search. Type 'quit' to exit.\n")

    while True:
        try:
            query = input("🔍 Search: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not query or query.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        results = retriever.search(query, top_k=5)

        if not results:
            print("  No results found.\n")
            continue

        print(f"\n  Found {len(results)} results:\n")
        for i, r in enumerate(results, 1):
            print(f"  {i}. [{r['similarity_score']:.3f}] ${r['price']:.2f} — {r['title'][:80]}")
            if r.get("store"):
                print(f"     Store: {r['store']}  |  Category: {r['main_category']}  |  Rating: {r['average_rating']}")
            if r.get("features"):
                print(f"     Feature: {r['features'][0][:100]}...")
            print()
