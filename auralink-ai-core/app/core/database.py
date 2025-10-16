"""
Database connection management with health checks and connection pooling
"""

import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager

import asyncpg
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class Database:
    """Database connection pool manager with health checks"""
    
    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self._settings = get_settings()
    
    async def connect(self) -> None:
        """Initialize database connection pool"""
        if self._pool:
            return
        
        try:
            # Build connection string from settings
            if self._settings.database_url:
                dsn = self._settings.database_url
            else:
                # Construct from Supabase settings
                dsn = f"postgresql://postgres.{self._settings.supabase_url.split('//')[1].split('.')[0]}:{self._settings.supabase_service_role_key}@{self._settings.supabase_url.split('//')[1]}/postgres"
            
            self._pool = await asyncpg.create_pool(
                dsn,
                min_size=5,
                max_size=20,
                command_timeout=60,
                max_queries=50000,
                max_inactive_connection_lifetime=300
            )
            
            # Verify connection
            async with self._pool.acquire() as conn:
                version = await conn.fetchval('SELECT version()')
                logger.info(f"✓ Database connected: {version[:50]}")
                
                # Check critical tables exist
                tables = await conn.fetch("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                table_count = len(tables)
                logger.info(f"✓ Database has {table_count} tables")
                
                if table_count < 50:
                    logger.warning(f"⚠ Expected ~56 tables, found only {table_count}")
                
        except Exception as e:
            logger.error(f"✗ Database connection failed: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close database connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("✓ Database disconnected")
    
    async def health_check(self) -> dict:
        """Perform database health check"""
        if not self._pool:
            return {
                "status": "unhealthy",
                "error": "No connection pool"
            }
        
        try:
            async with self._pool.acquire() as conn:
                # Simple query to check connectivity
                result = await conn.fetchval('SELECT 1')
                
                # Get pool stats
                pool_stats = {
                    "size": self._pool.get_size(),
                    "min_size": self._pool.get_min_size(),
                    "max_size": self._pool.get_max_size(),
                    "free_size": self._pool.get_idle_size()
                }
                
                return {
                    "status": "healthy",
                    "pool": pool_stats,
                    "latency_ms": 0  # Would measure in production
                }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions"""
        if not self._pool:
            raise RuntimeError("Database not connected")
        
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield conn
    
    @property
    def pool(self) -> asyncpg.Pool:
        """Get the connection pool"""
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first")
        return self._pool


# Global database instance
_db_instance: Optional[Database] = None


def get_database() -> Database:
    """Get the global database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


async def init_database() -> None:
    """Initialize database connection (call on startup)"""
    db = get_database()
    await db.connect()


async def close_database() -> None:
    """Close database connection (call on shutdown)"""
    db = get_database()
    await db.disconnect()
