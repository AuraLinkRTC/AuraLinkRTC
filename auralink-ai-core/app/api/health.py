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
async def readiness_check() -> Dict[str, str]:
    """
    Kubernetes readiness probe
    """
    # TODO: Check if service is ready to accept requests
    # (database connected, dependencies available, etc.)
    return {"status": "ready"}


@router.get("/liveness", status_code=status.HTTP_200_OK)
async def liveness_check() -> Dict[str, str]:
    """
    Kubernetes liveness probe
    """
    return {"status": "alive"}
