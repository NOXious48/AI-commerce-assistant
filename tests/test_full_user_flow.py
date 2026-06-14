"""
Test: Full User Flow — Shelf, Refinement, Product Info, Topic Switch, Direct UI Actions
========================================================================================
Tests scenarios 4-6 from our system vision.

Run: python tests/test_full_user_flow.py
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"
HEADERS = {"Authorization": "Bearer demo_token", "Content-Type": "application/json"}


def test_full_flow():
    print("=" * 70)
    print("  FULL USER FLOW TEST")
    print("=" * 70)
    
    # =====================================================================
    # Setup: Create session and run the movie night consultation
    # =====================================================================
    print("\n[Setup] Creating session and running movie night consultation...")
    res = requests.post(f"{BASE_URL}/api/chat/new-session", headers=HEADERS)
    session_id = res.json()["session_id"]
    
    # Message 1: Start consultation
    requests.post(f"{BASE_URL}/api/chat", headers=HEADERS, json={
        "session_id": session_id,
        "message": "I'm planning a movie night for 4 people",
        "page_context": {}
    })
    
    # Message 2: Provide preferences (triggers pipeline)
    res = requests.post(f"{BASE_URL}/api/chat", headers=HEADERS, json={
        "session_id": session_id,
        "message": "Under $50, chips and chocolate, no nuts",
        "page_context": {}
    })
    setup_data = res.json()
    products = setup_data.get("products", [])
    cart_items = setup_data.get("cart_items", [])
    print(f"  ✓ Setup complete: {len(products)} products, {len(cart_items)} cart items")
    
    # =====================================================================
    # Test 4: Recommendation Shelf
    # =====================================================================
    print("\n" + "=" * 70)
    print("  TEST 4: Recommendation Shelf")
    print("=" * 70)
    
    res = requests.get(
        f"{BASE_URL}/api/recommendations/shelf?domain=movie_night&session_id={session_id}",
        headers=HEADERS
    )
    shelf = res.json()
    
    shelf_products = shelf.get("products", [])
    shelf_type = shelf.get("shelf_type", "")
    based_on = shelf.get("based_on", {})
    
    print(f"  Shelf type: {shelf_type}")
    print(f"  Products on shelf: {len(shelf_products)}")
    print(f"  Based on: {based_on}")
    
    # Check "Why Recommended" badges (approval_reasons)
    products_with_reasons = [p for p in shelf_products if p.get("approval_reasons")]
    print(f"  Products with 'Why Recommended' badges: {len(products_with_reasons)}")
    if products_with_reasons:
        sample = products_with_reasons[0]
        print(f"    Example: {sample.get('title', '?')[:50]}")
        print(f"    Badge: {sample['approval_reasons'][0]}")
    
    assert len(shelf_products) >= 6, f"Expected 6+ products on shelf, got {len(shelf_products)}"
    print("  ✓ PASS: Shelf has 6+ curated products")

    # =====================================================================
    # Test 5a: "Remove the expensive one"
    # =====================================================================
    print("\n" + "=" * 70)
    print("  TEST 5a: Remove by characteristic")
    print("=" * 70)
    
    cart_before = len(cart_items)
    res = requests.post(f"{BASE_URL}/api/chat", headers=HEADERS, json={
        "session_id": session_id,
        "message": "remove the most expensive item from my cart",
        "page_context": {}
    })
    data = res.json()
    cart_after = len(data.get("cart_items", []))
    
    print(f"  Reply: {data['reply'][:150]}")
    print(f"  Cart before: {cart_before} → Cart after: {cart_after}")
    
    if cart_after < cart_before:
        print("  ✓ PASS: Item was removed from cart")
    else:
        print("  ⚠️ WARNING: Cart size didn't decrease (removal may not have matched)")

    # =====================================================================
    # Test 5b: "Add something to drink"
    # =====================================================================
    print("\n" + "=" * 70)
    print("  TEST 5b: Add something by category")
    print("=" * 70)
    
    cart_before = cart_after
    res = requests.post(f"{BASE_URL}/api/chat", headers=HEADERS, json={
        "session_id": session_id,
        "message": "add a drink to my cart",
        "page_context": {}
    })
    data = res.json()
    cart_after = len(data.get("cart_items", []))
    
    print(f"  Reply: {data['reply'][:150]}")
    print(f"  Cart before: {cart_before} → Cart after: {cart_after}")
    
    if cart_after > cart_before:
        print("  ✓ PASS: Drink item was added to cart")
    else:
        print("  ⚠️ WARNING: No new item added")

    # =====================================================================
    # Test 5c: "Tell me about the Hershey's one"
    # =====================================================================
    print("\n" + "=" * 70)
    print("  TEST 5c: Product info lookup")
    print("=" * 70)
    
    res = requests.post(f"{BASE_URL}/api/chat", headers=HEADERS, json={
        "session_id": session_id,
        "message": "tell me about the Hershey's product",
        "page_context": {}
    })
    data = res.json()
    reply = data["reply"]
    
    print(f"  Reply: {reply[:250]}")
    
    # Check if the reply contains product-specific info (not generic)
    has_product_info = any(word in reply.lower() for word in ["hershey", "chocolate", "rating", "review", "price", "$"])
    if has_product_info:
        print("  ✓ PASS: Reply contains specific product information")
    else:
        print("  ⚠️ WARNING: Reply may not have looked up product details")

    # =====================================================================
    # Test 5d: Topic switch — "switch to coffee instead"
    # =====================================================================
    print("\n" + "=" * 70)
    print("  TEST 5d: Topic switch (movie night → coffee)")
    print("=" * 70)
    
    res = requests.post(f"{BASE_URL}/api/chat", headers=HEADERS, json={
        "session_id": session_id,
        "message": "actually, forget movie night. Show me coffee options instead.",
        "page_context": {}
    })
    data = res.json()
    active_domains = data.get("active_domains", [])
    products = data.get("products", [])
    
    print(f"  Reply: {data['reply'][:150]}")
    print(f"  Active domains: {active_domains}")
    print(f"  Products: {len(products)}")
    
    if "movie_night" not in active_domains:
        print("  ✓ PASS: movie_night domain removed")
    else:
        print("  ⚠️ WARNING: movie_night still in active domains")
    
    coffee_domain = any("coffee" in d for d in active_domains)
    if coffee_domain:
        print("  ✓ PASS: coffee domain created")
    else:
        print("  ⚠️ WARNING: No coffee domain found")

    # =====================================================================
    # Test 6a: Direct "Add to Cart" button click
    # =====================================================================
    print("\n" + "=" * 70)
    print("  TEST 6a: Direct Add to Cart (UI button)")
    print("=" * 70)
    
    # Pick a product ASIN from the shelf
    if shelf_products:
        test_asin = shelf_products[0].get("parent_asin", "")
        test_title = shelf_products[0].get("title", "?")[:50]
        
        res = requests.post(f"{BASE_URL}/api/cart/add", headers=HEADERS, json={
            "session_id": session_id,
            "product_id": test_asin,
            "quantity": 2
        })
        
        if res.status_code == 200:
            cart_data = res.json()
            cart_items = cart_data.get("cart_items", [])
            added = next((i for i in cart_items if i.get("parent_asin") == test_asin), None)
            
            print(f"  Added: {test_title} (qty: 2)")
            print(f"  Cart now has: {len(cart_items)} items")
            
            if added and added.get("quantity", 0) >= 2:
                print(f"  ✓ PASS: Product added with quantity 2")
            else:
                print(f"  ⚠️ WARNING: Quantity mismatch")
        else:
            print(f"  ❌ FAIL: API returned {res.status_code}: {res.text[:100]}")
    else:
        print("  ⚠️ SKIPPED: No products on shelf to test with")

    # =====================================================================
    # Test 6b: Direct Cart Remove
    # =====================================================================
    print("\n" + "=" * 70)
    print("  TEST 6b: Direct Cart Remove (UI button)")
    print("=" * 70)
    
    if shelf_products:
        res = requests.post(f"{BASE_URL}/api/cart/remove", headers=HEADERS, json={
            "session_id": session_id,
            "product_id": test_asin,
            "fully_remove": True
        })
        
        if res.status_code == 200:
            cart_data = res.json()
            removed = not any(i.get("parent_asin") == test_asin for i in cart_data.get("cart_items", []))
            if removed:
                print(f"  ✓ PASS: Product fully removed from cart")
            else:
                print(f"  ⚠️ WARNING: Product still in cart")
        else:
            print(f"  ❌ FAIL: API returned {res.status_code}")

    # =====================================================================
    # Test 6c: Save Product
    # =====================================================================
    print("\n" + "=" * 70)
    print("  TEST 6c: Save Product")
    print("=" * 70)
    
    if shelf_products:
        res = requests.post(f"{BASE_URL}/api/user/saved-products", headers=HEADERS, json={
            "parent_asin": test_asin
        })
        if res.status_code == 201:
            print(f"  ✓ PASS: Product saved")
        else:
            print(f"  Status: {res.status_code} — {res.text[:100]}")
        
        # Verify it's in the list
        res = requests.get(f"{BASE_URL}/api/user/saved-products", headers=HEADERS)
        if res.status_code == 200:
            saved = res.json()
            if any(p.get("parent_asin") == test_asin for p in saved):
                print(f"  ✓ PASS: Product found in saved list")
            else:
                print(f"  ⚠️ WARNING: Product not in saved list")

    # =====================================================================
    # Summary
    # =====================================================================
    print("\n" + "=" * 70)
    print("  ALL TESTS COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    test_full_flow()
