import os
import json
import random
from typing import Dict, List, Any

class DatabaseManager:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.products_file = os.path.join(self.base_dir, "products.json")
        self.products: List[Dict[str, Any]] = []
        
        # In-memory storage keyed by session_id
        self.carts: Dict[str, Dict[str, int]] = {}  # session_id -> {product_id -> quantity}
        self.profiles: Dict[str, Dict[str, Any]] = {}  # session_id -> profile_dict
        self.weather: Dict[str, str] = {}  # session_id -> weather_string
        self.events: Dict[str, List[Dict[str, Any]]] = {}  # session_id -> [event_dicts]
        self.inventory: Dict[str, Dict[str, str]] = {}  # session_id -> {item -> days_remaining}
        self.orders: Dict[str, List[Dict[str, Any]]] = {}  # session_id -> [order_details]
        
        self.load_or_generate_products()

    def load_or_generate_products(self):
        if os.path.exists(self.products_file):
            try:
                with open(self.products_file, 'r') as f:
                    self.products = json.load(f)
                print(f"Loaded {len(self.products)} products from database.")
                return
            except Exception as e:
                print(f"Error reading products file, generating fresh: {e}")
                
        # Generate fresh products database
        self.generate_products()

    def generate_products(self):
        categories = {
            "Grocery_and_Gourmet_Food": {
                "subcategories": ["Beverages", "Snacks", "Breakfast", "Dairy & Cheese", "Meat & Seafood", "Pantry Staples"],
                "brands": ["Amul", "Mother Dairy", "Organix", "Nature Valley", "Quaker", "Tropicana", "Chobani", "Heinz", "Barilla", "Nestle"],
                "items": [
                    {"name": "Organic Almond Milk", "sub": "Beverages", "tags": ["beverage", "milk", "almond", "vegan", "lactose-free", "healthy", "organic"]},
                    {"name": "Whole Milk (1 Gallon)", "sub": "Dairy & Cheese", "tags": ["milk", "dairy", "breakfast", "calcium"]},
                    {"name": "Greek Yogurt - Strawberry", "sub": "Dairy & Cheese", "tags": ["yogurt", "strawberry", "dairy", "breakfast", "protein"]},
                    {"name": "Gluten-Free Rolled Oats", "sub": "Breakfast", "tags": ["oats", "oatmeal", "breakfast", "gluten-free", "fiber", "healthy"]},
                    {"name": "Organic Honey Bunches", "sub": "Breakfast", "tags": ["cereal", "breakfast", "honey", "sweet"]},
                    {"name": "Fresh Organic Bananas", "sub": "Breakfast", "tags": ["fruit", "banana", "potassium", "fresh", "organic", "vegan", "healthy"]},
                    {"name": "Premium Peanut Butter", "sub": "Pantry Staples", "tags": ["peanut", "butter", "spread", "protein", "nuts"]},
                    {"name": "Almond Butter (Peanut-Free)", "sub": "Pantry Staples", "tags": ["almond", "butter", "spread", "peanut-free", "healthy", "nuts"]},
                    {"name": "Jain-Friendly Lentil Soup", "sub": "Pantry Staples", "tags": ["soup", "lentil", "jain", "vegetarian", "organic", "healthy"]},
                    {"name": "Vegetarian Pasta Sauce", "sub": "Pantry Staples", "tags": ["pasta", "sauce", "tomato", "vegetarian", "organic"]},
                    {"name": "Grass-Fed Beef Ribeye", "sub": "Meat & Seafood", "tags": ["beef", "steak", "meat", "ribeye", "protein", "paleo"]},
                    {"name": "Fresh Atlantic Salmon Fillet", "sub": "Meat & Seafood", "tags": ["salmon", "fish", "omega3", "protein", "healthy"]},
                    {"name": "Eco-Friendly Organic Green Tea", "sub": "Beverages", "tags": ["tea", "green tea", "organic", "eco-friendly", "antioxidants"]},
                    {"name": "Keto Avocado Oil Mayo", "sub": "Pantry Staples", "tags": ["mayo", "avocado", "keto", "sugar-free", "healthy"]},
                    {"name": "Jain-Safe Basmati Rice", "sub": "Pantry Staples", "tags": ["rice", "basmati", "jain", "grain", "gluten-free"]}
                ],
                "unsplash_images": [
                    "https://images.unsplash.com/photo-1543257580-7269da773bf5?w=500&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1576092768241-dec231879fc3?w=500&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1528825871115-3581a5387919?w=500&auto=format&fit=crop"
                ]
            },
            "Health_and_Household": {
                "subcategories": ["Vitamins & Supplements", "Cleaning Supplies", "Personal Care", "First Aid", "Household Paper"],
                "brands": ["Optimum Nutrition", "Method", "Dettol", "Band-Aid", "Kirkland", "Mrs. Meyer's", "Nature's Bounty", "Seventh Generation"],
                "items": [
                    {"name": "Whey Protein Powder - Chocolate", "sub": "Vitamins & Supplements", "tags": ["protein", "powder", "chocolate", "workout", "muscle-gain", "recovery"]},
                    {"name": "Plant-Based Vegan Protein", "sub": "Vitamins & Supplements", "tags": ["protein", "vegan", "vanilla", "workout", "muscle-gain", "organic"]},
                    {"name": "Organic Multivitamin Gummies", "sub": "Vitamins & Supplements", "tags": ["vitamins", "gummies", "supplement", "healthy", "daily"]},
                    {"name": "Eco-Friendly Dish Soap", "sub": "Cleaning Supplies", "tags": ["dish soap", "cleaning", "biodegradable", "eco-friendly", "green"]},
                    {"name": "All-Purpose Cleaning Spray", "sub": "Cleaning Supplies", "tags": ["cleaning", "spray", "lavender", "disinfectant"]},
                    {"name": "Biodegradable Trash Bags", "sub": "Cleaning Supplies", "tags": ["trash bags", "bags", "eco-friendly", "green", "biodegradable"]},
                    {"name": "First Aid Emergency Kit", "sub": "First Aid", "tags": ["first aid", "safety", "emergency", "bandages", "medical"]},
                    {"name": "Rainy Day Cold Relief Medicine", "sub": "First Aid", "tags": ["medicine", "cold", "flu", "cough", "rainy-day", "fever"]},
                    {"name": "Child Fever Relief Syrup", "sub": "First Aid", "tags": ["fever", "child", "medicine", "pain-relief", "panic", "baby"]},
                    {"name": "Recycled Toilet Paper (12 Rolls)", "sub": "Household Paper", "tags": ["toilet paper", "recycled", "eco-friendly", "green", "household"]}
                ],
                "unsplash_images": [
                    "https://images.unsplash.com/photo-1584017911766-d451b3d0e843?w=500&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1584622650111-993a426fbf0a?w=500&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1550572017-edd951b55104?w=500&auto=format&fit=crop"
                ]
            },
            "Beauty_and_Personal_Care": {
                "subcategories": ["Skin Care", "Hair Care", "Makeup", "Bath & Body", "Oral Care"],
                "brands": ["L'Oreal", "Neutrogena", "Dove", "CeraVe", "Burt's Bees", "Colgate", "Shea Moisture", "EcoTools"],
                "items": [
                    {"name": "Mineral Sunscreen SPF 50", "sub": "Skin Care", "tags": ["sunscreen", "spf", "skincare", "sun protection", "heatwave", "summer"]},
                    {"name": "Hydrating Facial Cleanser", "sub": "Skin Care", "tags": ["cleanser", "skincare", "face wash", "hydrating"]},
                    {"name": "Moisturizing Shea Body Wash", "sub": "Bath & Body", "tags": ["body wash", "moisturizer", "shower", "shea"]},
                    {"name": "Organic Argan Oil Shampoo", "sub": "Hair Care", "tags": ["shampoo", "hair", "argan oil", "organic", "healthy"]},
                    {"name": "Biodegradable Bamboo Toothbrush", "sub": "Oral Care", "tags": ["toothbrush", "bamboo", "eco-friendly", "green", "oral-care"]},
                    {"name": "Fluoride-Free Charcoal Toothpaste", "sub": "Oral Care", "tags": ["toothpaste", "charcoal", "oral-care", "fresh"]},
                    {"name": "Eco-Friendly Makeup Sponge Set", "sub": "Makeup", "tags": ["makeup", "sponge", "eco-friendly", "green", "beauty"]}
                ],
                "unsplash_images": [
                    "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=500&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1526947425960-945c6e72858f?w=500&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1608248597481-496100c80836?w=500&auto=format&fit=crop"
                ]
            },
            "Home_and_Kitchen": {
                "subcategories": ["Cookware", "Small Appliances", "Bedding", "Bath", "Furniture", "Home Decor"],
                "brands": ["T-fal", "Instant Pot", "Keurig", "Cuisinart", "IKEA", "Philips", "Dyson", "Zinus"],
                "items": [
                    {"name": "Non-Stick Frying Pan (10-inch)", "sub": "Cookware", "tags": ["pan", "frying pan", "cookware", "kitchen"]},
                    {"name": "Stainless Steel Cookware Set (10pc)", "sub": "Cookware", "tags": ["cookware", "pots", "pans", "stainless steel", "kitchen", "budget-premium"]},
                    {"name": "Value Aluminum Cookware Set (8pc)", "sub": "Cookware", "tags": ["cookware", "pots", "pans", "budget-cheap", "kitchen"]},
                    {"name": "Multicooker 7-in-1 Pressure Cooker", "sub": "Small Appliances", "tags": ["pressure cooker", "multicooker", "appliance", "kitchen", "instant"]},
                    {"name": "Single Serve Coffee Maker", "sub": "Small Appliances", "tags": ["coffee maker", "coffee", "brewer", "appliance", "kitchen"]},
                    {"name": "Organic Cotton Queen Sheet Set", "sub": "Bedding", "tags": ["sheets", "cotton", "bedding", "organic", "eco-friendly"]},
                    {"name": "Sleek LED Study Desk Lamp", "sub": "Home Decor", "tags": ["lamp", "light", "desk lamp", "led", "study"]},
                    {"name": "Energy-Efficient Space Room Heater", "sub": "Small Appliances", "tags": ["heater", "room heater", "warmth", "cold-weather", "winter"]},
                    {"name": "Heavy-Duty Emergency Flashlight", "sub": "Small Appliances", "tags": ["flashlight", "emergency", "power-outage", "light", "panic"]},
                    {"name": "Hostel Party String Lights", "sub": "Home Decor", "tags": ["lights", "decorations", "party", "hostel-party", "cozy"]}
                ],
                "unsplash_images": [
                    "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=500&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1583847268964-b28dc8f51f92?w=500&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1513694203232-719a280e022f?w=500&auto=format&fit=crop"
                ]
            },
            "Pet_Supplies": {
                "subcategories": ["Dog Supplies", "Cat Supplies", "Fish & Aquatic", "Bird Supplies", "Small Animal"],
                "brands": ["Purina", "Blue Buffalo", "Royal Canin", "Friskies", "Greenies", "Kong", "EcoPet"],
                "items": [
                    {"name": "Grain-Free Premium Dog Food", "sub": "Dog Supplies", "tags": ["dog food", "dry food", "chicken", "pet food", "grain-free", "healthy"]},
                    {"name": "Salmon Recipe Dry Cat Food", "sub": "Cat Supplies", "tags": ["cat food", "dry food", "salmon", "pet food", "healthy"]},
                    {"name": "Organic Biodegradable Cat Litter", "sub": "Cat Supplies", "tags": ["cat litter", "litter", "eco-friendly", "green", "biodegradable"]},
                    {"name": "Durable Rubber Chew Toy (Large)", "sub": "Dog Supplies", "tags": ["dog toy", "toy", "chew", "rubber", "kong"]},
                    {"name": "Nutritional Fish Food Flakes", "sub": "Fish & Aquatic", "tags": ["fish food", "flakes", "aquatic", "pet food"]},
                    {"name": "Eco-Friendly Hemp Pet Bed", "sub": "Dog Supplies", "tags": ["pet bed", "bed", "hemp", "eco-friendly", "green"]}
                ],
                "unsplash_images": [
                    "https://images.unsplash.com/photo-1589924691995-400dc9ecc119?w=500&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1548767797-d8c844163c4c?w=500&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1516734212186-a967f81ad0d7?w=500&auto=format&fit=crop"
                ]
            },
            "Baby_Products": {
                "subcategories": ["Diapering", "Feeding", "Baby Gear", "Nursery", "Toys", "Bath & Skin Care"],
                "brands": ["Pampers", "Huggies", "Gerber", "Johnson's", "Fisher-Price", "Aveeno Baby", "Honest Company"],
                "items": [
                    {"name": "Organic Cotton Diapers (Size 3, 80ct)", "sub": "Diapering", "tags": ["diapers", "organic", "baby", "sensitive", "eco-friendly"]},
                    {"name": "Fragrance-Free Baby Wipes (240ct)", "sub": "Diapering", "tags": ["wipes", "baby", "fragrance-free", "sensitive"]},
                    {"name": "Organic Oatmeal Baby Cereal", "sub": "Feeding", "tags": ["baby food", "cereal", "oatmeal", "organic", "breakfast"]},
                    {"name": "Sensitive Skin Baby Lotion", "sub": "Bath & Skin Care", "tags": ["lotion", "baby", "sensitive", "moisturizer", "aveeno"]},
                    {"name": "Developmental Stacking Rings Toy", "sub": "Toys", "tags": ["toy", "baby toy", "stacking", "educational"]},
                    {"name": "Eco-Friendly Wood Baby Crib", "sub": "Nursery", "tags": ["crib", "nursery", "furniture", "wood", "eco-friendly"]}
                ],
                "unsplash_images": [
                    "https://images.unsplash.com/photo-1515488042361-404e9250afef?w=500&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1522850959076-589a0f443566?w=500&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1596461404969-9ae70f2830c1?w=500&auto=format&fit=crop"
                ]
            },
            "Sports_and_Outdoors": {
                "subcategories": ["Camping & Hiking", "Fitness & Yoga", "Cycling", "Running", "Water Sports", "Athletic Clothing"],
                "brands": ["Coleman", "Columbia", "Gatorade", "CamelBak", "Fitbit", "Under Armour", "Garmin", "Spalding"],
                "items": [
                    {"name": "Waterproof 4-Person Camping Tent", "sub": "Camping & Hiking", "tags": ["tent", "camping", "hiking", "waterproof", "outdoors", "trekking"]},
                    {"name": "Warm Down Sleeping Bag (Sub-Zero)", "sub": "Camping & Hiking", "tags": ["sleeping bag", "camping", "warmth", "cold-weather", "outdoors"]},
                    {"name": "Hydration Pack Water Backpack (2L)", "sub": "Camping & Hiking", "tags": ["hydration", "backpack", "water", "hiking", "strava-cycling", "cycling"]},
                    {"name": "Electrolyte Replacement Powder (Lemon-Lime)", "sub": "Fitness & Yoga", "tags": ["electrolytes", "hydration", "sports-drink", "workout", "heatwave", "running", "strava-running"]},
                    {"name": "Durable Eco-Friendly TPE Yoga Mat", "sub": "Fitness & Yoga", "tags": ["yoga mat", "yoga", "fitness", "eco-friendly", "green"]},
                    {"name": "Ergonomic Hydration Water Bottle (32oz)", "sub": "Fitness & Yoga", "tags": ["water bottle", "hydration", "bottle", "workout", "heatwave"]},
                    {"name": "Windproof Cycling Raincoat Jacket", "sub": "Cycling", "tags": ["raincoat", "jacket", "windproof", "cycling", "heavy-rain", "strava-cycling", "outdoors"]},
                    {"name": "Heavy-Duty Compact Umbrella", "sub": "Camping & Hiking", "tags": ["umbrella", "rain", "heavy-rain", "portable", "outdoors"]},
                    {"name": "Lightweight Running Sneakers", "sub": "Running", "tags": ["shoes", "running", "sneakers", "strava-running", "fitness"]}
                ],
                "unsplash_images": [
                    "https://images.unsplash.com/photo-1504280390367-361c6d9f38f4?w=500&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=500&auto=format&fit=crop",
                    "https://images.unsplash.com/photo-1485968579580-b6d095142e6e?w=500&auto=format&fit=crop"
                ]
            }
        }

        p_id_counter = 1000
        for cat_name, cat_data in categories.items():
            base_items = cat_data["items"]
            subcats = cat_data["subcategories"]
            brands = cat_data["brands"]
            images = cat_data["unsplash_images"]

            for i in range(300):
                p_id = f"prod-{p_id_counter}"
                p_id_counter += 1

                if i < len(base_items):
                    base = base_items[i]
                    title = base["name"]
                    sub = base["sub"]
                    tags = base["tags"].copy()
                else:
                    sub = random.choice(subcats)
                    brand_base = random.choice(brands)
                    
                    adjectives = ["Premium", "Eco", "Pro", "Value", "Essential", "Advanced", "Daily", "Organic", "Comfort"]
                    noun_map = {
                        "Beverages": ["Fruit Juice", "Cold Brew Coffee", "Sparkling Water", "Coconut Water"],
                        "Snacks": ["Granola Bars", "Potato Chips", "Fruit Snacks", "Mixed Nuts", "Rice Cakes"],
                        "Breakfast": ["Granola Cereal", "Pancake Mix", "Maple Syrup", "Instant Porridge"],
                        "Dairy & Cheese": ["Cheddar Cheese", "Butter Rolls", "Cottage Cheese", "Cream Cheese"],
                        "Pantry Staples": ["Olive Oil", "Sea Salt", "Brown Sugar", "Wheat Flour", "Black Pepper"],
                        "Meat & Seafood": ["Chicken Breasts", "Ground Turkey", "Canned Tuna", "Pork Loin"],
                        "Vitamins & Supplements": ["Vitamin C Capsules", "B-Complex tablets", "Omega-3 Softgels", "Calcium Tablets"],
                        "Cleaning Supplies": ["Multisurface Wipes", "Glass Cleaner", "Laundry Detergent", "Fabric Softener"],
                        "Personal Care": ["Deodorant Spray", "Hand Soap", "Body Lotion", "Cotton Swabs"],
                        "First Aid": ["Antiseptic Cream", "Adhesive Bandages", "Burn Gel", "Ice Pack"],
                        "Household Paper": ["Paper Towels", "Facial Tissues", "Napkins"],
                        "Skin Care": ["Moisturizing Cream", "Eye Serum", "Clay Mask", "Lip Balm"],
                        "Hair Care": ["Conditioner", "Hair Gel", "Hair Serum", "Hair Oil"],
                        "Makeup": ["Mascara", "Liquid Eyeliner", "Matte Lipstick", "Foundation Cream"],
                        "Bath & Body": ["Epsom Salt", "Bubble Bath", "Loofah Sponge"],
                        "Oral Care": ["Mouthwash", "Dental Floss", "Oral Gel"],
                        "Cookware": ["Baking Sheet", "Saucepan", "Cutting Board", "Measuring Cups"],
                        "Small Appliances": ["Toaster 2-Slice", "Electric Kettle", "Hand Mixer", "Blender"],
                        "Bedding": ["Memory Foam Pillow", "Fleece Blanket", "Mattress Protector"],
                        "Bath": ["Cotton Bath Towel", "Shower Curtain", "Bath Mat"],
                        "Furniture": ["Ergonomic Desk Chair", "Folding Table", "Wooden Coffee Table"],
                        "Home Decor": ["Scented Candle", "Picture Frame", "Wall Clock"],
                        "Dog Supplies": ["Dog Leash", "Dog Collar", "Dog Treats", "Puppy Shampoo"],
                        "Cat Supplies": ["Cat Treats", "Catnip Toy", "Scratching Post", "Cat Collar"],
                        "Fish & Aquatic": ["Aquarium Filter", "Water Conditioner", "Aquarium Gravel"],
                        "Bird Supplies": ["Bird Seed Mix", "Bird Cage Toy", "Bird Perch"],
                        "Small Animal": ["Hamster Wheel", "Wood Shavings bedding", "Hamster Treats"],
                        "Diapering": ["Diaper Rash Cream", "Diaper Pail Bags"],
                        "Feeding": ["Baby Bottle 3-Pack", "Silicone Bibs", "Baby Spoon Set"],
                        "Baby Gear": ["Stroller organizer", "Baby Carrier Wrap", "Car Seat Mirror"],
                        "Nursery": ["Fitted Crib Sheets", "Baby Swaddle Blanket", "Nursery Organizer"],
                        "Toys": ["Plush Teddy Bear", "Wooden Building Blocks", "Rattle Toy"],
                        "Bath & Skin Care": ["Baby Shampoo", "Baby Bubble Bath", "Baby Oil"],
                        "Camping & Hiking": ["Camping Lantern", "Pocket Knife", "Camping Chair", "Compass"],
                        "Fitness & Yoga": ["Resistance Bands", "Foam Roller", "Dumbbell Set 10lbs"],
                        "Cycling": ["Bike Helmet", "Bike Lock Cable", "Bike Pump", "Bike Lights"],
                        "Running": ["Running Waist Belt", "Reflective Running Vest", "Running Socks"],
                        "Water Sports": ["Swim Goggles", "Waterproof Phone Pouch", "Microfiber Towel"],
                        "Athletic Clothing": ["Moisture-Wicking Shirt", "Running Shorts", "Yoga Leggings"]
                    }
                    
                    nouns = noun_map.get(sub, ["Product"])
                    title = f"{random.choice(adjectives)} {brand_base} {random.choice(nouns)}"
                    
                    tags = [word.lower() for word in title.split()]
                    tags.append(cat_name.lower().replace("_", ""))
                    tags.append(sub.lower().replace(" ", ""))

                brand = random.choice(brands)
                
                price = round(random.uniform(2.99, 149.99) if "Furniture" not in sub else random.uniform(89.99, 399.99), 2)
                average_rating = round(random.uniform(3.8, 4.9), 1)
                rating_count = random.randint(10, 1450)
                description = f"This high-quality {title} by {brand} is perfect for your needs. It offers outstanding reliability, excellent performance, and is highly recommended by customers."
                features = [
                    "Premium quality materials and design",
                    "Highly durable and built to last",
                    "Sourced sustainably and responsibly",
                    "Easy to use and maintain"
                ]
                
                image_url = random.choice(images) + f"&sig={p_id_counter}"
                
                pros = ["Good value for money", "Highly durable", "Modern design", "Excellent customer support"]
                cons = ["Higher price point", "Requires assembly" if "Furniture" in sub else "Slightly bulky", "Limited color options"]
                
                stock = random.randint(0, 45)
                delivery_time = f"{random.choice([1, 2, 3, 5])} days"
                discount = random.choice([0, 5, 10, 15, 20])
                availability = stock > 0
                popularity_score = round(average_rating * (rating_count / 1500) * 10, 2)

                product = {
                    "product_id": p_id,
                    "title": title,
                    "brand": brand,
                    "category": cat_name,
                    "subcategory": sub,
                    "price": price,
                    "average_rating": average_rating,
                    "rating_count": rating_count,
                    "description": description,
                    "features": features,
                    "image_url": image_url,
                    "pros": pros,
                    "cons": cons,
                    "tags": list(set(tags)),
                    "stock": stock,
                    "delivery_time": delivery_time,
                    "discount": discount,
                    "availability": availability,
                    "popularity_score": popularity_score
                }

                self.products.append(product)

        with open(self.products_file, "w") as f:
            json.dump(self.products, f, indent=4)
        print(f"Catalog successfully generated! Total products: {len(self.products)}")

    def save_products(self):
        try:
            with open(self.products_file, "w") as f:
                json.dump(self.products, f, indent=4)
        except Exception as e:
            print(f"Error saving products database: {e}")

    def get_session_profile(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.profiles:
            # Default Profile structure
            self.profiles[session_id] = {
                "first_name": "Adnan",
                "last_name": "Ansari",
                "email": "adnan@example.com",
                "address": "123 Commerce Way, Seattle, WA 98101",
                "age": 28,
                "allergies": ["Peanut allergy"], # default peanut allergy to test filter
                "budget": 250.0,
                "healthy_mode": False,
                "green_mode": False,
                "workout_goals": "Muscle Gain",
                "strava_stats": "Running: 24km this week, Cycling: 45km"
            }
        return self.profiles[session_id]

    def update_session_profile(self, session_id: str, profile: Dict[str, Any]):
        self.profiles[session_id] = profile

    def get_session_cart(self, session_id: str) -> Dict[str, int]:
        if session_id not in self.carts:
            self.carts[session_id] = {}
        return self.carts[session_id]

    def clear_session_cart(self, session_id: str):
        self.carts[session_id] = {}

    def get_session_weather(self, session_id: str) -> str:
        if session_id not in self.weather:
            self.weather[session_id] = "Sunny, 22°C (72°F)"
        return self.weather[session_id]

    def set_session_weather(self, session_id: str, forecast: str):
        self.weather[session_id] = forecast

    def get_session_events(self, session_id: str) -> List[Dict[str, Any]]:
        if session_id not in self.events:
            self.events[session_id] = [
                {"title": "Kid's Birthday Party", "date": "Tomorrow", "type": "party"},
                {"title": "Weekend Camping Trip", "date": "In 5 days", "type": "vacation"}
            ]
        return self.events[session_id]

    def add_session_event(self, session_id: str, event: Dict[str, Any]):
        if session_id not in self.events:
            self.events[session_id] = []
        self.events[session_id].append(event)

    def get_session_inventory(self, session_id: str) -> Dict[str, str]:
        if session_id not in self.inventory:
            self.inventory[session_id] = {
                "Whole Milk": "3 days remaining",
                "Organic Eggs": "1 day remaining (Low!)",
                "Basmati Rice": "14 days remaining",
                "Dog Food": "2 days remaining (Low!)"
            }
        return self.inventory[session_id]

    def update_session_inventory(self, session_id: str, item: str, days_str: str):
        if session_id not in self.inventory:
            self.inventory[session_id] = {}
        self.inventory[session_id][item] = days_str

    def get_session_orders(self, session_id: str) -> List[Dict[str, Any]]:
        if session_id not in self.orders:
            self.orders[session_id] = []
        return self.orders[session_id]

    def add_session_order(self, session_id: str, order: Dict[str, Any]):
        if session_id not in self.orders:
            self.orders[session_id] = []
        self.orders[session_id].append(order)

db = DatabaseManager()
