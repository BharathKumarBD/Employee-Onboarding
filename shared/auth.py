"""Authentication and authorization utilities for Aarambh-AI."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.security.api_key import APIKeyHeader

from shared.config import ADMIN_API_KEY, DEFAULT_ADMIN_PASSWORD, DEFAULT_EMPLOYEE_ID, DEFAULT_EMPLOYEE_PASSWORD, SESSION_SECRET

# Security Bearer & Headers
bearer_scheme = HTTPBearer(auto_error=False)
admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)
session_header = APIKeyHeader(name="X-Session-Token", auto_error=False)

TOKEN_MAX_AGE = 86400 * 7  # 7 days


def hash_password(password: str, salt: str | None = None) -> str:
    """Hash a password using salted PBKDF2-HMAC-SHA256 (standard library)."""
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}:{key.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verify a plain password against a stored salt:hash string."""
    try:
        parts = stored_hash.split(":")
        if len(parts) != 2:
            return False
        salt, _ = parts
        computed = hash_password(plain_password, salt)
        return hmac.compare_digest(computed, stored_hash)
    except Exception:
        return False


def create_token(user_id: str, role: str = "employee") -> str:
    """Create a signed, tamper-proof session token without external JWT dependencies."""
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_MAX_AGE,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
    signature = hmac.new(
        SESSION_SECRET.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify and decode a signed token. Returns claims dict or None."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        expected_sig = hmac.new(
            SESSION_SECRET.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Pad base64 if needed
        padding = 4 - (len(payload_b64) % 4)
        if padding != 4:
            payload_b64 += "=" * padding

        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8"))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def get_current_user_optional(
    auth: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    session_token: str | None = Security(session_header),
    admin_key: str | None = Security(admin_key_header),
) -> dict[str, Any] | None:
    """Extract authenticated user from Bearer token, session header, or admin key."""
    # 1. Check Bearer token
    if auth and auth.credentials:
        claims = verify_token(auth.credentials)
        if claims:
            return claims

    # 2. Check X-Session-Token
    if session_token:
        claims = verify_token(session_token)
        if claims:
            return claims

    # 3. Check X-Admin-Key
    import shared.config as config
    admin_secret = getattr(config, "ADMIN_API_KEY", "").strip()
    if admin_key and admin_secret and hmac.compare_digest(admin_key, admin_secret):
        return {"sub": "admin", "role": "admin"}

    return None


def get_current_user(
    auth: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    session_token: str | None = Security(session_header),
    admin_key: str | None = Security(admin_key_header),
) -> dict[str, Any]:
    """Require valid authenticated user or raise 401."""
    user = get_current_user_optional(auth, session_token, admin_key)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in or provide a valid session token.",
        )
    return user


def require_employee_access(
    requested_employee_id: str,
    user: dict[str, Any] | None,
) -> None:
    """Enforce strict server-side employee authorization to prevent IDOR vulnerabilities.
    
    Admins can access any employee record.
    Employees can ONLY access their own records.
    Unauthenticated callers are strictly rejected with 401.
    """
    if not user or not isinstance(user, dict):
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in or provide a valid session token.",
        )
    if user.get("role") == "admin":
        return

    user_sub = user.get("sub")
    if not user_sub or user_sub != requested_employee_id:
        raise HTTPException(
            status_code=403,
            detail=f"Access forbidden: Authenticated as '{user_sub}', cannot access employee '{requested_employee_id}' data.",
        )


def require_admin_role(user: dict[str, Any]) -> None:
    """Require admin role."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator access required.",
        )

