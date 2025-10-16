"""
Health check endpoints for AI Core service
"""

from fastapi import APIRouter, status
from datetime import datetime
from typing import Dict, Any
import psutil
import os

router = APIRouter()


async def get_dependencies_health() -> Dict[str, Any]:
    """Check health of all dependencies"""
    dependencies = {}
    
    # Check database
    try:
        from app.core.database import get_database
        db = get_database()
        db_health = await db.health_check()
        dependencies["database"] = db_health
    except Exception as e:
        dependencies["database"] = {"status": "error", "error": str(e)}
    
    # Check Redis
    try:
        from app.core.redis_client import get_redis
        redis_client = get_redis()
        redis_health = await redis_client.health_check()
        dependencies["redis"] = redis_health
    except Exception as e:
        dependencies["redis"] = {"status": "error", "error": str(e)}
    
    return dependencies


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint
    """
    return {
        "status": "healthy",
        "service": "auralink-ai-core",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@router.get("/health/detailed", status_code=status.HTTP_200_OK)
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detailed health check with system metrics
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "status": "healthy",
        "service": "auralink-ai-core",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "system": {
            "cpu_percent": cpu_percent,
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "used": memory.used
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent
            },
            "process": {
                "pid": os.getpid(),
                "threads": psutil.Process().num_threads()
            }
        },
        "dependencies": await get_dependencies_health()
    }


@router.get("/readiness", status_code=status.HTTP_200_OK)
async def readiness_check() -> Dict[str, Any]:
    """
    Comprehensive Kubernetes readiness probe
    Returns 200 only if all critical services are ready to accept traffic
    Returns 503 if any critical service is not initialized
    """
    from fastapi import HTTPException
    
    checks = {}
    all_ready = True
    
    # 1. Database check (CRITICAL)
    try:
        from app.core.database import get_database_pool
        pool = get_database_pool()
        if pool is None:
            checks["database"] = {"status": "not_initialized", "ready": False}
            all_ready = False
        else:
            # Test actual connection
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            checks["database"] = {"status": "connected", "ready": True}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e), "ready": False}
        all_ready = False
    
    # 2. Redis check (OPTIONAL - don't fail readiness if Redis is down)
    try:
        from app.core.redis_client import get_redis_client
        redis = get_redis_client()
        if redis is None:
            checks["redis"] = {"status": "not_initialized", "ready": False, "optional": True}
        else:
            await redis.ping()
            checks["redis"] = {"status": "connected", "ready": True}
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e), "ready": False, "optional": True}
        # Don't fail overall readiness for Redis
    
    # 3. gRPC server check (CRITICAL for AIC Protocol)
    try:
        from app.services.grpc_server import get_grpc_server_status
        grpc_status = get_grpc_server_status()
        checks["grpc_server"] = {"status": grpc_status, "ready": grpc_status == "running"}
        if grpc_status != "running":
            all_ready = False
    except Exception as e:
        checks["grpc_server"] = {"status": "error", "error": str(e), "ready": False}
        all_ready = False
    
    # 4. Memory service check (if enabled)
    try:
        from app.core.config import get_settings
        settings = get_settings()
        if settings.enable_memory:
            from app.core.dependencies import get_memory_service
            memory_service = get_memory_service()
            if memory_service is None or not hasattr(memory_service, 'is_initialized'):
                checks["memory_service"] = {"status": "not_initialized", "ready": False}
            elif not memory_service.is_initialized():
                checks["memory_service"] = {"status": "not_initialized", "ready": False}
            else:
                checks["memory_service"] = {"status": "initialized", "ready": True}
    except Exception as e:
        checks["memory_service"] = {"status": "error", "error": str(e), "ready": False}
    
    # 5. Speech service check (if enabled)
    try:
        if settings.enable_speech:
            from app.core.dependencies import get_speech_service
            speech_service = get_speech_service()
            if speech_service is None or not hasattr(speech_service, 'is_initialized'):
                checks["speech_service"] = {"status": "not_initialized", "ready": False}
            elif not speech_service.is_initialized():
                checks["speech_service"] = {"status": "not_initialized", "ready": False}
            else:
                checks["speech_service"] = {"status": "initialized", "ready": True}
    except Exception as e:
        checks["speech_service"] = {"status": "error", "error": str(e), "ready": False}
    
    # 6. Agent service check (if enabled)
    try:
        if settings.enable_agents:
            from app.core.dependencies import get_agent_service
            agent_service = get_agent_service()
            if agent_service is None or not hasattr(agent_service, 'is_initialized'):
                checks["agent_service"] = {"status": "not_initialized", "ready": False}
            elif not agent_service.is_initialized():
                checks["agent_service"] = {"status": "not_initialized", "ready": False}
            else:
                checks["agent_service"] = {"status": "initialized", "ready": True}
    except Exception as e:
        checks["agent_service"] = {"status": "error", "error": str(e), "ready": False}
    
    # Overall status
    response = {
        "ready": all_ready,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
        "service": "auralink-ai-core"
    }
    
    # Return 503 if not ready (Kubernetes will not route traffic)
    if not all_ready:
        raise HTTPException(status_code=503, detail=response)
    
    return response


@router.get("/liveness", status_code=status.HTTP_200_OK)
async def liveness_check() -> Dict[str, Any]:
    """
    Kubernetes liveness probe
    Checks if the process is alive and event loop is responsive
    Returns 500 if process is hung or deadlocked
    """
    import asyncio
    from fastapi import HTTPException
    
    try:
        # Test if event loop is responsive
        await asyncio.sleep(0)  # Yields to event loop
        
        # Check if process is not consuming excessive resources
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Warn if resource usage is extreme (but don't fail)
        warnings = []
        if cpu_percent > 95:
            warnings.append(f"High CPU usage: {cpu_percent}%")
        if memory.percent > 95:
            warnings.append(f"High memory usage: {memory.percent}%")
        
        response = {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat(),
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "pid": os.getpid()
        }
        
        if warnings:
            response["warnings"] = warnings
        
        return response
        
    except asyncio.CancelledError:
        # Event loop is being cancelled - process is shutting down
        raise HTTPException(
            status_code=500,
            detail={"status": "dead", "error": "Event loop cancelled"}
        )
    except Exception as e:
        # Process is hung or deadlocked
        raise HTTPException(
            status_code=500,
            detail={"status": "dead", "error": str(e)}
        )
