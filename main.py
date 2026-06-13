import os
from fastapi import FastAPI, Header, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

from database import db
from search import search_engine
from agent import GeminiShoppingAgent
from schemas import (
    ChatRequest, ChatResponse, ProductSchema, 
    ProfileSchema, CartItemSchema, OrderDetailsSchema
)

# Load environment variables
load_dotenv()

from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI(
    title="Personal AI Commerce Assistant Backend",
    description="FastAPI-based agent backend using the Google GenAI SDK.",
    version="1.0.0"
)

# Enable CORS for Streamlit frontend interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static web interface
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return f.read()
    return HTMLResponse("Static file static/index.html not found.", status_code=404)

def get_api_key(x_gemini_key: Optional[str] = Header(None)) -> str:
    """
    Retrieves the Gemini API key. Prioritizes the header, falls back to environment variable.
    """
    key = x_gemini_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise HTTPException(
            status_code=401, 
            detail="Gemini API Key is missing. Please provide it in x-gemini-key header or set GEMINI_API_KEY env variable."
        )
    return key

# --- Chat/Agent Route ---

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, x_gemini_key: Optional[str] = Header(None)):
    api_key = get_api_key(x_gemini_key)
    
    # Initialize the agent with the provided API key
    agent = GeminiShoppingAgent(api_key=api_key)
    
    # We retrieve the chat history from the frontend or db if desired.
    # For stateless REST, the client passes history. For simplicity, we get history from frontend in the Streamlit client,
    # but here we can just execute the single turns since the Streamlit client maintains the session.
    # Let's execute the chat
    result = agent.send_message(request.message, session_id=request.session_id)
    
    return ChatResponse(
        response=result["text"],
        thoughts=result["thoughts"],
        success=result["success"]
    )

# --- Product Catalog Routes ---

@app.get("/api/products", response_model=List[ProductSchema])
def list_products(
    query: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(8),
    session_id: Optional[str] = Query(None)
):
    """
    Searches the product database. Incorporates profile filters if session_id is provided.
    """
    if query:
        return search_engine.search(query, category=category, limit=limit, session_id=session_id)
    
    # Return list of products filtering by category
    results = db.products
    if category:
        results = [p for p in results if p["category"].lower() == category.lower()]
    return results[:limit]

@app.get("/api/products/{productId}", response_model=ProductSchema)
def get_product(productId: str):
    product = next((p for p in db.products if p["product_id"] == productId), None)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

# --- User Profile Routes ---

@app.get("/api/profile", response_model=ProfileSchema)
def get_profile(session_id: str):
    return db.get_session_profile(session_id)

@app.post("/api/profile")
def update_profile(session_id: str, profile: ProfileSchema):
    db.update_session_profile(session_id, profile.model_dump())
    return {"message": "Profile updated successfully"}

# --- Cart Management Routes ---

@app.get("/api/cart")
def get_cart(session_id: str):
    cart = db.get_session_cart(session_id)
    cart_items = []
    total = 0.0
    for pid, qty in cart.items():
        product = next((p for p in db.products if p["product_id"] == pid), None)
        if product:
            subtotal = product["price"] * qty
            total += subtotal
            cart_items.append({
                "product_id": pid,
                "title": product["title"],
                "price": product["price"],
                "quantity": qty,
                "subtotal": round(subtotal, 2),
                "image_url": product["image_url"]
            })
    return {"items": cart_items, "total_cost": round(total, 2)}

@app.post("/api/cart")
def add_to_cart(session_id: str, item: CartItemSchema):
    cart = db.get_session_cart(session_id)
    product = next((p for p in db.products if p["product_id"] == item.product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    if product["stock"] < item.quantity:
        raise HTTPException(status_code=400, detail=f"Only {product['stock']} available in stock.")
        
    if item.quantity <= 0:
        # If quantity <= 0, remove item
        if item.product_id in cart:
            del cart[item.product_id]
    else:
        cart[item.product_id] = item.quantity
        
    return {"message": "Cart updated", "cart_size": len(cart)}

@app.delete("/api/cart")
def clear_cart(session_id: str):
    db.clear_session_cart(session_id)
    return {"message": "Cart cleared"}

# --- Checkout API ---

@app.post("/api/checkout")
def checkout(session_id: str, email: str = Body(..., embed=True), address: str = Body(..., embed=True)):
    cart = db.get_session_cart(session_id)
    if not cart:
        raise HTTPException(status_code=400, detail="Cart is empty")
        
    order_items = []
    total = 0.0
    for pid, qty in list(cart.items()):
        product = next((p for p in db.products if p["product_id"] == pid), None)
        if product:
            subtotal = product["price"] * qty
            total += subtotal
            order_items.append({
                "product_id": pid,
                "title": product["title"],
                "price": product["price"],
                "quantity": qty
            })
            product["stock"] = max(0, product["stock"] - qty)
            
    import uuid
    order_id = f"{uuid.uuid4().hex[:8].upper()}-ORDER"
    
    order_details = {
        "order_id": order_id,
        "email": email,
        "address": address,
        "items": order_items,
        "total": round(total, 2)
    }
    
    db.add_session_order(session_id, order_details)
    db.clear_session_cart(session_id)
    db.save_products()
    
    return order_details

# --- Simulation Configurations Endpoints ---

@app.get("/api/simulator/weather")
def get_weather(session_id: str):
    return {"weather": db.get_session_weather(session_id)}

@app.post("/api/simulator/weather")
def set_weather(session_id: str, weather: str = Body(..., embed=True)):
    db.set_session_weather(session_id, weather)
    return {"message": f"Weather set to {weather}"}

@app.get("/api/simulator/events")
def get_events(session_id: str):
    return {"events": db.get_session_events(session_id)}

@app.post("/api/simulator/events")
def add_event(session_id: str, event: Dict[str, Any] = Body(...)):
    db.add_session_event(session_id, event)
    return {"message": "Event added"}

@app.get("/api/simulator/inventory")
def get_inventory(session_id: str):
    return {"inventory": db.get_session_inventory(session_id)}

@app.post("/api/simulator/inventory")
def update_inventory(session_id: str, item: str = Body(..., embed=True), days_remaining: str = Body(..., embed=True)):
    db.update_session_inventory(session_id, item, days_remaining)
    return {"message": f"Inventory updated for {item}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
