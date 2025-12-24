"""
TON ID OAuth 2.0 Integration
https://id.ton.org - Official TON identity provider

Enables:
- Wallet-to-Telegram linking
- KOL verification
- Social proof (Twitter verification status)
- Badge verification for premium features
"""

import os
import secrets
import hashlib
import base64
import httpx
from dataclasses import dataclass
from typing import Optional, Dict, Any
from urllib.parse import urlencode
import jwt
from jwt import PyJWKClient

# Configuration
TONID_ISSUER = "https://id.ton.org"
TONID_AUTH_URL = "https://id.ton.org/v1/oauth2/signin"
TONID_TOKEN_URL = "https://id.ton.org/v1/oauth2/token"
TONID_USERINFO_URL = "https://id.ton.org/v1/oauth2/userinfo"
TONID_WALLET_URL = "https://id.ton.org/v1/wallet"
TONID_JWKS_URL = "https://id.ton.org/.well-known/jwks.json"

# Get from environment (request from @boldov on Telegram)
TONID_CLIENT_ID = os.getenv("TONID_CLIENT_ID", "")
TONID_REDIRECT_URI = os.getenv("TONID_REDIRECT_URI", "https://notaryton.com/auth/tonid/callback")


@dataclass
class TONIDUser:
    """Verified user from TON ID"""
    sub: str  # Unique TON ID user identifier
    telegram_id: Optional[int] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    wallet_address: Optional[str] = None
    wallet_raw: Optional[str] = None
    twitter_verified: bool = False
    youtube_verified: bool = False


@dataclass
class PKCEChallenge:
    """PKCE values for OAuth flow"""
    code_verifier: str
    code_challenge: str
    state: str


def generate_pkce() -> PKCEChallenge:
    """Generate PKCE code verifier and challenge for OAuth flow"""
    # Generate random code verifier (43-128 chars)
    code_verifier = secrets.token_urlsafe(32)

    # Generate code challenge = base64url(SHA256(code_verifier))
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(16)

    return PKCEChallenge(
        code_verifier=code_verifier,
        code_challenge=code_challenge,
        state=state
    )


def build_auth_url(
    pkce: PKCEChallenge,
    scopes: list[str] = None,
    redirect_tma: Optional[str] = None,
    response_format: Optional[str] = None
) -> str:
    """
    Build TON ID authorization URL

    Args:
        pkce: PKCE challenge values
        scopes: OAuth scopes (default: openid, profile, wallet, offline_access)
        redirect_tma: Optional mini-app redirect URL for seamless TMA flow
        response_format: Optional "json" for mini-app integration

    Returns:
        Authorization URL to redirect user to
    """
    if scopes is None:
        scopes = ["openid", "profile", "wallet", "offline_access"]

    params = {
        "response_type": "code",
        "client_id": TONID_CLIENT_ID,
        "redirect_uri": TONID_REDIRECT_URI,
        "scope": " ".join(scopes),
        "state": pkce.state,
        "code_challenge": pkce.code_challenge,
        "code_challenge_method": "S256"
    }

    if redirect_tma:
        params["redirect_tma"] = redirect_tma

    if response_format:
        params["response_format"] = response_format

    return f"{TONID_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(
    code: str,
    code_verifier: str
) -> Dict[str, Any]:
    """
    Exchange authorization code for tokens

    Args:
        code: Authorization code from callback
        code_verifier: Original PKCE code verifier

    Returns:
        Token response with access_token, id_token, refresh_token
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TONID_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": TONID_REDIRECT_URI,
                "client_id": TONID_CLIENT_ID,
                "code_verifier": code_verifier
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.text}")

        return response.json()


async def refresh_tokens(refresh_token: str) -> Dict[str, Any]:
    """Refresh access token using refresh token"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TONID_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": TONID_CLIENT_ID
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")

        return response.json()


