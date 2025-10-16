"""
Rate limiting middleware for AuraLink AI Core
Implements Redis-backed sliding window rate limiting
"""

import time
import logging
from typing import Optional, Callable
from functools import wraps

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis-backed rate limiter using sliding window algorithm"""
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: Optional[int] = None,
        requests_per_day: Optional[int] = None,
        key_prefix: str = "rate_limit"
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.requests_per_day = requests_per_day
        self.key_prefix = key_prefix
    
    def _get_rate_limit_key(self, identifier: str, window: str) -> str:
        """Generate Redis key for rate limiting"""
        return f"{self.key_prefix}:{identifier}:{window}"
    
    async def _check_limit(
        self,
        redis_client,
        identifier: str,
        limit: int,
        window_seconds: int,
        window_name: str
    ) -> tuple[bool, int, int]:
        """
        Check if request is within rate limit
        
        Returns:
            (allowed, current_count, reset_time)
        """
        if not redis_client.client:
            # If Redis is down, allow request (fail open)
            logger.warning("Redis unavailable - rate limiting disabled")
            return True, 0, 0
        
        key = self._get_rate_limit_key(identifier, window_name)
        current_time = int(time.time())
        window_start = current_time - window_seconds
        
        try:
            # Use sliding window counter
            pipe = redis_client.client.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count entries in current window
            pipe.zcard(key)
            
            # Add current request timestamp
            pipe.zadd(key, {f"{current_time}:{time.time_ns()}": current_time})
            
            # Set expiration
            pipe.expire(key, window_seconds + 10)
            
            results = await pipe.execute()
            current_count = results[1] if len(results) > 1 else 0
            
            # Check if limit exceeded (before adding current request)
            if current_count >= limit:
                reset_time = current_time + window_seconds
                return False, current_count, reset_time
            
            reset_time = current_time + window_seconds
            return True, current_count + 1, reset_time
            
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # Fail open - allow request if Redis operation fails
            return True, 0, 0
    
    async def check_rate_limit(self, identifier: str) -> dict:
        """
        Check all configured rate limits
        
        Returns dict with rate limit status and headers
        """
        redis_client = get_redis()
        
        # Check minute limit
        allowed = True
        limit_name = "minute"
        current_count = 0
        reset_time = 0
        
        if self.requests_per_minute:
            allowed, current_count, reset_time = await self._check_limit(
                redis_client,
                identifier,
                self.requests_per_minute,
                60,
                "minute"
            )
            if not allowed:
                limit_name = "minute"
        
        # Check hour limit if minute limit passed
        if allowed and self.requests_per_hour:
            allowed, count_hour, reset_hour = await self._check_limit(
                redis_client,
                identifier,
                self.requests_per_hour,
                3600,
                "hour"
            )
            if not allowed:
                limit_name = "hour"
                current_count = count_hour
                reset_time = reset_hour
        
        # Check day limit if hour limit passed
        if allowed and self.requests_per_day:
            allowed, count_day, reset_day = await self._check_limit(
                redis_client,
                identifier,
                self.requests_per_day,
                86400,
                "day"
            )
            if not allowed:
                limit_name = "day"
                current_count = count_day
                reset_time = reset_day
        
        return {
            "allowed": allowed,
            "limit_name": limit_name,
            "current_count": current_count,
            "reset_time": reset_time,
            "limit_minute": self.requests_per_minute,
            "limit_hour": self.requests_per_hour,
            "limit_day": self.requests_per_day
        }


class RateLimitMiddleware:
    """FastAPI middleware for rate limiting"""
    
    def __init__(
        self,
        app,
        default_limit: int = 100,
        per_user_limit: int = 60,
        per_ip_limit: int = 30
    ):
        self.app = app
        self.default_limiter = RateLimiter(requests_per_minute=default_limit)
        self.user_limiter = RateLimiter(
            requests_per_minute=per_user_limit,
            requests_per_hour=per_user_limit * 60,
            requests_per_day=per_user_limit * 60 * 24
        )
        self.ip_limiter = RateLimiter(
            requests_per_minute=per_ip_limit,
            requests_per_hour=per_ip_limit * 30
        )
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        
        request = Request(scope, receive)
        
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/readiness", "/liveness", "/metrics"]:
            return await self.app(scope, receive, send)
        
        # Determine identifier (prefer user ID over IP)
        identifier = None
        user_id = request.headers.get("X-User-ID") or request.state.__dict__.get("user_id")
        
        if user_id:
            identifier = f"user:{user_id}"
            limiter = self.user_limiter
        else:
            # Fall back to IP-based limiting
            client_ip = request.client.host if request.client else "unknown"
            identifier = f"ip:{client_ip}"
            limiter = self.ip_limiter
        
        # Check rate limit
        result = await limiter.check_rate_limit(identifier)
        
        if not result["allowed"]:
            # Return 429 Too Many Requests
            headers = {
                "X-RateLimit-Limit": str(result.get(f"limit_{result['limit_name']}", 0)),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(result["reset_time"]),
                "Retry-After": str(result["reset_time"] - int(time.time()))
            }
            
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded for {result['limit_name']}. Please retry after {headers['Retry-After']} seconds.",
                        "limit": result.get(f"limit_{result['limit_name']}", 0),
                        "reset_time": result["reset_time"]
                    }
                },
                headers=headers
            )
            
            await response(scope, receive, send)
            return
        
        # Add rate limit headers to response
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                headers[b"x-ratelimit-limit"] = str(result.get(f"limit_{result['limit_name']}", 0)).encode()
                headers[b"x-ratelimit-remaining"] = str(
                    result.get(f"limit_{result['limit_name']}", 0) - result["current_count"]
                ).encode()
                headers[b"x-ratelimit-reset"] = str(result["reset_time"]).encode()
                message["headers"] = list(headers.items())
            
            await send(message)
        
        await self.app(scope, receive, send_with_headers)


def rate_limit(
    requests_per_minute: int = 60,
    requests_per_hour: Optional[int] = None,
    requests_per_day: Optional[int] = None
):
    """
    Decorator for endpoint-specific rate limiting
    
    Usage:
        @router.post("/api/v1/endpoint")
        @rate_limit(requests_per_minute=10, requests_per_hour=100)
        async def my_endpoint():
            ...
    """
    limiter = RateLimiter(
        requests_per_minute=requests_per_minute,
        requests_per_hour=requests_per_hour,
        requests_per_day=requests_per_day,
        key_prefix="endpoint_rate_limit"
    )
    
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from kwargs
            request = kwargs.get("request") or next(
                (arg for arg in args if isinstance(arg, Request)), None
            )
            
            if not request:
                # No request found, skip rate limiting
                return await func(*args, **kwargs)
            
            # Get user identifier
            user_id = getattr(request.state, "user_id", None)
            if user_id:
                identifier = f"user:{user_id}:{func.__name__}"
            else:
                client_ip = request.client.host if request.client else "unknown"
                identifier = f"ip:{client_ip}:{func.__name__}"
            
            # Check rate limit
            result = await limiter.check_rate_limit(identifier)
            
            if not result["allowed"]:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded for {result['limit_name']}",
                        "reset_time": result["reset_time"]
                    },
                    headers={
                        "X-RateLimit-Limit": str(result.get(f"limit_{result['limit_name']}", 0)),
                        "X-RateLimit-Reset": str(result["reset_time"]),
                        "Retry-After": str(result["reset_time"] - int(time.time()))
                    }
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator
