"""
Rate Limiting Middleware
Redis-based sliding window rate limiting
"""

import logging
from typing import Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from ..config import get_settings
from ..redis_client import get_redis_client, RateLimiter

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using Redis sliding window algorithm
    
    Limits:
    - 100 requests/minute per user
    - 1000 requests/minute per service
    - 10000 requests/minute per IP for anonymous requests
    """
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and apply rate limiting
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
        
        Returns:
            Response
        """
        settings = get_settings()
        
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)
        
        try:
            # Get Redis client
            redis = await get_redis_client()
            rate_limiter = RateLimiter(redis)
            
            # Determine rate limit key
            rate_limit_key, limit, window = await self._get_rate_limit_params(request)
            
            # Check rate limit
            allowed = await rate_limiter.check_limit(rate_limit_key, limit, window)
            
            if not allowed:
                # Get remaining count for response headers
                remaining = await rate_limiter.get_remaining(rate_limit_key, limit)
                
                logger.warning(f"Rate limit exceeded: {rate_limit_key}")
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {window} seconds.",
                    headers={
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": str(remaining),
                        "X-RateLimit-Reset": str(window),
                        "Retry-After": str(window)
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers to response
            remaining = await rate_limiter.get_remaining(rate_limit_key, limit)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(window)
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limit middleware error: {e}")
            # Fail open - allow request if rate limiting fails
            return await call_next(request)
    
    async def _get_rate_limit_params(
        self,
        request: Request
    ) -> tuple[str, int, int]:
        """
        Get rate limit parameters for request
        
        Args:
            request: Incoming request
        
        Returns:
            (key, limit, window_seconds)
        """
        settings = get_settings()
        
        # Check for authenticated service (from JWT)
        if hasattr(request.state, "auth"):
            auth = request.state.auth
            
            # Service authentication
            if auth.get("service"):
                return (
                    f"service:{auth['service']}",
                    settings.rate_limit_per_service,
                    settings.rate_limit_window_seconds
                )
            
            # User authentication
            if auth.get("aura_id"):
                return (
                    f"user:{auth['aura_id']}",
                    settings.rate_limit_per_user,
                    settings.rate_limit_window_seconds
                )
        
        # Fallback to IP-based rate limiting
        client_ip = request.client.host if request.client else "unknown"
        return (
            f"ip:{client_ip}",
            10000,  # Higher limit for anonymous
            60  # 1 minute window
        )
