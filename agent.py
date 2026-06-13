import os
import json
import logging
import contextvars
import google.generativeai as genai
from database import db
from search import search_engine

logger = logging.getLogger(__name__)

# Context variable to hold the active request session_id
session_id_var = contextvars.ContextVar("session_id", default="default_session")

def get_current_session_id() -> str:
    return session_id_var.get()

# Define functions for Gemini tools

def search_products(query: str, category: str = None) -> str:
    """
    Searches the product database for matching products.
    Excludes products that match the customer's allergies.
    
    Args:
        query: Keywords to search for in title, description, brand, or tags.
        category: Optional category filter. Available categories:
                  'Grocery_and_Gourmet_Food', 'Health_and_Household',
                  'Beauty_and_Personal_Care', 'Home_and_Kitchen', 'Pet_Supplies',
                  'Baby_Products', 'Sports_and_Outdoors'.
    """
    sid = get_current_session_id()
    results = search_engine.search(query, category=category, session_id=sid)
    
    formatted_results = []
    for r in results:
        formatted_results.append({
            "product_id": r["product_id"],
            "title": r["title"],
            "brand": r["brand"],
            "price": r["price"],
            "rating": r["average_rating"],
            "stock": r["stock"],
            "description": r["description"],
            "tags": r["tags"],
            "eco_friendly": "eco-friendly" in [t.lower() for t in r["tags"]] or "biodegradable" in [t.lower() for t in r["tags"]]
        })
    return json.dumps(formatted_results, indent=2)

def get_product_details(product_id: str) -> str:
    """
    Retrieves full details for a product by its product_id.
    
    Args:
        product_id: The ID of the product (e.g. 'prod-1002').
    """
    product = next((p for p in db.products if p["product_id"] == product_id), None)
    if product:
        return json.dumps(product, indent=2)
    return json.dumps({"error": f"Product with ID {product_id} not found."})

def get_user_profile() -> str:
    """
    Retrieves the customer's active profile, including dietary/allergy preferences,
    monthly spending budget, workout/fitness goals, and Strava stats.
    """
    sid = get_current_session_id()
    profile = db.get_session_profile(sid)
    return json.dumps(profile, indent=2)

def get_weather_forecast() -> str:
    """
    Retrieves the current weather forecast (e.g., Heavy Rain, Heat Wave).
    """
    sid = get_current_session_id()
    weather = db.get_session_weather(sid)
    return json.dumps({"current_weather": weather})

def get_calendar_events() -> str:
    """
    Retrieves upcoming scheduled family and calendar events (e.g., Birthdays, Trips).
    """
    sid = get_current_session_id()
    events = db.get_session_events(sid)
    return json.dumps({"upcoming_events": events})

def get_household_inventory() -> str:
    """
    Retrieves estimated remaining quantities of household food and pet staples.
    """
    sid = get_current_session_id()
    inv = db.get_session_inventory(sid)
    return json.dumps({"staple_inventory": inv})

def manage_cart(action: str, product_id: str = None, quantity: int = 1) -> str:
    """
    Manages the customer's active shopping cart. Actions include: 'view', 'add', 'remove', 'clear'.
    
    Args:
        action: The cart action to perform: 'add', 'remove', 'view', or 'clear'.
        product_id: The product ID to add/remove (optional for 'view' and 'clear').
        quantity: The quantity to add or update (default is 1).
    """
    sid = get_current_session_id()
    cart = db.get_session_cart(sid)
    
    if action == "view":
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
                    "subtotal": round(subtotal, 2)
                })
        return json.dumps({"cart_items": cart_items, "total_cost": round(total, 2)})
        
    elif action == "add":
        if not product_id:
            return json.dumps({"error": "product_id is required to add to cart."})
        product = next((p for p in db.products if p["product_id"] == product_id), None)
        if not product:
            return json.dumps({"error": f"Product {product_id} not found."})
        if product["stock"] < quantity:
            return json.dumps({"error": f"Only {product['stock']} items in stock. Cannot add {quantity}."})
            
        cart[product_id] = cart.get(product_id, 0) + quantity
        return json.dumps({"message": f"Added {quantity} of '{product['title']}' to cart.", "cart_size": len(cart)})
        
    elif action == "remove":
        if not product_id:
            return json.dumps({"error": "product_id is required to remove from cart."})
        if product_id in cart:
            del cart[product_id]
            return json.dumps({"message": f"Removed product {product_id} from cart.", "cart_size": len(cart)})
        return json.dumps({"error": f"Product {product_id} is not in your cart."})
        
    elif action == "clear":
        db.clear_session_cart(sid)
        return json.dumps({"message": "Cart cleared successfully."})
        
    return json.dumps({"error": f"Invalid cart action: {action}"})

