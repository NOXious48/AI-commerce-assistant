"""
Test: Movie Night Consultation Flow
=====================================
Simulates the exact user flow:
1. User says "I'm planning a movie night for 4 people"
   → Expected: Rufus asks 1-2 questions, does NOT recommend products yet
2. User provides preferences "Under $50, chips and chocolate, no nuts"
   → Expected: System triggers plan_event, retrieves products, filters, builds cart

Run: python tests/test_movie_night_flow.py
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"
HEADERS = {"Authorization": "Bearer demo_token", "Content-Type": "application/json"}


def test_movie_night_flow():
    print("=" * 60)
    print("  TEST: Movie Night Consultation Flow")
    print("=" * 60)
    
    # Step 0: Create a new session
    print("\n[Step 0] Creating new session...")
    res = requests.post(f"{BASE_URL}/api/chat/new-session", headers=HEADERS)
    assert res.status_code == 200, f"Failed to create session: {res.text}"
    session = res.json()
    session_id = session["session_id"]
    print(f"  ✓ Session created: {session_id}")

    # =================================================================
    # Step 1: "I'm planning a movie night for 4 people"
    # Expected: Conversational response asking questions. NO products.
    # =================================================================
    print("\n[Step 1] Sending: 'I'm planning a movie night for 4 people'")
    start = time.time()
    res = requests.post(f"{BASE_URL}/api/chat", headers=HEADERS, json={
        "session_id": session_id,
        "message": "I'm planning a movie night for 4 people",
        "page_context": {}
    })
    elapsed = time.time() - start
    assert res.status_code == 200, f"Chat failed: {res.text}"
    data = res.json()
    
    reply = data["reply"]
    products = data.get("products", [])
    cart_items = data.get("cart_items", [])
    active_domains = data.get("active_domains", [])
    
    print(f"  ⏱  Response time: {elapsed:.1f}s")
    print(f"  💬 Reply: {reply[:200]}")
    print(f"  📦 Products shown: {len(products)}")
    print(f"  🛒 Cart items: {len(cart_items)}")
    print(f"  🌐 Active domains: {active_domains}")
    
    # ASSERTIONS for Step 1
    step1_pass = True
    if len(products) > 0:
        print("  ❌ FAIL: Products were shown on first message (should only ask questions)")
        step1_pass = False
    else:
        print("  ✓ PASS: No products dumped on first message")
    
    if len(cart_items) > 0:
        print("  ❌ FAIL: Cart items added on first message (should only consult)")
        step1_pass = False
    else:
        print("  ✓ PASS: Cart is empty (consultation phase)")
    
    if "?" in reply:
        print("  ✓ PASS: Rufus asked a question")
    else:
        print("  ⚠️ WARNING: Reply doesn't contain a question mark")

    # =================================================================
    # Step 2: "Under $50 total, we like chips and chocolate, no nuts"
    # Expected: plan_event triggers, products retrieved, cart built
    # =================================================================
    print("\n[Step 2] Sending: 'Under $50 total, we like chips and chocolate, no nuts'")
    start = time.time()
    res = requests.post(f"{BASE_URL}/api/chat", headers=HEADERS, json={
        "session_id": session_id,
        "message": "Under $50 total, we like chips and chocolate, no nuts",
        "page_context": {}
    })
    elapsed = time.time() - start
    assert res.status_code == 200, f"Chat failed: {res.text}"
    data = res.json()
    
    reply = data["reply"]
    products = data.get("products", [])
    cart_items = data.get("cart_items", [])
    active_domains = data.get("active_domains", [])
    actions = data.get("actions_taken", [])
    audit = data.get("execution_audit_trail", [])
    
    print(f"  ⏱  Response time: {elapsed:.1f}s")
    print(f"  💬 Reply: {reply[:200]}")
    print(f"  📦 Products shown: {len(products)}")
    print(f"  🛒 Cart items: {len(cart_items)}")
    print(f"  🌐 Active domains: {active_domains}")
    print(f"  📋 Actions taken: {len(actions)}")
    if actions:
        for a in actions[:5]:
            action_text = a.get("action", str(a)) if isinstance(a, dict) else str(a)
            print(f"      → {action_text}")
    
    # ASSERTIONS for Step 2
    step2_pass = True
    if len(products) == 0:
        print("  ❌ FAIL: No products retrieved after user gave preferences")
        step2_pass = False
    else:
        print(f"  ✓ PASS: {len(products)} products retrieved")
    
    if len(cart_items) == 0:
        print("  ⚠️ WARNING: Cart is still empty (plan_event may not have triggered)")
    else:
        print(f"  ✓ PASS: {len(cart_items)} items added to cart")
        for item in cart_items[:3]:
            title = item.get("title", item.get("parent_asin", "?"))
            print(f"      🛒 {title[:60]} (${item.get('price', '?')})")
    
    # Check that "no nuts" constraint was applied
    nut_products = [p for p in products if "nut" in (p.get("title", "") + " ".join(p.get("features", []))).lower()]
    if nut_products:
        print(f"  ⚠️ WARNING: {len(nut_products)} products might contain nuts (review agent should have filtered)")
    else:
        print("  ✓ PASS: No nut-containing products in results")

    # =================================================================
    # Summary
    # =================================================================
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    print(f"  Step 1 (Consultation): {'✓ PASS' if step1_pass else '❌ FAIL'}")
    print(f"  Step 2 (Plan & Build): {'✓ PASS' if step2_pass else '❌ FAIL'}")
    print(f"  Overall: {'✓ ALL TESTS PASSED' if step1_pass and step2_pass else '❌ SOME TESTS FAILED'}")
    print("=" * 60)


if __name__ == "__main__":
    test_movie_night_flow()
