"""Authentication and authorization for DocEater API."""

import secrets
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from ..config import get_settings


class TokenData(BaseModel):
    """Token payload data."""
    
    user_id: str
    username: str
    scopes: list[str] = []
    exp: datetime
    iat: datetime


class AuthConfig(BaseModel):
    """Authentication configuration."""
    
    # JWT settings
    jwt_secret_key: str = secrets.token_urlsafe(32)
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # API key settings
    api_key_header: str = "X-API-Key"
    api_keys: dict[str, str] = {}  # api_key -> user_id mapping
    
    # Security settings
    require_auth: bool = True
    allow_anonymous_health: bool = True


# Global auth config (will be initialized from settings)
auth_config = AuthConfig()

# Security scheme for FastAPI
security = HTTPBearer(auto_error=False)


def init_auth_config(settings) -> None:
    """Initialize authentication configuration from settings."""
    global auth_config
    
    # Load from environment or use defaults
    auth_config.jwt_secret_key = getattr(settings, 'jwt_secret_key', auth_config.jwt_secret_key)
    auth_config.jwt_algorithm = getattr(settings, 'jwt_algorithm', auth_config.jwt_algorithm)
    auth_config.jwt_expiration_hours = getattr(settings, 'jwt_expiration_hours', auth_config.jwt_expiration_hours)
    auth_config.require_auth = getattr(settings, 'require_auth', auth_config.require_auth)
    auth_config.allow_anonymous_health = getattr(settings, 'allow_anonymous_health', auth_config.allow_anonymous_health)
    
    # Load API keys from environment
    api_keys_str = getattr(settings, 'api_keys', '')
    if api_keys_str:
        # Format: "key1:user1,key2:user2"
        for pair in api_keys_str.split(','):
            if ':' in pair:
                key, user_id = pair.strip().split(':', 1)
                auth_config.api_keys[key] = user_id


def create_jwt_token(user_id: str, username: str, scopes: list[str] = None) -> str:
    """Create a JWT token for a user."""
    if scopes is None:
        scopes = ["read", "write"]
    
    now = datetime.utcnow()
    exp = now + timedelta(hours=auth_config.jwt_expiration_hours)
    
    payload = {
        "user_id": user_id,
        "username": username,
        "scopes": scopes,
        "exp": exp,
        "iat": now,
    }
    
    return jwt.encode(payload, auth_config.jwt_secret_key, algorithm=auth_config.jwt_algorithm)


def verify_jwt_token(token: str) -> TokenData:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, auth_config.jwt_secret_key, algorithms=[auth_config.jwt_algorithm])
        
        return TokenData(
            user_id=payload["user_id"],
            username=payload["username"],
            scopes=payload.get("scopes", []),
            exp=datetime.fromtimestamp(payload["exp"]),
            iat=datetime.fromtimestamp(payload["iat"]),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_api_key(api_key: str) -> str:
    """Verify an API key and return the associated user ID."""
    user_id = auth_config.api_keys.get(api_key)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return user_id


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    settings = Depends(get_settings)
) -> Optional[TokenData]:
    """Get the current authenticated user."""
    
    # Initialize auth config if not done
    if not auth_config.api_keys and hasattr(settings, 'api_keys'):
        init_auth_config(settings)
    
    # If authentication is disabled, return anonymous user
    if not auth_config.require_auth:
        return TokenData(
            user_id="anonymous",
            username="anonymous",
            scopes=["read", "write"],
            exp=datetime.utcnow() + timedelta(hours=24),
            iat=datetime.utcnow(),
        )
    
    # No credentials provided
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # Try JWT token first
    try:
        return verify_jwt_token(token)
    except HTTPException:
        pass
    
    # Try API key
    try:
        user_id = verify_api_key(token)
        return TokenData(
            user_id=user_id,
            username=user_id,
            scopes=["read", "write"],
            exp=datetime.utcnow() + timedelta(hours=24),
            iat=datetime.utcnow(),
        )
    except HTTPException:
        pass
    
    # Neither worked
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    settings = Depends(get_settings)
) -> Optional[TokenData]:
    """Get the current user, but don't require authentication."""
    try:
        return await get_current_user(credentials, settings)
    except HTTPException:
        return None


def require_scope(required_scope: str):
    """Dependency to require a specific scope."""
    
    async def check_scope(current_user: TokenData = Depends(get_current_user)):
        if required_scope not in current_user.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required scope: {required_scope}",
            )
        return current_user
    
    return check_scope


# Common permission dependencies
require_read = require_scope("read")
require_write = require_scope("write")
require_admin = require_scope("admin")
