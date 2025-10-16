"""
AuraLink Mesh Routing API
Phase 6: AuraID & Mesh Network
Enterprise-grade mesh routing endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

from app.core.dependencies import get_db_pool
from app.services.mesh_routing_service import MeshRoutingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mesh", tags=["mesh"])


# ================================================================
# Request/Response Models
# ================================================================

class FindRouteRequest(BaseModel):
    """Request to find optimal route"""
    source_aura_id: str = Field(..., description="Source AuraID")
    destination_aura_id: str = Field(..., description="Destination AuraID")
    media_type: str = Field(default="audio_video", description="Media type: audio, video, audio_video")
    require_aic: bool = Field(default=False, description="Require AIC Protocol support")


class RouteResponse(BaseModel):
    """Route response with AI-optimized path"""
    route_id: Optional[str] = None
    source_node_id: str
    destination_node_id: str
    path_nodes: List[str]
    path_length: int
    route_type: str
    predicted_latency_ms: int
    predicted_bandwidth_mbps: int
    ai_score: float
    is_optimal: bool
    supports_aic: bool
    media_type: str
    optimization_factors: Dict[str, Any]


class UpdateRoutePerformanceRequest(BaseModel):
    """Update route with actual performance metrics"""
    route_id: str
    actual_latency_ms: int
    actual_bandwidth_mbps: int
    packet_loss_rate: float
    jitter_ms: int


class RouteAnalyticsResponse(BaseModel):
    """Route analytics data"""
    total_routes: int
    optimal_routes: int
    avg_ai_score: float
    avg_predicted_latency: float
    avg_actual_latency: Optional[float]
    avg_prediction_error: Optional[float]
    avg_success_rate: float


# ================================================================
# Endpoints
# ================================================================

@router.post("/find-route", response_model=RouteResponse, status_code=status.HTTP_200_OK)
async def find_optimal_route(
    request: FindRouteRequest,
    db_pool=Depends(get_db_pool)
):
    """
    Find optimal route between two AuraIDs using AI prediction
    
    This endpoint uses machine learning to predict the best path through
    the mesh network based on latency, bandwidth, reputation, and other factors.
    """
    try:
        routing_service = MeshRoutingService(db_pool)
        
        route = await routing_service.find_optimal_route(
            source_aura_id=request.source_aura_id,
            destination_aura_id=request.destination_aura_id,
            media_type=request.media_type,
            require_aic=request.require_aic
        )
        
        if not route:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No route available between {request.source_aura_id} and {request.destination_aura_id}"
            )
        
        return RouteResponse(**route)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding route: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find optimal route"
        )


@router.post("/routes/performance", status_code=status.HTTP_200_OK)
async def update_route_performance(
    request: UpdateRoutePerformanceRequest,
    db_pool=Depends(get_db_pool)
):
    """
    Update route with actual performance metrics
    
    This endpoint is used to feed actual performance data back into the
    AI model for continuous learning and improvement.
    """
    try:
        routing_service = MeshRoutingService(db_pool)
        
        await routing_service.update_route_performance(
            route_id=request.route_id,
            actual_latency_ms=request.actual_latency_ms,
            actual_bandwidth_mbps=request.actual_bandwidth_mbps,
            packet_loss_rate=request.packet_loss_rate,
            jitter_ms=request.jitter_ms
        )
        
        return {
            "success": True,
            "message": "Route performance updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error updating route performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update route performance"
        )


@router.get("/routes/analytics", response_model=RouteAnalyticsResponse)
async def get_route_analytics(
    time_range_hours: int = 24,
    db_pool=Depends(get_db_pool)
):
    """
    Get analytics for mesh routing performance
    
    Returns aggregated statistics about route quality, AI prediction
    accuracy, and overall mesh network performance.
    """
    try:
        routing_service = MeshRoutingService(db_pool)
        
        analytics = await routing_service.get_route_analytics(time_range_hours)
        
        return RouteAnalyticsResponse(
            total_routes=analytics.get('total_routes', 0),
            optimal_routes=analytics.get('optimal_routes', 0),
            avg_ai_score=analytics.get('avg_ai_score', 0.0),
            avg_predicted_latency=analytics.get('avg_predicted_latency', 0.0),
            avg_actual_latency=analytics.get('avg_actual_latency'),
            avg_prediction_error=analytics.get('avg_prediction_error'),
            avg_success_rate=analytics.get('avg_success_rate', 0.0)
        )
        
    except Exception as e:
        logger.error(f"Error getting route analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get route analytics"
        )


@router.get("/health", status_code=status.HTTP_200_OK)
async def mesh_service_health(db_pool=Depends(get_db_pool)):
    """Check mesh routing service health"""
    try:
        async with db_pool.acquire() as conn:
            # Check database connectivity
            await conn.fetchval("SELECT 1")
            
            # Get node statistics
            node_count = await conn.fetchval("""
                SELECT COUNT(*) FROM mesh_nodes WHERE is_online = TRUE
            """)
            
            # Get route statistics
            route_count = await conn.fetchval("""
                SELECT COUNT(*) FROM mesh_routes 
                WHERE is_active = TRUE AND expires_at > NOW()
            """)
            
            return {
                "status": "healthy",
                "service": "mesh_routing",
                "online_nodes": node_count,
                "active_routes": route_count,
                "ai_routing_enabled": True
            }
            
    except Exception as e:
        logger.error(f"Mesh service health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mesh routing service unhealthy"
        )