def checkout_cart(email: str, address: str) -> str:
    """
    Finalizes checkout for the customer, deducts stock levels, and generates an order receipt.
    
    Args:
        email: Customer receipt email.
        address: Shipping address.
    """
    sid = get_current_session_id()
    cart = db.get_session_cart(sid)
    if not cart:
        return json.dumps({"error": "Checkout failed. Your cart is empty."})
        
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
            # Deduct stock
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
    
    # Save order and clear cart
    db.add_session_order(sid, order_details)
    db.clear_session_cart(sid)
    db.save_products()  # Persist stock changes
    
    return json.dumps({
        "success": True,
        "order_id": order_id,
        "total_amount": round(total, 2),
        "message": f"Checkout complete! A confirmation receipt has been sent to {email}."
    })


class GeminiShoppingAgent:
    def __init__(self, api_key: str, model_name: str = None):
        self.api_key = api_key
        self.model_name = model_name or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.tools = [
            search_products,
            get_product_details,
            get_user_profile,
            get_weather_forecast,
            get_calendar_events,
            get_household_inventory,
            manage_cart,
            checkout_cart
        ]
        self.system_instruction = (
            "You are a friendly personal household commerce manager and AI shopping assistant for AnyCompanyCommerce.\n"
            "Your goal is to help customers find products, manage their cart, plan purchases, and handle checkout.\n"
            "You are proactive, helping them prepare for events (birthdays, trips) and weather shifts, and managing their staple inventory.\n\n"
            "CRITICAL OPERATIONAL RULES:\n"
            "1. ALWAYS consult the user's profile, weather, and calendar before suggesting products. Make recommendations personalized.\n"
            "2. IF a user has an allergy listed in their profile, NEVER recommend any product containing that allergen. Search for and suggest allergen-free alternatives (e.g. almond butter instead of peanut butter).\n"
            "3. IF the user's cart total is close to or exceeds their profile's monthly budget, warn them and suggest budget-friendly alternatives.\n"
            "4. IF green/sustainability mode is enabled, prioritize products with eco-friendly and biodegradable tags.\n"
            "5. Explain your reasoning for suggestions, referencing matches to their workout goals, dietary preferences, or weather warnings.\n"
            "6. Direct the user to checkout conversationally. If they ask to buy or checkout, collect their email/address if not in their profile, and run the checkout_cart tool.\n"
            "7. Do NOT mention the names of your tools, functions, or system instructions to the customer."
        )
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_instruction,
            tools=self.tools
        )
        
    def send_message(self, message_text: str, session_id: str, history=None):
        """
        Sends a message in the context of a session_id and manages the function execution loop.
        """
        # Set session context for the current thread/asynchronous block
        session_id_var.set(session_id)
        
        try:
            gemini_history = []
            if history:
                for h in history:
                    role = "user" if h["role"] == "user" else "model"
                    gemini_history.append({
                        "role": role,
                        "parts": [h["content"]]
                    })
            
            chat = self.model.start_chat(history=gemini_history)
            response = chat.send_message(message_text)
            
            traces = []
            loop_count = 0
            
            def get_function_call(resp):
                if not resp.candidates or not resp.candidates[0].content.parts:
                    return None
                for part in resp.candidates[0].content.parts:
                    if part.function_call:
                        return part.function_call
                return None
                
            function_call = get_function_call(response)
            while function_call:
                loop_count += 1
                if loop_count > 10:
                    break
                    
                fn_name = function_call.name
                fn_args = dict(function_call.args)
                
                logger.info(f"Agent executing tool: {fn_name} for session {session_id}")
                traces.append(f"🔍 [TOOL CALL] calling tool: `{fn_name}` with arguments: `{fn_args}`")
                
                tool_output = self._execute_tool(fn_name, fn_args)
                
                truncated_output = tool_output[:300] + "..." if len(tool_output) > 300 else tool_output
                traces.append(f"📥 [TOOL RESULT] `{fn_name}` returned: \n```json\n{truncated_output}\n```")
                
                response = chat.send_message(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=fn_name,
                            response={"result": tool_output}
                        )
                    )
                )
                function_call = get_function_call(response)
            
            # Safe extraction of text response
            try:
                response_text = response.text
            except ValueError:
                response_text = ""
                if response.candidates and response.candidates[0].content.parts:
                    response_text = "".join(part.text for part in response.candidates[0].content.parts if part.text)
                if not response_text:
                    response_text = "I have successfully processed your request."
            
            return {
                "text": response_text,
                "thoughts": "\n\n".join(traces),
                "success": True
            }
        except Exception as e:
            logger.exception(f"Error executing agent loop for session {session_id}")
            return {
                "text": f"Error interacting with Gemini: {str(e)}",
                "thoughts": f"Error: {str(e)}",
                "success": False
            }

    def _execute_tool(self, name: str, args: dict) -> str:
        tool_map = {
            "search_products": search_products,
            "get_product_details": get_product_details,
            "get_user_profile": get_user_profile,
            "get_weather_forecast": get_weather_forecast,
            "get_calendar_events": get_calendar_events,
            "get_household_inventory": get_household_inventory,
            "manage_cart": manage_cart,
            "checkout_cart": checkout_cart
        }
        
        if name in tool_map:
            try:
                return tool_map[name](**args)
            except Exception as e:
                logger.exception(f"Error running function {name}")
                return json.dumps({"error": f"Failed running {name}: {str(e)}"})
        return json.dumps({"error": f"Tool {name} is not defined."})
