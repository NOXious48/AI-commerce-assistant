"""
JWT Verifier — Cognito Token Verification
==========================================
Downloads JWKS from Cognito and verifies JWT access tokens.
Provides a FastAPI dependency for extracting the current user.
"""

import os
import time
import logging
from typing import Dict, Any, Optional

import httpx
from jose import jwt, JWTError, jwk
from jose.utils import base64url_decode
from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


class JWTVerifier:
    """Verifies Cognito JWT tokens using JWKS."""

    def __init__(self):
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.user_pool_id = os.environ["COGNITO_USER_POOL_ID"]
        self.client_id = os.environ["COGNITO_CLIENT_ID"]

        self.issuer = f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"
        self.jwks_url = f"{self.issuer}/.well-known/jwks.json"

        self._jwks: Optional[Dict] = None
        self._jwks_fetched_at: float = 0
        self._jwks_ttl: int = 86400  # Cache JWKS for 24 hours

    def _get_jwks(self) -> Dict:
        """Download and cache JWKS from Cognito."""
        now = time.time()
        if self._jwks and (now - self._jwks_fetched_at) < self._jwks_ttl:
            return self._jwks

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(self.jwks_url)
                response.raise_for_status()
                self._jwks = response.json()
                self._jwks_fetched_at = now
                logger.info("JWKS fetched successfully from Cognito")
                return self._jwks
        except Exception as e:
            logger.exception("Failed to fetch JWKS")
            if self._jwks:
                return self._jwks  # Use stale cache if available
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable.",
            )

    def _get_signing_key(self, token: str) -> Dict:
        """Find the correct signing key for a token from JWKS."""
        jwks = self._get_jwks()
        try:
            headers = jwt.get_unverified_headers(token)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format.",
            )

        kid = headers.get("kid")
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing key ID.",
            )

        for key in jwks.get("keys", []):
            if key["kid"] == kid:
                return key

        # Key not found — JWKS might be stale, force refresh
        self._jwks = None
        jwks = self._get_jwks()
        for key in jwks.get("keys", []):
            if key["kid"] == kid:
                return key

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: key not found.",
        )

    def verify_access_token(self, token: str) -> Dict[str, Any]:
        """Verify a Cognito access token and return its claims."""
        signing_key = self._get_signing_key(token)

        try:
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self.issuer,
                options={
                    "verify_aud": False,  # Access tokens use client_id differently
                    "verify_iss": True,
                    "verify_exp": True,
                },
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired.",
            )
        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token.",
            )

        # Verify this is an access token
        if claims.get("token_use") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type.",
            )

        # Verify issuer matches
        if claims.get("iss") != self.issuer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token issuer.",
            )

        return claims

    def decode_id_token(self, token: str) -> Dict[str, Any]:
        """Decode an ID token (lighter verification, used for user info)."""
        signing_key = self._get_signing_key(token)

        try:
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self.issuer,
                options={
                    "verify_aud": True,  # ID tokens include aud=client_id
                    "verify_iss": True,
                    "verify_exp": True,
                },
            )
        except JWTError as e:
            logger.warning(f"ID token decode failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid ID token.",
            )

        return claims


# Module-level singleton
jwt_verifier = JWTVerifier()


# ---------------------------------------------------------------------------
# FastAPI Dependency
# ---------------------------------------------------------------------------

async def get_current_user(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency: extracts and verifies the JWT from the
    Authorization header. Returns user claims.

    Usage:
        @app.get("/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            user_id = user["sub"]
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header. Use: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    claims = jwt_verifier.verify_access_token(token)

    return {
        "sub": claims["sub"],
        "email": claims.get("email", ""),
        "username": claims.get("username", claims.get("email", "")),
    }
