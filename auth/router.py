"""
Auth Router — Authentication API Endpoints
============================================
Handles signup, login, email verification, password reset,
and logout. Uses HttpOnly cookies for refresh tokens.
"""

import os
import logging
from typing import Optional

from fastapi import APIRouter, Request, Response, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, Field

from auth.cognito_service import cognito_service
from auth.jwt_verifier import get_current_user
from auth.rate_limiter import rate_limiter, get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Cookie settings
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"  # True in production w/ HTTPS
COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=100)

class ConfirmRequest(BaseModel):
    email: str
    code: str = Field(..., min_length=1, max_length=10)

class LoginRequest(BaseModel):
    email: str
    password: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str = Field(..., min_length=8, max_length=128)

class ResendCodeRequest(BaseModel):
    email: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(req: SignupRequest, request: Request):
    """Register a new user account."""
    ip = get_client_ip(request)
    rate_limiter.check(f"signup:{ip}", max_requests=3, window_seconds=60)

    # Import here to avoid circular imports
    from db.dynamo_service import dynamo_service

    result = cognito_service.signup(req.email, req.password, req.full_name)

    # Create user record in DynamoDB
    try:
        dynamo_service.create_user(
            user_id=result["user_sub"],
            email=req.email,
            full_name=req.full_name,
        )
    except Exception as e:
        logger.exception("Failed to create DynamoDB user record")
        # Don't fail the signup — Cognito user was created successfully

    return result


@router.post("/confirm")
async def confirm_signup(req: ConfirmRequest, request: Request):
    """Verify email with OTP code."""
    ip = get_client_ip(request)
    rate_limiter.check(f"confirm:{ip}", max_requests=5, window_seconds=60)

    return cognito_service.confirm_signup(req.email, req.code)


@router.post("/login")
async def login(req: LoginRequest, request: Request, response: Response):
    """
    Login and receive tokens.
    - access_token + id_token returned in response body (stored in JS memory)
    - refresh_token set as HttpOnly cookie (not accessible to JS)
    """
    ip = get_client_ip(request)
    rate_limiter.check(f"login:{ip}", max_requests=5, window_seconds=60)

    tokens = cognito_service.login(req.email, req.password)

    # Set refresh token as HttpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        max_age=COOKIE_MAX_AGE,
        path="/api/auth",  # Only sent to auth endpoints
    )

    # Extract 'sub' (User ID) from the ID token to use for SECRET_HASH during refresh
    import json
    import base64
    payload = tokens["id_token"].split('.')[1]
    # Add padding if necessary
    payload += '=' * (-len(payload) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(payload).decode('utf-8'))
    user_sub = decoded.get("sub", req.email)

    # Store user_sub for SECRET_HASH computation on refresh
    response.set_cookie(
        key="cognito_username",
        value=user_sub,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        max_age=COOKIE_MAX_AGE,
        path="/api/auth",
    )

    # Return access + id tokens in body (frontend stores in memory)
    return {
        "access_token": tokens["access_token"],
        "id_token": tokens["id_token"],
        "expires_in": tokens["expires_in"],
        "token_type": tokens["token_type"],
    }


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    """
    Silent token refresh using the HttpOnly cookie.
    Returns new access + id tokens. Updates the refresh token cookie.
    """
    refresh_token = request.cookies.get("refresh_token")
    username = request.cookies.get("cognito_username", "")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token found. Please log in.",
        )

    tokens = cognito_service.refresh_tokens(refresh_token, username=username)

    # Cognito may or may not return a new refresh token on refresh.
    # If it does, update the cookie. Otherwise keep the existing one.
    new_refresh = tokens.get("refresh_token")
    if new_refresh:
        response.set_cookie(
            key="refresh_token",
            value=new_refresh,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="strict",
            max_age=COOKIE_MAX_AGE,
            path="/api/auth",
        )

    return {
        "access_token": tokens["access_token"],
        "id_token": tokens["id_token"],
        "expires_in": tokens["expires_in"],
        "token_type": tokens["token_type"],
    }


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, request: Request):
    """Send a password reset code to the user's email."""
    ip = get_client_ip(request)
    rate_limiter.check(f"forgot:{ip}", max_requests=3, window_seconds=60)

    return cognito_service.forgot_password(req.email)


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, request: Request):
    """Reset password using the emailed code."""
    ip = get_client_ip(request)
    rate_limiter.check(f"reset:{ip}", max_requests=5, window_seconds=60)

    return cognito_service.confirm_forgot_password(req.email, req.code, req.new_password)


@router.post("/resend-code")
async def resend_code(req: ResendCodeRequest, request: Request):
    """Resend email verification code."""
    ip = get_client_ip(request)
    rate_limiter.check(f"resend:{ip}", max_requests=3, window_seconds=60)

    return cognito_service.resend_confirmation_code(req.email)


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current authenticated user info from JWT."""
    from db.dynamo_service import dynamo_service

    # Fetch full profile from DynamoDB
    profile = dynamo_service.get_user(user["sub"])
    if profile:
        return {
            "sub": user["sub"],
            "email": profile.get("email", user.get("email", "")),
            "full_name": profile.get("full_name", ""),
            "created_at": profile.get("created_at", ""),
            "preferences": profile.get("preferences", {}),
        }

    return {
        "sub": user["sub"],
        "email": user.get("email", user.get("username", "")),
        "full_name": "",
        "created_at": "",
        "preferences": {},
    }


@router.post("/logout")
async def logout(request: Request, response: Response, user: dict = Depends(get_current_user)):
    """Logout: invalidate all refresh tokens and clear cookie."""
    # Get access token from header to call GlobalSignOut
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.split(" ")[-1] if " " in auth_header else ""

    if token:
        cognito_service.global_sign_out(token)

    # Clear the refresh token cookie
    response.delete_cookie(
        key="refresh_token",
        path="/api/auth",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
    )
    response.delete_cookie(
        key="cognito_username",
        path="/api/auth",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
    )

    return {"message": "Successfully logged out."}
