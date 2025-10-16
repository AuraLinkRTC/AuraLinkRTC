"""
AuraLink AI Core Microservice
Main FastAPI application for AI features
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import uvicorn

# Import routers
from app.api import health, ai_agents, memory, speech, translation, aic_compression, mesh
# Phase 5 routers
from app.api import mcp, workflows, agent_teams, llm_selection
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.core.exceptions import AuraError
from app.services.grpc_server import AICgRPCServer


# Prometheus metrics
REQUEST_COUNT = Counter(
    'auralink_ai_requests_total',
    'Total AI Core requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'auralink_ai_request_duration_seconds',
    'Request latency',
    ['method', 'endpoint']
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown"""
    # Startup
    settings = get_settings()
    logging.info(f"Starting AuraLink AI Core - Environment: {settings.environment}")
    logging.info(f"Service running on port {settings.service_port}")
    
    # Initialize gRPC server for AIC Protocol (Phase 3)
    grpc_server = AICgRPCServer(port=50051)
    grpc_task = asyncio.create_task(grpc_server.start())
    logging.info("AIC gRPC server starting on port 50051")
    
    # Initialize Phase 4 & 5 services
    from app.core.dependencies import initialize_services, cleanup_services
    
    logging.info("Initializing AuraLink AI Core services...")
    
    # Initialize database
    from app.core.database import init_database
    from app.core.redis_client import init_redis
    
    try:
        await init_database()
        logging.info("✓ Database connection established")
    except Exception as e:
        logging.error(f"✗ Database initialization failed: {e}")
        raise
    
    try:
        await init_redis()
        logging.info("✓ Redis connection established")
    except Exception as e:
        logging.warning(f"⚠ Redis initialization failed (continuing without cache): {e}")
    
    try:
        await initialize_services()
        logging.info("✓ Phase 4 Services Initialized:")
        logging.info("  - Memory Service (SuperMemory.ai)")
        logging.info("  - AI Provider Service (BYOK)")
        logging.info("  - Speech Service (STT/TTS)")
        logging.info("  - Translation Service (12+ languages)")
        logging.info("  - Workflow Service (Temporal)")
        logging.info("  - Agent Service")
        logging.info("✓ Phase 5 Services Initialized:")
        logging.info("  - MCP Integration (DeepWiki, Memory, Sequential-Thinking, Supabase)")
        logging.info("  - LangGraph Agent Service (Stateful multi-step workflows)")
        logging.info("  - CrewAI Service (Role-based agent teams)")
        logging.info("  - AutoGen Service (Multi-agent conversations)")
        logging.info("  - LLM Selection Service (Multiple LLM support)")
        logging.info("  - Prefect Workflow Service (Dynamic orchestration)")
    except Exception as e:
        logging.error(f"Failed to initialize services: {e}")
    
    logging.info("AuraLink AI Core fully initialized - Phase 5 active ✨")
    
    yield
    
    # Shutdown
    logging.info("Shutting down AuraLink AI Core")
    await grpc_server.stop()
    await cleanup_services()
    logging.info("All services shut down successfully")


# Create FastAPI app
settings = get_settings()
app = FastAPI(
    title="AuraLink AI Core",
    description="Intelligent AI service for AuraLink real-time communication",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# Setup logging
setup_logging(settings.log_level)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler for AuraError
@app.exception_handler(AuraError)
async def aura_error_handler(request: Request, exc: AuraError):
    """Handle AuraError exceptions"""
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=exc.status_code
    ).inc()
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=500
    ).inc()
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": {"error": str(exc)} if settings.is_development else {}
        }
    )


# Middleware for request metrics
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


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    """Expose Prometheus metrics"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(ai_agents.router, prefix="/api/v1/agents", tags=["AI Agents"])
app.include_router(memory.router, prefix="/api/v1/memory", tags=["Memory"])
app.include_router(speech.router, prefix="/api/v1/speech", tags=["Speech"])
app.include_router(translation.router, prefix="/api/v1/translation", tags=["Translation"])
app.include_router(aic_compression.router, prefix="/api/v1/aic", tags=["AIC Protocol"])

# Phase 5 routers
app.include_router(mcp.router, prefix="/api/v1/mcp", tags=["MCP Integration"])
app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["Workflows"])
app.include_router(agent_teams.router, prefix="/api/v1/teams", tags=["Agent Teams"])
app.include_router(llm_selection.router, prefix="/api/v1/llm", tags=["LLM Selection"])

# Phase 6 routers
app.include_router(mesh.router, tags=["Mesh Network"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "AuraLink AI Core",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.environment
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=settings.is_development,
        log_level=settings.log_level.lower()
    )
