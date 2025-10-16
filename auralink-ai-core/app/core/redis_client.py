"""
Redis client for caching, pub/sub, and session management
"""

import asyncio
import json
import logging
from typing import Optional, Any, Union
from contextlib import asynccontextmanager

import redis.asyncio as redis
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client with connection pooling and health checks"""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._settings = get_settings()
    
    async def connect(self) -> None:
        """Initialize Redis connection"""
        if self._client:
            return
        
        try:
            # Parse Redis host
            host_port = self._settings.redis_url.split(':')
            host = host_port[0] if len(host_port) > 0 else 'localhost'
            port = int(host_port[1]) if len(host_port) > 1 else 6379
            
            self._client = await redis.from_url(
                f"redis://{host}:{port}",
                password=self._settings.redis_password if self._settings.redis_password else None,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50
            )
            
            # Verify connection
            await self._client.ping()
            info = await self._client.info('server')
            logger.info(f"✓ Redis connected: v{info.get('redis_version', 'unknown')}")
            
        except Exception as e:
            logger.error(f"✗ Redis connection failed: {e}")
            logger.warning("⚠ Service will continue without Redis caching")
            self._client = None
    
    async def disconnect(self) -> None:
        """Close Redis connection"""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("✓ Redis disconnected")
    
    async def health_check(self) -> dict:
        """Perform Redis health check"""
        if not self._client:
            return {
                "status": "unavailable",
                "message": "Redis not connected"
            }
        
        try:
            # Ping Redis
            await self._client.ping()
            
            # Get server info
            info = await self._client.info('stats')
            
            return {
                "status": "healthy",
                "connected_clients": info.get('connected_clients', 0),
                "total_commands_processed": info.get('total_commands_processed', 0),
                "keyspace_hits": info.get('keyspace_hits', 0),
                "keyspace_misses": info.get('keyspace_misses', 0)
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from Redis"""
        if not self._client:
            return None
        try:
            return await self._client.get(key)
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Union[str, dict, list],
        expire: Optional[int] = None
    ) -> bool:
        """Set value in Redis with optional expiration (seconds)"""
        if not self._client:
            return False
        
        try:
            # Serialize if needed
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            if expire:
                await self._client.setex(key, expire, value)
            else:
                await self._client.set(key, value)
            return True
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        if not self._client:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        if not self._client:
            return False
        try:
            return await self._client.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis EXISTS error: {e}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key"""
        if not self._client:
            return False
        try:
            await self._client.expire(key, seconds)
            return True
        except Exception as e:
            logger.error(f"Redis EXPIRE error: {e}")
            return False
    
    async def publish(self, channel: str, message: Union[str, dict]) -> bool:
        """Publish message to channel"""
        if not self._client:
            return False
        try:
            if isinstance(message, dict):
                message = json.dumps(message)
            await self._client.publish(channel, message)
            return True
        except Exception as e:
            logger.error(f"Redis PUBLISH error: {e}")
            return False
    
    async def subscribe(self, *channels: str):
        """Subscribe to channels (returns pubsub object)"""
        if not self._client:
            raise RuntimeError("Redis not connected")
        
        self._pubsub = self._client.pubsub()
        await self._pubsub.subscribe(*channels)
        return self._pubsub
    
    @property
    def client(self) -> Optional[redis.Redis]:
        """Get the Redis client"""
        return self._client


# Global Redis instance
_redis_instance: Optional[RedisClient] = None


def get_redis() -> RedisClient:
    """Get the global Redis instance"""
    global _redis_instance
    if _redis_instance is None:
        _redis_instance = RedisClient()
    return _redis_instance


async def init_redis() -> None:
    """Initialize Redis connection (call on startup)"""
    redis_client = get_redis()
    await redis_client.connect()


async def close_redis() -> None:
    """Close Redis connection (call on shutdown)"""
    redis_client = get_redis()
    await redis_client.disconnect()
