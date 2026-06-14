"""
Test: Multiple Simultaneous Goals + Remaining Features
=======================================================
Tests:
- Multi-domain: movie night + gaming laptop simultaneously
- "Forget movie night" removes only that domain
- 5b: Add drink (retry)
- 5c: Product info lookup (retry)
- 6b: Remove button fix

Includes delays between calls to avoid Gemini rate limiting.

Run: python tests/test_multi_domain_and_remaining.py
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"
HEADERS = {"Authorization": "Bearer demo_token", "Content-Type": "application/json"}

def wait(seconds=4):
    """Wait between API calls to avoid Gemini rate limits."""
    time.sleep(seconds)

def send_chat(session_id, message):
    """Send a chat message and return the response data."""
    res = requests.post(f"{BASE_URL}/api/chat", headers=HEADERS, json={
        "session_id": session_id,
        "message": message,
        "page_context": {}
    })
    if res.status_code != 200:
        print(f"  ❌ HTTP {res.status_code}: {res.text[:100]}")
        return None
    return res.json()


def test_multi_domain():
    print("=" * 70)
    print("  TEST 8: Multiple Simultaneous Goals")
    print("=" * 70)
    
    # Create session
    res = requests.post(f"{BASE_URL}/api/chat/new-session", headers=HEADERS)
    session_id = res.json()["session_id"]
    print(f"  Session: {session_id}")

    # =====================================================================
    # Goal 1: Movie night
    # =====================================================================
    print("\n  [8.1] Starting Goal 1: Movie Night")
    data = send_chat(session_id, "I'm planning a movie night for 4 people")
    if data:
        print(f"    Reply: {data['reply'][:100]}")
        print(f"    Domains: {data['active_domains']}")
    
    wait(3)
    
    data = send_chat(session_id, "budget $40, we like popcorn and soda")
    if data:
        print(f"    Reply: {data['reply'][:100]}")
        print(f"    Domains: {data['active_domains']}")
        print(f"    Products: {len(data.get('products', []))}")
        print(f"    Cart: {len(data.get('cart_items', []))}")
    
    wait(3)

    # =====================================================================
    # Goal 2: Gaming laptop (added WITHOUT abandoning movie night)
    # =====================================================================
    print("\n  [8.2] Starting Goal 2: Gaming Laptop (simultaneously)")
    data = send_chat(session_id, "I also need a gaming laptop under $800")
    if data:
        print(f"    Reply: {data['reply'][:100]}")
        print(f"    Domains: {data['active_domains']}")
        products = data.get('products', [])
        print(f"    Products: {len(products)}")
        
        # Check both domains exist
        domains = data['active_domains']
        has_movie = any("movie" in d for d in domains)
        has_gaming = any("gaming" in d or "laptop" in d for d in domains)
        
        if has_movie and has_gaming:
            print("    ✅ PASS: Both domains active simultaneously")
        elif has_gaming:
            print("    ⚠️ WARNING: Gaming domain exists but movie_night may have been replaced")
        else:
            print("    ❌ FAIL: Gaming domain not created")
    
    wait(3)

    # =====================================================================
    # "Forget movie night" — should only remove that domain
    # =====================================================================
    print("\n  [8.3] Abandoning Goal 1: 'forget movie night'")
    data = send_chat(session_id, "forget movie night")
    if data:
        print(f"    Reply: {data['reply'][:100]}")
        domains = data['active_domains']
        print(f"    Domains after: {domains}")
        
        has_movie = any("movie" in d for d in domains)
        has_gaming = any("gaming" in d or "laptop" in d for d in domains)
        
        if not has_movie:
            print("    ✅ PASS: movie_night domain removed")
        else:
            print("    ❌ FAIL: movie_night still active")
        
        if has_gaming:
            print("    ✅ PASS: gaming domain still active (not affected)")
        else:
            print("    ⚠️ WARNING: gaming domain was also removed")
    
    wait(3)

    # =====================================================================
    # Test 5b RETRY: "Add a drink" (with delay to avoid rate limit)
    # =====================================================================
    print("\n" + "=" * 70)
    print("  TEST 5b RETRY: Add something by category")
    print("=" * 70)
    
    # First create a fresh session with products
    res = requests.post(f"{BASE_URL}/api/chat/new-session", headers=HEADERS)
    session_id2 = res.json()["session_id"]
    
    send_chat(session_id2, "suggest some snacks")
    wait(5)
    
    data = send_chat(session_id2, "add a chocolate to my cart")
    if data:
        cart = data.get("cart_items", [])
        print(f"    Reply: {data['reply'][:150]}")
        print(f"    Cart items: {len(cart)}")
        if cart:
            print("    ✅ PASS: Item added to cart via conversation")
        else:
            print("    ⚠️ WARNING: Cart still empty")
    
    wait(5)

    # =====================================================================
    # Test 5c RETRY: Product info lookup
    # =====================================================================
    print("\n" + "=" * 70)
    print("  TEST 5c RETRY: Product info lookup")
    print("=" * 70)
    
    data = send_chat(session_id2, "tell me more about the first product you recommended")
    if data:
        reply = data['reply']
        print(f"    Reply: {reply[:250]}")
        
        has_info = any(w in reply.lower() for w in ["price", "$", "rating", "review", "features", "brand"])
        if has_info:
            print("    ✅ PASS: Reply contains product-specific information")
        else:
            print("    ⚠️ WARNING: Reply may be generic")
    
    wait(5)

    # =====================================================================
    # Test 6b FIX: Direct cart remove
    # =====================================================================
    print("\n" + "=" * 70)
    print("  TEST 6b: Direct Cart Remove (same session)")
    print("=" * 70)
    
    # Add a product first
    # Get a product from shelf
    shelf_res = requests.get(
        f"{BASE_URL}/api/recommendations/shelf?domain=snacks&session_id={session_id2}",
        headers=HEADERS
    )
    
    if shelf_res.status_code == 200:
        shelf_data = shelf_res.json()
        shelf_products = shelf_data.get("products", [])
        if shelf_products:
            test_asin = shelf_products[0]["parent_asin"]
            
            # Add it
            add_res = requests.post(f"{BASE_URL}/api/cart/add", headers=HEADERS, json={
                "session_id": session_id2, "product_id": test_asin, "quantity": 1
            })
            
            if add_res.status_code == 200:
                cart_before = len(add_res.json().get("cart_items", []))
                
                # Now remove it
                rem_res = requests.post(f"{BASE_URL}/api/cart/remove", headers=HEADERS, json={
                    "session_id": session_id2, "product_id": test_asin, "fully_remove": True
                })
                
                if rem_res.status_code == 200:
                    cart_after = len(rem_res.json().get("cart_items", []))
                    print(f"    Cart: {cart_before} → {cart_after}")
                    if cart_after < cart_before:
                        print("    ✅ PASS: Product removed via direct API")
                    else:
                        print("    ⚠️ WARNING: Product still in cart")
                else:
                    print(f"    ❌ FAIL: Remove returned {rem_res.status_code}")
            else:
                print(f"    ❌ FAIL: Add returned {add_res.status_code}")
        else:
            print("    ⚠️ SKIPPED: No shelf products")
    else:
        print(f"    ⚠️ SKIPPED: Shelf not available ({shelf_res.status_code})")

    # =====================================================================
    # Summary
    # =====================================================================
    print("\n" + "=" * 70)
    print("  ALL TESTS COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    test_multi_domain()
