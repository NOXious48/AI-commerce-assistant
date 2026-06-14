import pytest
from review_filter_agent import review_filter_agent, review_data_index
from schemas import ReviewFilterResult

# Mock some review summaries
review_data_index.summaries = {
    "GOOD_PROD": {
        "parent_asin": "GOOD_PROD",
        "avg_rating": 4.8,
        "positive_ratio": 0.9,
        "negative_ratio": 0.05,
        "verified_ratio": 0.8,
        "top_praises": ["great taste", "high quality"],
        "top_complaints": []
    },
    "BAD_PROD": {
        "parent_asin": "BAD_PROD",
        "avg_rating": 2.1,
        "positive_ratio": 0.1,
        "negative_ratio": 0.6,
        "verified_ratio": 0.5,
        "top_praises": [],
        "top_complaints": ["tastes awful", "waste of money"]
    },
    "GLUTEN_PROD": {
        "parent_asin": "GLUTEN_PROD",
        "avg_rating": 4.0,
        "positive_ratio": 0.7,
        "negative_ratio": 0.1,
        "verified_ratio": 0.8,
        "top_praises": ["tasty"],
        "top_complaints": ["contains gluten", "allergic reaction"]
    }
}

def test_hard_rejection_brand():
    products = [{"parent_asin": "P1", "store": "BrandX", "price": 10}]
    mem = {"avoided_brands": ["brandx"]}
    state = {}
    
    res = review_filter_agent.filter_products(products, state, mem)
    assert len(res.approved_products) == 0
    assert len(res.rejected_products) == 1
    assert "avoided list" in res.filtering_reasons["P1"][0]

def test_hard_rejection_dietary():
    products = [{"parent_asin": "GLUTEN_PROD", "price": 10}]
    mem = {"dietary_preferences": ["gluten free"]}
    state = {}
    
    res = review_filter_agent.filter_products(products, state, mem)
    assert len(res.approved_products) == 0
    assert len(res.rejected_products) == 1
    assert "gluten" in res.filtering_reasons["GLUTEN_PROD"][0]

def test_hard_rejection_extreme_negative():
    products = [{"parent_asin": "BAD_PROD", "price": 10}]
    
    res = review_filter_agent.filter_products(products, {}, {})
    assert len(res.approved_products) == 0
    assert len(res.rejected_products) == 1
    assert "negative reviews" in res.filtering_reasons["BAD_PROD"][0]

def test_approval_and_sorting():
    products = [
        {"parent_asin": "GOOD_PROD", "price": 20, "similarity_score": 0.8},
        {"parent_asin": "OKAY_PROD", "price": 20, "similarity_score": 0.2} # No reviews, gets default score
    ]
    
    res = review_filter_agent.filter_products(products, {}, {})
    assert len(res.approved_products) == 2
    assert res.approved_products[0]["parent_asin"] == "GOOD_PROD" # Should be first due to high similarity and good reviews
    assert res.approved_products[0]["alignment_score"] > 70
    assert len(res.approval_reasons["GOOD_PROD"]) > 0

def test_budget_penalty():
    # Target is $20. Product is $40. Should get penalized and possibly drop below 60.
    products = [{"parent_asin": "OKAY_PROD", "price": 40, "similarity_score": 0.1}]
    state = {"budget": "under 20"}
    
    res = review_filter_agent.filter_products(products, state, {})
    # OKAY_PROD starts with default ~10 rev score + small req score (2) + 10 base pref + 5 base mem + 10 ctx = 37. 
    # With price 40 vs 20, 100% overage -> ~10 penalty. Score = ~27 < 60. Rejected.
    assert len(res.rejected_products) == 1
    assert "exceeds your target budget" in str(res.filtering_reasons["OKAY_PROD"])

def test_max_approved_limit():
    products = []
    # Create 40 identical good products
    for i in range(40):
        products.append({"parent_asin": f"PROD_{i}", "price": 10, "similarity_score": 0.9, "store": "FavBrand"})
        
    mem = {"favorite_brands": ["favbrand"]}
    
    res = review_filter_agent.filter_products(products, {}, mem)
    
    # Should cap at 30
    assert len(res.approved_products) == 30
    assert len(res.rejected_products) == 10
    assert res.metrics["approved_count"] == 30
    assert res.metrics["rejected_count"] == 10
    
    # Check reason for the 31st product
    rejected_asin = res.rejected_products[0]["parent_asin"]
    assert "maximum display limit" in res.filtering_reasons[rejected_asin][0]
