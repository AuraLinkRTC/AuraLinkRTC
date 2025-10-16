"""
Authentication utilities for AuraLink Python services
"""

import os
import jwt
from typing import Dict, Any, Optional
from datetime import datetime
from .errors import AuraError, ErrorCode


def get_supabase_config() -> Dict[str, str]:
    """Get Supabase configuration from environment"""
    return {
        "url": os.getenv("SUPABASE_URL", ""),
        "anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
        "service_role_key": os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        "jwt_secret": os.getenv("SUPABASE_JWT_SECRET", ""),
    }


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify a Supabase JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        Dict containing decoded claims
        
    Raises:
        AuraError: If token is invalid or expired
    """
    config = get_supabase_config()
    jwt_secret = config.get("jwt_secret")
    
    if not jwt_secret:
        raise AuraError(
            ErrorCode.INTERNAL_ERROR,
            "JWT secret not configured"
        )
    
    try:
        # Decode and verify token
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            options={"verify_exp": True}
        )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise AuraError(
            ErrorCode.EXPIRED_TOKEN,
            "Token has expired"
        )
    except jwt.InvalidTokenError as e:
        raise AuraError(
            ErrorCode.INVALID_TOKEN,
            f"Invalid token: {str(e)}"
        )


def get_user_from_token(token: str) -> Dict[str, Any]:
    """
    Extract user information from JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        Dict containing user_id, email, and role
        
    Raises:
        AuraError: If token is invalid
    """
    claims = verify_token(token)
    
    return {
        "user_id": claims.get("sub"),
        "email": claims.get("email"),
        "role": claims.get("role", "user"),
        "session_id": claims.get("session_id"),
    }


def extract_token(authorization: Optional[str]) -> Optional[str]:
    """
    Extract bearer token from Authorization header
    
    Args:
        authorization: Authorization header value
        
    Returns:
        Token string or None
    """
    if not authorization:
        return None
        
    parts = authorization.split()
    if len(parts) == 2 and parts[0].upper() == "BEARER":
        return parts[1]
        
    return None


def require_auth(authorization: Optional[str]) -> Dict[str, Any]:
    """
    Require authentication and return user info
    
    Args:
        authorization: Authorization header value
        
    Returns:
        Dict containing user information
        
    Raises:
        AuraError: If authentication fails
    """
    token = extract_token(authorization)
    if not token:
        raise AuraError(
            ErrorCode.UNAUTHORIZED,
            "Missing authentication token"
        )
    
    return get_user_from_token(token)


def require_role(user: Dict[str, Any], required_role: str) -> None:
    """
    Require user to have a specific role
    
    Args:
        user: User information dict
        required_role: Required role
        
    Raises:
        AuraError: If user doesn't have required role
    """
    user_role = user.get("role", "user")
    
    role_hierarchy = {
        "user": 0,
        "moderator": 1,
        "admin": 2,
    }
    
    required_level = role_hierarchy.get(required_role, 0)
    user_level = role_hierarchy.get(user_role, 0)
    
    if user_level < required_level:
        raise AuraError(
            ErrorCode.FORBIDDEN,
            f"Required role: {required_role}"
        )
