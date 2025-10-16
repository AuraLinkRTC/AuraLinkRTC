"""
Database Connection Pool Management
Production-grade PostgreSQL connection pooling with asyncpg
"""

import asyncpg
import logging
from typing import Optional
from contextlib import asynccontextmanager

from .config import get_settings

logger = logging.getLogger(__name__)

# Global connection pool
_db_pool: Optional[asyncpg.Pool] = None


async def create_db_pool() -> asyncpg.Pool:
    """
    Create asyncpg connection pool with production configuration
    
    Features:
    - Connection pooling (5-20 connections)
    - Automatic reconnection
    - Statement timeout
    - Command timeout
    - Health checks
    
    Returns:
        asyncpg.Pool instance
    """
    settings = get_settings()
    
    logger.info(f"Creating database connection pool to {settings.database_url}")
    
    try:
        pool = await asyncpg.create_pool(
            dsn=str(settings.database_url),
            min_size=settings.database_pool_min,
            max_size=settings.database_pool_max,
            timeout=settings.database_pool_timeout,
            command_timeout=settings.database_command_timeout,
            # Connection initialization callback
            init=_init_connection,
            # Connection setup for each new connection
            setup=_setup_connection,
        )
        
        # Test connection
        async with pool.acquire() as conn:
            version = await conn.fetchval("SELECT version()")
            logger.info(f"✓ Database connected: {version[:50]}...")
        
        logger.info(
            f"✓ Connection pool created: "
            f"{settings.database_pool_min}-{settings.database_pool_max} connections"
        )
        
        return pool
        
    except Exception as e:
        logger.error(f"✗ Failed to create database pool: {e}")
        raise


async def _init_connection(conn: asyncpg.Connection) -> None:
    """
    Initialize each new connection
    
    Args:
        conn: asyncpg connection
    """
    # Set statement timeout to prevent long-running queries
    await conn.execute("SET statement_timeout TO '60s'")
    
    # Set timezone
    await conn.execute("SET timezone TO 'UTC'")
    
    # Enable json type support
    await conn.set_type_codec(
        'json',
        encoder=lambda v: v,
        decoder=lambda v: v,
        schema='pg_catalog'
    )
    
    logger.debug(f"Connection initialized: {id(conn)}")


async def _setup_connection(conn: asyncpg.Connection) -> None:
    """
    Setup connection-specific configuration
    
    Args:
        conn: asyncpg connection
    """
    # Add custom type handlers if needed
    pass


async def get_db_pool() -> asyncpg.Pool:
    """
    Get global database pool (dependency injection)
    
    Returns:
        asyncpg.Pool instance
    
    Raises:
        RuntimeError: If pool not initialized
    """
    global _db_pool
    
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    
    return _db_pool


async def init_db() -> asyncpg.Pool:
    """
    Initialize global database connection pool
    
    Returns:
        asyncpg.Pool instance
    """
    global _db_pool
    
    if _db_pool is not None:
        logger.warning("Database pool already initialized")
        return _db_pool
    
    _db_pool = await create_db_pool()
    return _db_pool


async def close_db() -> None:
    """
    Close database connection pool gracefully
    """
    global _db_pool
    
    if _db_pool is not None:
        logger.info("Closing database connection pool...")
        await _db_pool.close()
        _db_pool = None
        logger.info("✓ Database pool closed")
    else:
        logger.warning("Database pool not initialized")


@asynccontextmanager
async def get_db_connection():
    """
    Context manager for database connections
    
    Usage:
        async with get_db_connection() as conn:
            result = await conn.fetchrow("SELECT * FROM users")
    
    Yields:
        asyncpg.Connection
    """
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def get_db_transaction():
    """
    Context manager for database transactions
    
    Automatically commits on success, rolls back on exception
    
    Usage:
        async with get_db_transaction() as conn:
            await conn.execute("INSERT INTO ...")
            await conn.execute("UPDATE ...")
    
    Yields:
        asyncpg.Connection with active transaction
    """
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn


class DatabaseHealthCheck:
    """Database health check utility"""
    
    @staticmethod
    async def check() -> dict:
        """
        Check database health
        
        Returns:
            Health check result
        """
        try:
            pool = await get_db_pool()
            
            async with pool.acquire() as conn:
                # Check basic connectivity
                await conn.fetchval("SELECT 1")
                
                # Get pool stats
                pool_size = pool.get_size()
                pool_free = pool.get_idle_size()
                pool_used = pool_size - pool_free
                
                # Get database stats
                db_stats = await conn.fetchrow("""
                    SELECT 
                        pg_database_size(current_database()) as db_size,
                        numbackends as active_connections
                    FROM pg_stat_database
                    WHERE datname = current_database()
                """)
                
                return {
                    "status": "healthy",
                    "pool": {
                        "size": pool_size,
                        "free": pool_free,
                        "used": pool_used,
                        "utilization": f"{(pool_used / pool_size * 100):.1f}%"
                    },
                    "database": {
                        "size_mb": round(db_stats['db_size'] / 1024 / 1024, 2),
                        "active_connections": db_stats['active_connections']
                    }
                }
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Dependency for FastAPI
async def get_db():
    """
    FastAPI dependency for database access
    
    Usage:
        @app.get("/users")
        async def get_users(db: asyncpg.Pool = Depends(get_db)):
            async with db.acquire() as conn:
                users = await conn.fetch("SELECT * FROM users")
    """
    return await get_db_pool()
