import os
import json
import logging
import math
from collections import Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REVIEWS_PATH = os.path.join(DATA_DIR, "products_reviews", "products_reviews.json")
SUMMARIES_PATH = os.path.join(DATA_DIR, "products_reviews", "review_summaries.json")

# Simple stop words for keyword extraction
STOP_WORDS = {"the", "and", "a", "to", "of", "in", "it", "is", "i", "that", "for", "on", "you", 
              "with", "was", "as", "this", "but", "are", "have", "they", "my", "not", "be", "so", 
              "or", "at", "if", "from", "just", "we", "like", "can", "good", "great", "very", "would"}

def extract_keywords(text: str, top_n: int = 5) -> list:
    words = [w.strip(".,!?()[]{}'\"") for w in text.lower().split()]
    words = [w for w in words if len(w) > 3 and w not in STOP_WORDS]
    
    # Bi-grams for better context
    bigrams = []
    for i in range(len(words) - 1):
        bigrams.append(f"{words[i]} {words[i+1]}")
        
    counts = Counter(words + bigrams)
    return [item[0] for item in counts.most_common(top_n)]

def generate_summaries():
    logger.info(f"Loading raw reviews from {REVIEWS_PATH}")
    if not os.path.exists(REVIEWS_PATH):
        logger.error("Raw reviews file not found.")
        return

    try:
        with open(REVIEWS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load reviews: {e}")
        return

    reviews_list = data.get("reviews", [])
    logger.info(f"Processing {len(reviews_list)} products...")

    summaries = {}

    for prod_data in reviews_list:
        asin = prod_data.get("parent_asin")
        if not asin:
            continue
            
        reviews = prod_data.get("reviews", [])
        if not reviews:
            continue

        total_reviews = len(reviews)
        ratings = [r.get("rating", 0) for r in reviews if isinstance(r.get("rating"), (int, float))]
        
        if not ratings:
            continue

        avg_rating = sum(ratings) / len(ratings)
        positive_count = sum(1 for r in ratings if r >= 4)
        negative_count = sum(1 for r in ratings if r <= 2)
        verified_count = sum(1 for r in reviews if r.get("verified_purchase", False))

        positive_ratio = positive_count / total_reviews
        negative_ratio = negative_count / total_reviews
        verified_ratio = verified_count / total_reviews

        # Extract complaints and praises based on rating
        positive_texts = " ".join([r.get("title", "") + " " + r.get("text", "") for r in reviews if r.get("rating", 0) >= 4])
        negative_texts = " ".join([r.get("title", "") + " " + r.get("text", "") for r in reviews if r.get("rating", 0) <= 2])

        top_praises = extract_keywords(positive_texts, top_n=5)
        top_complaints = extract_keywords(negative_texts, top_n=5)

        summaries[asin] = {
            "parent_asin": asin,
            "avg_rating": round(avg_rating, 2),
            "total_reviews": total_reviews,
            "positive_ratio": round(positive_ratio, 2),
            "negative_ratio": round(negative_ratio, 2),
            "verified_ratio": round(verified_ratio, 2),
            "top_praises": top_praises,
            "top_complaints": top_complaints
        }

    logger.info(f"Saving {len(summaries)} review summaries to {SUMMARIES_PATH}")
    
    os.makedirs(os.path.dirname(SUMMARIES_PATH), exist_ok=True)
    with open(SUMMARIES_PATH, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2)
        
    logger.info("Summaries generated successfully.")

if __name__ == "__main__":
    generate_summaries()
