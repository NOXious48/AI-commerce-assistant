from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class ChatRequest(BaseModel):
    message: str
    session_id: str

class ChatResponse(BaseModel):
    response: str
    thoughts: str
    success: bool

class ProductSchema(BaseModel):
    product_id: str
    title: str
    brand: str
    category: str
    subcategory: str
    price: float
    average_rating: float
    rating_count: int
    description: str
    features: List[str]
    image_url: str
    pros: List[str]
    cons: List[str]
    tags: List[str]
    stock: int
    delivery_time: str
    discount: int
    availability: bool
    popularity_score: float

class ProfileSchema(BaseModel):
    first_name: str
    last_name: str
    email: str
    address: str
    age: int
    allergies: List[str]
    budget: float
    healthy_mode: bool
    green_mode: bool
    workout_goals: str
    strava_stats: str

class CartItemSchema(BaseModel):
    product_id: str
    quantity: int

class OrderItemSchema(BaseModel):
    product_id: str
    title: str
    price: float
    quantity: int

class OrderDetailsSchema(BaseModel):
    order_id: str
    email: str
    address: str
    items: List[OrderItemSchema]
    total: float
