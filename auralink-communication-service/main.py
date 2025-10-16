"""
AuraLink Communication Service
Main FastAPI application entry point
Production-Ready Implementation
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import uvicorn

# Import API configuration and utilities
from api.config import get_settings
from api.database import init_db, close_db, DatabaseHealthCheck
from api.redis_client import init_redis, close_redis, RedisHealthCheck
from api.middleware.rate_limit import RateLimitMiddleware

# Import API routers
from api.routes import matrix, mesh, presence

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    'comm_service_requests_total',
    'Total Communication Service requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'comm_service_request_duration_seconds',
    'Request latency',
    ['method', 'endpoint']
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager
    Handles startup and shutdown procedures
    """
    # Startup
    settings = get_settings()
    logger.info(f"Starting AuraLink Communication Service")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Service Port: {settings.service_port}")
    
    # Initialize database connection pool
    try:
        await init_db()
        logger.info("✓ Database connection pool initialized")
    except Exception as e:
        logger.error(f"✗ Database initialization failed: {e}")
        raise
    
    # Initialize Redis client
    try:
        await init_redis()
        logger.info("✓ Redis client initialized")
    except Exception as e:
        logger.warning(f"⚠ Redis initialization failed (continuing without cache): {e}")
    
    # Initialize modules
    logger.info("✓ Communication Service Modules:")
    logger.info("  - AuraID Module (Registration & Resolution)")
    logger.info("  - Verification Service (Email, Phone, Document, Social, Biometric)")
    logger.info("  - WebRTC Bridge (Matrix ↔ LiveKit)")
    logger.info("  - Mesh Routing Engine (AI-Optimized P2P)")
    logger.info("  - Trust System (Abuse Reporting & Auto-Moderation)")
    
    logger.info("AuraLink Communication Service fully initialized ✨")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AuraLink Communication Service...")
    await close_redis()
    await close_db()
    logger.info("All services shut down successfully")


# Create FastAPI application
settings = get_settings()
app = FastAPI(
    title="AuraLink Communication Service",
    description="Internal API for Matrix integration, AuraID management, and mesh routing",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)


# Request metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Track request metrics"""
    with REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).time():
        response = await call_next(request)
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    return response


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": {"error": str(exc)} if settings.is_development else {}
        }
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Comprehensive health check
    
    Checks:
    - Service status
    - Database connectivity
    - Redis connectivity
    """
    db_health = await DatabaseHealthCheck.check()
    redis_health = await RedisHealthCheck.check()
    
    overall_status = "healthy"
    if db_health["status"] != "healthy":
        overall_status = "degraded"
    if redis_health["status"] != "healthy":
        overall_status = "degraded"
    
    return {
        "service": "communication-service",
        "status": overall_status,
        "version": "1.0.0",
        "environment": settings.environment,
        "checks": {
            "database": db_health,
            "redis": redis_health
        }
    }


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "AuraLink Communication Service",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.environment,
        "features": {
            "auraid_management": True,
            "matrix_integration": True,
            "mesh_routing": settings.enable_mesh_routing,
            "ai_optimization": settings.enable_ai_optimization,
            "aic_protocol": settings.enable_aic_protocol
        },
        "endpoints": {
            "docs": "/docs" if settings.is_development else None,
            "health": "/health",
            "metrics": "/metrics",
            "matrix": "/internal/matrix",
            "mesh": "/internal/mesh",
            "presence": "/internal/presence"
        }
    }


# Register API routers
app.include_router(
    matrix.router,
    prefix="/internal/matrix",
    tags=["Matrix Integration"]
)

app.include_router(
    mesh.router,
    prefix="/internal/mesh",
    tags=["Mesh Network"]
)

app.include_router(
    presence.router,
    prefix="/internal/presence",
    tags=["Presence Management"]
)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
        access_log=True
    )
