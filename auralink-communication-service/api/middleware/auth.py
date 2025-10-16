"""
JWT Authentication Middleware
Service-to-service authentication for internal API
"""

import logging
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta

from ..config import get_settings

logger = logging.getLogger(__name__)

security = HTTPBearer()


class AuthenticationError(HTTPException):
    """Authentication error exception"""
    
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


async def verify_service_token(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> dict:
    """
    Verify JWT service token
    
    Args:
        credentials: HTTP Bearer credentials
    
    Returns:
        Token payload
    
    Raises:
        AuthenticationError: If token is invalid
    """
    settings = get_settings()
    token = credentials.credentials
    
    try:
        # Decode JWT
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
            raise AuthenticationError("Token expired")
        
        # Extract service identity
        service_name = payload.get("service")
        if not service_name:
            raise AuthenticationError("Invalid token: missing service identifier")
        
        logger.debug(f"Authenticated service: {service_name}")
        
        return {
            "service": service_name,
            "scopes": payload.get("scopes", []),
            "user_id": payload.get("user_id"),
            "aura_id": payload.get("aura_id")
        }
        
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise AuthenticationError("Invalid token")
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise AuthenticationError("Authentication failed")


def create_service_token(
    service_name: str,
    scopes: list = None,
    expires_minutes: int = None
) -> str:
    """
    Create JWT token for service-to-service communication
    
    Args:
        service_name: Service name
        scopes: Access scopes
        expires_minutes: Token expiration in minutes
    
    Returns:
        JWT token string
    """
    settings = get_settings()
    expires_minutes = expires_minutes or settings.jwt_expiration_minutes
    
    payload = {
        "service": service_name,
        "scopes": scopes or [],
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),
        "iat": datetime.utcnow()
    }
    
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    return token


def create_user_token(
    user_id: str,
    aura_id: str,
    scopes: list = None,
    expires_minutes: int = None
) -> str:
    """
    Create JWT token for user authentication
    
    Args:
        user_id: User ID
        aura_id: AuraID
        scopes: Access scopes
        expires_minutes: Token expiration in minutes
    
    Returns:
        JWT token string
    """
    settings = get_settings()
    expires_minutes = expires_minutes or settings.jwt_expiration_minutes
    
    payload = {
        "user_id": user_id,
        "aura_id": aura_id,
        "scopes": scopes or [],
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),
        "iat": datetime.utcnow()
    }
    
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    return token
