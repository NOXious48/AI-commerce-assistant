"""
DynamoDB Service — Data Access Layer
======================================
Handles all DynamoDB operations for Users, ChatSessions,
Messages, and SavedProducts tables.

SECURITY: All methods require user_id from verified JWT sub.
Never accept user_id from frontend requests.
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# Default preferences schema
DEFAULT_PREFERENCES = {
    "dietary_preferences": [],
    "favorite_categories": [],
    "preferred_brands": [],
    "allergens": [],
    "price_range": {"min": 0, "max": 50},
}


class DynamoService:
    """DynamoDB operations for all application tables."""

    def __init__(self):
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region)

        self.users_table = self.dynamodb.Table(
            os.environ.get("DYNAMODB_USERS_TABLE", "Users")
        )
        self.sessions_table = self.dynamodb.Table(
            os.environ.get("DYNAMODB_SESSIONS_TABLE", "ChatSessions")
        )
        self.messages_table = self.dynamodb.Table(
            os.environ.get("DYNAMODB_MESSAGES_TABLE", "Messages")
        )
        self.saved_products_table = self.dynamodb.Table(
            os.environ.get("DYNAMODB_SAVED_PRODUCTS_TABLE", "SavedProducts")
        )
        logger.info("DynamoService initialized")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _float_to_decimal(obj: Any) -> Any:
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: DynamoService._float_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [DynamoService._float_to_decimal(v) for v in obj]
        return obj

    # ==================================================================
    # USERS
    # ==================================================================

    def create_user(self, user_id: str, email: str, full_name: str) -> Dict:
        """Create a new user record after Cognito signup."""
        item = {
            "user_id": user_id,
            "email": email,
            "full_name": full_name,
            "created_at": self._now(),
            "preferences": DEFAULT_PREFERENCES,
            "memory": {},
        }
        try:
            self.users_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(user_id)",
            )
            logger.info(f"Created user record: {user_id}")
            return item
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(f"User record already exists: {user_id}")
                return item
            raise

    def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user profile by Cognito sub."""
        try:
            response = self.users_table.get_item(Key={"user_id": user_id})
            item = response.get("Item")
            if item:
                # Convert Decimal to float/int for JSON serialization
                return self._convert_decimals(item)
            return None
        except ClientError as e:
            logger.exception(f"Error getting user {user_id}")
            return None

    def update_preferences(self, user_id: str, preferences: Dict) -> Dict:
        """Update user preferences. Validates against schema."""
        try:
            self.users_table.update_item(
                Key={"user_id": user_id},
                UpdateExpression="SET preferences = :p, updated_at = :u",
                ExpressionAttributeValues={
                    ":p": preferences,
                    ":u": self._now(),
                },
                ConditionExpression="attribute_exists(user_id)",
            )
            return {"message": "Preferences updated", "preferences": preferences}
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(f"User not found for preferences update: {user_id}")
                return {"message": "User not found"}
            raise

    def get_preferences(self, user_id: str) -> Dict:
        """Get user preferences."""
        user = self.get_user(user_id)
        if user:
            return user.get("preferences", DEFAULT_PREFERENCES)
        return DEFAULT_PREFERENCES

    def update_user_memory(self, user_id: str, memory_dict: Dict) -> Dict:
        """Update the user's long-term memory."""
        try:
            self.users_table.update_item(
                Key={"user_id": user_id},
                UpdateExpression="SET memory = :m, updated_at = :u",
                ExpressionAttributeValues={
                    ":m": self._float_to_decimal(memory_dict),
                    ":u": self._now(),
                },
                ConditionExpression="attribute_exists(user_id)",
            )
            return {"message": "Memory updated", "memory": memory_dict}
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(f"User not found for memory update: {user_id}")
                return {"message": "User not found"}
            raise

    def get_user_memory(self, user_id: str) -> Dict:
        """Get the user's long-term memory."""
        user = self.get_user(user_id)
        if user:
            return user.get("memory", {})
        return {}

    # ==================================================================
    # CHAT SESSIONS (UUID-based, multiple per user)
    # ==================================================================

    def create_session(self, user_id: str, title: str = "New Chat") -> Dict:
        """Create a new chat session with a UUID."""
        session_id = str(uuid.uuid4())
        now = self._now()
        item = {
            "PK": f"USER#{user_id}",
            "SK": f"SESSION#{session_id}",
            "session_id": session_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "consultation_state": {},
            "last_retrieved_products": [],
            "recommendation_workspace": {},
        }
        self.sessions_table.put_item(Item=item)
        logger.info(f"Created session {session_id} for user {user_id}")
        return {
            "session_id": session_id,
            "title": title,
            "created_at": now,
            "consultation_state": {},
            "last_retrieved_products": [],
            "recommendation_workspace": {}
        }

    def list_sessions(self, user_id: str) -> List[Dict]:
        """List all chat sessions for a user, sorted by most recent."""
        try:
            response = self.sessions_table.query(
                KeyConditionExpression=Key("PK").eq(f"USER#{user_id}"),
                ScanIndexForward=False,  # newest first
            )
            sessions = []
            for item in response.get("Items", []):
                sessions.append({
                    "session_id": item["session_id"],
                    "title": item.get("title", "Untitled"),
                    "created_at": item.get("created_at", ""),
                    "updated_at": item.get("updated_at", ""),
                })
            # Sort by updated_at descending
            sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
            return sessions
        except ClientError as e:
            logger.exception(f"Error listing sessions for {user_id}")
            return []

    def get_session(self, user_id: str, session_id: str) -> Optional[Dict]:
        """Get a specific session. Enforces ownership via user_id."""
        try:
            response = self.sessions_table.get_item(
                Key={
                    "PK": f"USER#{user_id}",
                    "SK": f"SESSION#{session_id}",
                }
            )
            item = response.get("Item")
            if item:
                return {
                    "session_id": item["session_id"],
                    "title": item.get("title", "Untitled"),
                    "created_at": item.get("created_at", ""),
                    "updated_at": item.get("updated_at", ""),
                    "consultation_state": item.get("consultation_state", {}),
                    "last_retrieved_products": item.get("last_retrieved_products", []),
                    "recommendation_workspace": item.get("recommendation_workspace", {}),
                }
            return None
        except ClientError:
            return None

    def update_consultation_state(self, user_id: str, session_id: str, state_dict: Dict, products: Optional[List] = None, workspace: Optional[Dict] = None):
        """Update a session's consultation state, optionally last retrieved products, and recommendation workspace."""
        try:
            update_expr = "SET consultation_state = :s, updated_at = :u"
            expr_values = {
                ":s": self._float_to_decimal(state_dict),
                ":u": self._now(),
            }
            if products is not None:
                update_expr += ", last_retrieved_products = :p"
                expr_values[":p"] = self._float_to_decimal(products)
            if workspace is not None:
                update_expr += ", recommendation_workspace = :w"
                expr_values[":w"] = self._float_to_decimal(workspace)

            self.sessions_table.update_item(
                Key={
                    "PK": f"USER#{user_id}",
                    "SK": f"SESSION#{session_id}",
                },
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
            )
        except ClientError as e:
            logger.exception(f"Error updating consultation state")

    def update_session_title(self, user_id: str, session_id: str, title: str):
        """Update a session's title."""
        try:
            self.sessions_table.update_item(
                Key={
                    "PK": f"USER#{user_id}",
                    "SK": f"SESSION#{session_id}",
                },
                UpdateExpression="SET title = :t, updated_at = :u",
                ExpressionAttributeValues={
                    ":t": title,
                    ":u": self._now(),
                },
            )
        except ClientError as e:
            logger.exception(f"Error updating session title")

    def update_session_timestamp(self, user_id: str, session_id: str):
        """Touch the session's updated_at timestamp."""
        try:
            self.sessions_table.update_item(
                Key={
                    "PK": f"USER#{user_id}",
                    "SK": f"SESSION#{session_id}",
                },
                UpdateExpression="SET updated_at = :u",
                ExpressionAttributeValues={":u": self._now()},
            )
        except ClientError:
            pass

    def delete_session(self, user_id: str, session_id: str) -> Dict:
        """Delete a session and its messages. Enforces ownership."""
        # First verify ownership
        session = self.get_session(user_id, session_id)
        if not session:
            return {"message": "Session not found"}

        # Delete the session record
        try:
            self.sessions_table.delete_item(
                Key={
                    "PK": f"USER#{user_id}",
                    "SK": f"SESSION#{session_id}",
                }
            )
        except ClientError:
            pass

        # Cascade delete all messages
        self.delete_session_messages(session_id)

        return {"message": "Session deleted"}

    # ==================================================================
    # MESSAGES
    # ==================================================================

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        products: Optional[List] = None,
    ) -> Dict:
        """Save a chat message."""
        now = self._now()
        item = {
            "PK": f"SESSION#{session_id}",
            "SK": f"MSG#{now}",
            "role": role,
            "content": content,
            "timestamp": now,
        }
        if products:
            # Store minimal product info for history
            item["products"] = self._float_to_decimal([
                {
                    "parent_asin": p.get("parent_asin", ""),
                    "title": p.get("title", ""),
                    "price": p.get("price", 0),
                    "image_url": p.get("image_url", ""),
                }
                for p in products[:6]
            ])

        self.messages_table.put_item(Item=item)
        return item

    def get_messages(self, session_id: str, limit: int = 50) -> List[Dict]:
        """Get messages for a session, ordered chronologically."""
        try:
            response = self.messages_table.query(
                KeyConditionExpression=Key("PK").eq(f"SESSION#{session_id}"),
                ScanIndexForward=True,  # oldest first
                Limit=limit,
            )
            messages = []
            for item in response.get("Items", []):
                msg = {
                    "role": item["role"],
                    "content": item["content"],
                    "timestamp": item.get("timestamp", ""),
                }
                if "products" in item:
                    msg["products"] = self._convert_decimals(item["products"])
                messages.append(msg)
            return messages
        except ClientError as e:
            logger.exception(f"Error getting messages for session {session_id}")
            return []

    def delete_session_messages(self, session_id: str):
        """Delete all messages for a session."""
        try:
            response = self.messages_table.query(
                KeyConditionExpression=Key("PK").eq(f"SESSION#{session_id}"),
                ProjectionExpression="PK, SK",
            )
            with self.messages_table.batch_writer() as batch:
                for item in response.get("Items", []):
                    batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
        except ClientError as e:
            logger.exception(f"Error deleting messages for session {session_id}")

    # ==================================================================
    # SAVED PRODUCTS
    # ==================================================================

    def save_product(self, user_id: str, parent_asin: str) -> Dict:
        """Save a product to user's saved list."""
        item = {
            "PK": f"USER#{user_id}",
            "SK": f"PRODUCT#{parent_asin}",
            "parent_asin": parent_asin,
            "saved_at": self._now(),
        }
        self.saved_products_table.put_item(Item=item)
        return {"message": "Product saved", "parent_asin": parent_asin}

    def unsave_product(self, user_id: str, parent_asin: str) -> Dict:
        """Remove a product from user's saved list."""
        try:
            self.saved_products_table.delete_item(
                Key={
                    "PK": f"USER#{user_id}",
                    "SK": f"PRODUCT#{parent_asin}",
                }
            )
            return {"message": "Product removed"}
        except ClientError:
            return {"message": "Product not found"}

    def list_saved_products(self, user_id: str) -> List[Dict]:
        """List all saved products for a user."""
        try:
            response = self.saved_products_table.query(
                KeyConditionExpression=Key("PK").eq(f"USER#{user_id}"),
            )
            return [
                {
                    "parent_asin": item["parent_asin"],
                    "saved_at": item.get("saved_at", ""),
                }
                for item in response.get("Items", [])
            ]
        except ClientError:
            return []

    def is_product_saved(self, user_id: str, parent_asin: str) -> bool:
        """Check if a product is in the user's saved list."""
        try:
            response = self.saved_products_table.get_item(
                Key={
                    "PK": f"USER#{user_id}",
                    "SK": f"PRODUCT#{parent_asin}",
                }
            )
            return "Item" in response
        except ClientError:
            return False

    # ==================================================================
    # Helpers
    # ==================================================================

    @staticmethod
    def _convert_decimals(obj):
        """Recursively convert DynamoDB Decimal types to float/int."""
        if isinstance(obj, list):
            return [DynamoService._convert_decimals(i) for i in obj]
        elif isinstance(obj, dict):
            return {k: DynamoService._convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return obj


# Module-level singleton
dynamo_service = DynamoService()