def verify_id_token(id_token: str) -> Dict[str, Any]:
    """
    Verify and decode ID token JWT

    Args:
        id_token: JWT from token response

    Returns:
        Decoded token claims
    """
    # Get JWKS for verification
    jwks_client = PyJWKClient(TONID_JWKS_URL)
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)

    # Decode and verify
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=TONID_CLIENT_ID,
        issuer=TONID_ISSUER
    )

    return claims


async def get_user_info(access_token: str) -> Dict[str, Any]:
    """Get user profile from userinfo endpoint"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            TONID_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if response.status_code != 200:
            raise Exception(f"Userinfo failed: {response.text}")

        data = response.json()
        return data.get("data", data)


async def get_wallet_address(access_token: str) -> Optional[Dict[str, str]]:
    """
    Get user's linked wallet address

    Returns None if user declined to share wallet
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            TONID_WALLET_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if response.status_code == 404:
            # User didn't share wallet
            return None

        if response.status_code != 200:
            raise Exception(f"Wallet fetch failed: {response.text}")

        data = response.json()
        return data.get("data", data)


async def verify_badge(
    access_token: str,
    collection_address: str
) -> bool:
    """
    Verify if user holds a badge from specific collection

    Args:
        access_token: User's access token
        collection_address: Badge collection address (friendly format)

    Returns:
        True if user has badge, False otherwise
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://id.ton.org/v1/badge/{collection_address}/verify",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if response.status_code != 200:
            return False

        data = response.json()
        return data.get("data", {}).get("hasBadge", False)


async def get_full_user_profile(access_token: str) -> TONIDUser:
    """
    Get complete user profile including wallet

    Args:
        access_token: Valid access token

    Returns:
        TONIDUser with all available data
    """
    # Get basic profile
    profile = await get_user_info(access_token)

    # Get wallet (may be None)
    wallet = await get_wallet_address(access_token)

    # Extract social verification status
    socials = profile.get("socials", {})

    return TONIDUser(
        sub=profile.get("sub"),
        telegram_id=profile.get("telegram_id"),
        name=profile.get("name"),
        picture=profile.get("picture"),
        wallet_address=wallet.get("friendly_wallet_address") if wallet else None,
        wallet_raw=wallet.get("raw_wallet_address") if wallet else None,
        twitter_verified=socials.get("twitter", False),
        youtube_verified=socials.get("youtube", False)
    )


# In-memory session storage (use Redis in production)
_pending_auth: Dict[str, PKCEChallenge] = {}


def start_auth_session(user_id: int) -> tuple[str, PKCEChallenge]:
    """
    Start OAuth session for user

    Args:
        user_id: Telegram user ID

    Returns:
        (auth_url, pkce) - URL to redirect and PKCE values to store
    """
    pkce = generate_pkce()
    _pending_auth[pkce.state] = pkce

    # Also store user_id -> state mapping for callback
    _pending_auth[f"user_{user_id}"] = pkce

    auth_url = build_auth_url(pkce)
    return auth_url, pkce


def get_pending_auth(state: str) -> Optional[PKCEChallenge]:
    """Get pending auth session by state"""
    return _pending_auth.get(state)


def clear_auth_session(state: str):
    """Clear completed auth session"""
    if state in _pending_auth:
        del _pending_auth[state]


# Convenience function for bot integration
async def complete_auth(code: str, state: str) -> Optional[TONIDUser]:
    """
    Complete OAuth flow and return verified user

    Args:
        code: Authorization code from callback
        state: State parameter for CSRF validation

    Returns:
        TONIDUser if successful, None if failed
    """
    # Get pending session
    pkce = get_pending_auth(state)
    if not pkce:
        print(f"No pending auth for state: {state}")
        return None

    try:
        # Exchange code for tokens
        tokens = await exchange_code_for_tokens(code, pkce.code_verifier)

        # Verify ID token
        claims = verify_id_token(tokens["id_token"])

        # Get full profile
        user = await get_full_user_profile(tokens["access_token"])

        # Clear session
        clear_auth_session(state)

        return user

    except Exception as e:
        print(f"Auth completion failed: {e}")
        clear_auth_session(state)
        return None
