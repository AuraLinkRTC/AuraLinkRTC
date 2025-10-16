"""
Redis Client for Caching and Presence Management
Production-grade Redis client with connection pooling
"""

import redis.asyncio as aioredis
import logging
import json
from typing import Optional, Any, List
from datetime import timedelta

from .config import get_settings

logger = logging.getLogger(__name__)

# Global Redis client
_redis_client: Optional[aioredis.Redis] = None


async def create_redis_client() -> aioredis.Redis:
    """
    Create Redis client with connection pooling
    
    Features:
    - Connection pooling
    - Automatic reconnection
    - Health checks
    - JSON serialization support
    
    Returns:
        aioredis.Redis instance
    """
    settings = get_settings()
    
    logger.info(f"Creating Redis client: {settings.redis_url}")
    
    try:
        # Parse Redis URL
        if settings.redis_password:
            url = settings.redis_connection_url
        else:
            url = settings.redis_url
        
        # Create connection pool
        pool = aioredis.ConnectionPool.from_url(
            url,
            max_connections=settings.redis_max_connections,
            decode_responses=True,
            encoding="utf-8"
        )
        
        # Create Redis client
        client = aioredis.Redis(connection_pool=pool)
        
        # Test connection
        await client.ping()
        info = await client.info()
        
        logger.info(f"✓ Redis connected: v{info.get('redis_version', 'unknown')}")
        logger.info(f"✓ Redis pool created: max {settings.redis_max_connections} connections")
        
        return client
        
    except Exception as e:
        logger.error(f"✗ Failed to create Redis client: {e}")
        raise


async def get_redis_client() -> aioredis.Redis:
    """
    Get global Redis client (dependency injection)
    
    Returns:
        aioredis.Redis instance
    
    Raises:
        RuntimeError: If client not initialized
    """
    global _redis_client
    
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    
    return _redis_client


async def init_redis() -> aioredis.Redis:
    """
    Initialize global Redis client
    
    Returns:
        aioredis.Redis instance
    """
    global _redis_client
    
    if _redis_client is not None:
        logger.warning("Redis client already initialized")
        return _redis_client
    
    _redis_client = await create_redis_client()
    return _redis_client


async def close_redis() -> None:
    """
    Close Redis client gracefully
    """
    global _redis_client
    
    if _redis_client is not None:
        logger.info("Closing Redis client...")
        await _redis_client.close()
        _redis_client = None
        logger.info("✓ Redis client closed")
    else:
        logger.warning("Redis client not initialized")


