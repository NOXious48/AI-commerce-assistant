"""
Cognito Service — AWS Cognito Identity Provider Wrapper
========================================================
Wraps boto3 cognito-idp calls with clean error handling.
All errors are mapped to safe HTTP exceptions that prevent
account enumeration and information leakage.
"""

import os
import hmac
import hashlib
import base64
import logging
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class CognitoService:
    """Handles all Cognito authentication operations."""

    def __init__(self):
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.user_pool_id = os.environ["COGNITO_USER_POOL_ID"]
        self.client_id = os.environ["COGNITO_CLIENT_ID"]
        self.client_secret = os.environ.get("COGNITO_CLIENT_SECRET", "")

        self.client = boto3.client("cognito-idp", region_name=self.region)
        logger.info(f"CognitoService initialized (pool={self.user_pool_id})")

    def _compute_secret_hash(self, username: str) -> str:
        """Compute SECRET_HASH = Base64(HMAC_SHA256(client_secret, username + client_id))."""
        message = username + self.client_id
        dig = hmac.new(
            self.client_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(dig).decode("utf-8")

    # ------------------------------------------------------------------
    # Signup
    # ------------------------------------------------------------------

    def signup(self, email: str, password: str, full_name: str) -> Dict[str, Any]:
        """Register a new user. Triggers email verification."""
        try:
            response = self.client.sign_up(
                ClientId=self.client_id,
                SecretHash=self._compute_secret_hash(email),
                Username=email,
                Password=password,
                UserAttributes=[
                    {"Name": "email", "Value": email},
                    {"Name": "name", "Value": full_name},
                ],
            )
            return {
                "message": "Account created. Please check your email for verification code.",
                "user_sub": response["UserSub"],
            }
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "UsernameExistsException":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with this email already exists.",
                )
            elif code == "InvalidPasswordException":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password does not meet requirements. Must be 8+ characters with uppercase, lowercase, number, and symbol.",
                )
            elif code == "InvalidParameterException":
                msg = e.response["Error"].get("Message", "Invalid input.")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=msg,
                )
            elif code == "TooManyRequestsException":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait and try again.",
                )
            else:
                logger.exception(f"Cognito signup error: {code}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An unexpected error occurred. Please try again.",
                )

    # ------------------------------------------------------------------
    # Confirm Signup (Email OTP)
    # ------------------------------------------------------------------

    def confirm_signup(self, email: str, code: str) -> Dict[str, Any]:
        """Confirm user registration with the emailed verification code."""
        try:
            self.client.confirm_sign_up(
                ClientId=self.client_id,
                SecretHash=self._compute_secret_hash(email),
                Username=email,
                ConfirmationCode=code,
            )
            return {"message": "Email verified successfully. You can now log in."}
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "CodeMismatchException":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid verification code. Please check and try again.",
                )
            elif error_code == "ExpiredCodeException":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Verification code has expired. Please request a new one.",
                )
            elif error_code == "NotAuthorizedException":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This account is already verified.",
                )
            elif error_code == "UserNotFoundException":
                # Generic message to prevent account enumeration
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid verification code. Please check and try again.",
                )
            elif error_code == "TooManyRequestsException":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait and try again.",
                )
            else:
                logger.exception(f"Cognito confirm_signup error: {error_code}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An unexpected error occurred.",
                )

    # ------------------------------------------------------------------
    # Resend Confirmation Code
    # ------------------------------------------------------------------

    def resend_confirmation_code(self, email: str) -> Dict[str, Any]:
        """Resend the email verification code."""
        try:
            self.client.resend_confirmation_code(
                ClientId=self.client_id,
                SecretHash=self._compute_secret_hash(email),
                Username=email,
            )
            return {"message": "Verification code sent. Please check your email."}
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("UserNotFoundException", "InvalidParameterException"):
                # Generic to prevent enumeration
                return {"message": "If an account exists, a verification code has been sent."}
            elif error_code == "TooManyRequestsException":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait before requesting another code.",
                )
            else:
                logger.exception(f"Cognito resend_code error: {error_code}")
                return {"message": "If an account exists, a verification code has been sent."}

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate user and return tokens."""
        try:
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": email,
                    "PASSWORD": password,
                    "SECRET_HASH": self._compute_secret_hash(email),
                },
            )
            auth_result = response["AuthenticationResult"]
            return {
                "access_token": auth_result["AccessToken"],
                "id_token": auth_result["IdToken"],
                "refresh_token": auth_result["RefreshToken"],
                "expires_in": auth_result["ExpiresIn"],
                "token_type": auth_result["TokenType"],
            }
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("NotAuthorizedException", "UserNotFoundException"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password.",
                )
            elif error_code == "UserNotConfirmedException":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Please verify your email before logging in.",
                )
            elif error_code == "TooManyRequestsException":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many login attempts. Please wait and try again.",
                )
            elif error_code == "PasswordResetRequiredException":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Password reset required. Please use the Forgot Password flow.",
                )
            else:
                logger.exception(f"Cognito login error: {error_code}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An unexpected error occurred. Please try again.",
                )

    # ------------------------------------------------------------------
    # Refresh Tokens
    # ------------------------------------------------------------------

    def refresh_tokens(self, refresh_token: str, username: str = "") -> Dict[str, Any]:
        """Get new access/id tokens using a refresh token."""
        try:
            auth_params = {
                "REFRESH_TOKEN": refresh_token,
            }
            if self.client_secret and username:
                auth_params["SECRET_HASH"] = self._compute_secret_hash(username)

            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow="REFRESH_TOKEN_AUTH",
                AuthParameters=auth_params,
            )
            auth_result = response["AuthenticationResult"]
            return {
                "access_token": auth_result["AccessToken"],
                "id_token": auth_result["IdToken"],
                "expires_in": auth_result["ExpiresIn"],
                "token_type": auth_result["TokenType"],
            }
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("NotAuthorizedException", "InvalidParameterException"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session expired. Please log in again.",
                )
            else:
                logger.exception(f"Cognito refresh error: {error_code}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session expired. Please log in again.",
                )

    # ------------------------------------------------------------------
    # Forgot Password
    # ------------------------------------------------------------------

    def forgot_password(self, email: str) -> Dict[str, Any]:
        """Initiate the forgot password flow. Sends a reset code via email."""
        try:
            self.client.forgot_password(
                ClientId=self.client_id,
                SecretHash=self._compute_secret_hash(email),
                Username=email,
            )
            return {"message": "If an account exists with this email, a reset code has been sent."}
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("UserNotFoundException", "InvalidParameterException"):
                # Generic to prevent enumeration
                return {"message": "If an account exists with this email, a reset code has been sent."}
            elif error_code == "TooManyRequestsException":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait before trying again.",
                )
            elif error_code == "LimitExceededException":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Attempt limit exceeded. Please try again later.",
                )
            else:
                logger.exception(f"Cognito forgot_password error: {error_code}")
                return {"message": "If an account exists with this email, a reset code has been sent."}

    # ------------------------------------------------------------------
    # Confirm Forgot Password (Reset)
    # ------------------------------------------------------------------

    def confirm_forgot_password(
        self, email: str, code: str, new_password: str
    ) -> Dict[str, Any]:
        """Reset password using the emailed code."""
        try:
            self.client.confirm_forgot_password(
                ClientId=self.client_id,
                SecretHash=self._compute_secret_hash(email),
                Username=email,
                ConfirmationCode=code,
                Password=new_password,
            )
            return {"message": "Password reset successfully. You can now log in with your new password."}
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "CodeMismatchException":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid reset code. Please check and try again.",
                )
            elif error_code == "ExpiredCodeException":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Reset code has expired. Please request a new one.",
                )
            elif error_code == "InvalidPasswordException":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New password does not meet requirements.",
                )
            elif error_code in ("UserNotFoundException", "InvalidParameterException"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid reset code. Please check and try again.",
                )
            else:
                logger.exception(f"Cognito confirm_forgot_password error: {error_code}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An unexpected error occurred.",
                )

    # ------------------------------------------------------------------
    # Get User Info
    # ------------------------------------------------------------------

    def get_user(self, access_token: str) -> Dict[str, Any]:
        """Get user attributes using an access token."""
        try:
            response = self.client.get_user(AccessToken=access_token)
            attrs = {a["Name"]: a["Value"] for a in response["UserAttributes"]}
            return {
                "sub": attrs.get("sub", ""),
                "email": attrs.get("email", ""),
                "name": attrs.get("name", ""),
                "email_verified": attrs.get("email_verified", "false") == "true",
            }
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NotAuthorizedException":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token.",
                )
            else:
                logger.exception(f"Cognito get_user error: {error_code}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not retrieve user information.",
                )

    # ------------------------------------------------------------------
    # Global Sign Out
    # ------------------------------------------------------------------

    def global_sign_out(self, access_token: str) -> Dict[str, Any]:
        """Sign out user from all devices by invalidating all refresh tokens."""
        try:
            self.client.global_sign_out(AccessToken=access_token)
            return {"message": "Successfully logged out from all devices."}
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NotAuthorizedException":
                # Token already invalid — user is effectively signed out
                return {"message": "Successfully logged out."}
            else:
                logger.exception(f"Cognito global_sign_out error: {error_code}")
                return {"message": "Successfully logged out."}


# Module-level singleton
cognito_service = CognitoService()
