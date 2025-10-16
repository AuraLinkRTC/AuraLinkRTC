"""
AuraLink Communication Service Internal API
FastAPI application for internal service communication
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AuraLink Communication Service",
    description="Internal API for Matrix integration and AuraID management",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers
from .routes import matrix, mesh, presence

# Register routers
app.include_router(matrix.router, prefix="/internal/matrix", tags=["Matrix"])
app.include_router(mesh.router, prefix="/internal/mesh", tags=["Mesh Network"])
app.include_router(presence.router, prefix="/internal/presence", tags=["Presence"])

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "communication-service"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "AuraLink Communication Service",
        "version": "1.0.0",
        "docs": "/docs"
    }