class RedisCache:
    """
    High-level Redis caching utility
    
    Provides convenient methods for common caching patterns
    """
    
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None
        """
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (optional)
        
        Returns:
            True if successful
        """
        try:
            serialized = json.dumps(value)
            if ttl:
                await self.redis.setex(key, ttl, serialized)
            else:
                await self.redis.set(key, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache
        
        Args:
            key: Cache key
        
        Returns:
            True if successful
        """
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache
        
        Args:
            key: Cache key
        
        Returns:
            True if exists
        """
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment counter
        
        Args:
            key: Cache key
            amount: Increment amount
        
        Returns:
            New value or None
        """
        try:
            return await self.redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return None
    
    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set TTL on existing key
        
        Args:
            key: Cache key
            ttl: Time to live in seconds
        
        Returns:
            True if successful
        """
        try:
            return await self.redis.expire(key, ttl)
        except Exception as e:
            logger.error(f"Cache expire error for key {key}: {e}")
            return False


class PresenceManager:
    """
    Manage user presence using Redis
    
    Stores online/offline status with TTL
    """
    
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self.presence_prefix = "presence:"
        self.default_ttl = 300  # 5 minutes
    
    async def set_online(
        self,
        aura_id: str,
        status: str = "online",
        ttl: int = None
    ) -> bool:
        """
        Set user as online
        
        Args:
            aura_id: User AuraID
            status: Status message (online, away, busy, dnd)
            ttl: Time to live in seconds
        
        Returns:
            True if successful
        """
        try:
            key = f"{self.presence_prefix}{aura_id}"
            await self.redis.setex(
                key,
                ttl or self.default_ttl,
                status
            )
            return True
        except Exception as e:
            logger.error(f"Set online error for {aura_id}: {e}")
            return False
    
    async def set_offline(self, aura_id: str) -> bool:
        """
        Set user as offline
        
        Args:
            aura_id: User AuraID
        
        Returns:
            True if successful
        """
        try:
            key = f"{self.presence_prefix}{aura_id}"
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Set offline error for {aura_id}: {e}")
            return False
    
    async def get_status(self, aura_id: str) -> Optional[str]:
        """
        Get user presence status
        
        Args:
            aura_id: User AuraID
        
        Returns:
            Status or None if offline
        """
        try:
            key = f"{self.presence_prefix}{aura_id}"
            return await self.redis.get(key)
        except Exception as e:
            logger.error(f"Get status error for {aura_id}: {e}")
            return None
    
    async def is_online(self, aura_id: str) -> bool:
        """
        Check if user is online
        
        Args:
            aura_id: User AuraID
        
        Returns:
            True if online
        """
        status = await self.get_status(aura_id)
        return status is not None
    
    async def get_bulk_status(self, aura_ids: List[str]) -> dict:
        """
        Get presence for multiple users
        
        Args:
            aura_ids: List of AuraIDs
        
        Returns:
            Dict mapping aura_id -> status
        """
        try:
            keys = [f"{self.presence_prefix}{aid}" for aid in aura_ids]
            values = await self.redis.mget(keys)
            
            result = {}
            for aura_id, status in zip(aura_ids, values):
                result[aura_id] = {
                    "status": status or "offline",
                    "is_online": status is not None
                }
            
            return result
        except Exception as e:
            logger.error(f"Bulk status error: {e}")
            return {}


class RateLimiter:
    """
    Redis-based rate limiter using sliding window algorithm
    """
    
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self.prefix = "rate_limit:"
    
    async def check_limit(
        self,
        key: str,
        limit: int,
        window: int = 60
    ) -> bool:
        """
        Check if request is within rate limit
        
        Args:
            key: Rate limit key (e.g., user:123 or ip:1.2.3.4)
            limit: Maximum requests per window
            window: Time window in seconds
        
        Returns:
            True if within limit, False if exceeded
        """
        try:
            full_key = f"{self.prefix}{key}"
            
            # Increment counter
            current = await self.redis.incr(full_key)
            
            # Set expiry on first request
            if current == 1:
                await self.redis.expire(full_key, window)
            
            # Check if limit exceeded
            return current <= limit
            
        except Exception as e:
            logger.error(f"Rate limit check error for {key}: {e}")
            # Fail open (allow request) on error
            return True
    
    async def get_remaining(
        self,
        key: str,
        limit: int
    ) -> int:
        """
        Get remaining requests in current window
        
        Args:
            key: Rate limit key
            limit: Maximum requests per window
        
        Returns:
            Remaining requests
        """
        try:
            full_key = f"{self.prefix}{key}"
            current = await self.redis.get(full_key)
            
            if current is None:
                return limit
            
            remaining = limit - int(current)
            return max(0, remaining)
            
        except Exception as e:
            logger.error(f"Get remaining error for {key}: {e}")
            return 0


class RedisHealthCheck:
    """Redis health check utility"""
    
    @staticmethod
    async def check() -> dict:
        """
        Check Redis health
        
        Returns:
            Health check result
        """
        try:
            client = await get_redis_client()
            
            # Ping
            await client.ping()
            
            # Get info
            info = await client.info()
            
            # Get stats
            used_memory_mb = info.get('used_memory', 0) / 1024 / 1024
            connected_clients = info.get('connected_clients', 0)
            
            return {
                "status": "healthy",
                "redis_version": info.get('redis_version', 'unknown'),
                "used_memory_mb": round(used_memory_mb, 2),
                "connected_clients": connected_clients,
                "uptime_seconds": info.get('uptime_in_seconds', 0)
            }
            
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# FastAPI dependency
async def get_redis():
    """
    FastAPI dependency for Redis access
    
    Usage:
        @app.get("/cache")
        async def get_cache(redis: aioredis.Redis = Depends(get_redis)):
            value = await redis.get("key")
    """
    return await get_redis_client()
