import os
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "INSECURE_DEFAULT_CHANGE_IN_PRODUCTION")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 7 days default

bearerScheme = HTTPBearer(auto_error=False)
apiKeyHeader = APIKeyHeader(name="X-API-Key", auto_error=False)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def _verify_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """Verify an API key against DB. Returns user dict or None."""
    try:
        from db.connection import get_pool
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT ak.user_id, ak.id as key_id, u.org_id
                FROM api_keys ak
                JOIN users u ON u.id = ak.user_id
                WHERE ak.key_hash = $1
                  AND (ak.expires_at IS NULL OR ak.expires_at > now())
                  AND u.is_active = TRUE
            """, key_hash)
            if row:
                # Update last_used_at
                await conn.execute(
                    "UPDATE api_keys SET last_used_at = now() WHERE id = $1",
                    row["key_id"]
                )
                return {"user_id": str(row["user_id"]), "org_id": str(row["org_id"]) if row["org_id"] else None, "auth_method": "api_key"}
    except Exception as e:
        logger.warning(f"API key verification failed: {e}")
    return None

async def require_auth(
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearerScheme),
    api_key: Optional[str] = Security(apiKeyHeader),
) -> Dict[str, Any]:
    """
    Dependency that requires either a valid JWT Bearer token or a valid API key.
    Returns the user payload dict.
    """
    if bearer and bearer.credentials:
        payload = decode_token(bearer.credentials)
        payload["auth_method"] = "jwt"
        return payload

    if api_key:
        user = await _verify_api_key(api_key)
        if user:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "API-Key"},
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide a Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def optional_auth(
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearerScheme),
    api_key: Optional[str] = Security(apiKeyHeader),
) -> Optional[Dict[str, Any]]:
    """Like require_auth but returns None instead of raising if no credentials provided."""
    try:
        return await require_auth(bearer, api_key)
    except HTTPException as e:
        if e.status_code == 401:
            return None
        raise
