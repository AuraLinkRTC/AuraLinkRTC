"""
Mesh Routing API Endpoints
Phase 6: AuraID & Mesh Network
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

from ..core.dependencies import get_db_pool, get_current_user
from ..services.mesh_routing_service import MeshRoutingService

router = APIRouter(prefix="/api/v1/mesh", tags=["Mesh Routing"])


# Request/Response Models
class RouteRequest(BaseModel):
    """Request for optimal route"""
    source_aura_id: str = Field(..., description="Source AuraID")
    destination_aura_id: str = Field(..., description="Destination AuraID")
    media_type: str = Field(default="audio_video", description="Media type")
    require_aic: bool = Field(default=False, description="Require AIC Protocol support")


class RouteResponse(BaseModel):
    """Route response"""
    route_id: Optional[str]
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
    optimization_factors: Dict


class RoutePerformanceUpdate(BaseModel):
    """Update route with actual performance"""
    actual_latency_ms: int = Field(..., ge=0, description="Actual latency in milliseconds")
    actual_bandwidth_mbps: int = Field(..., ge=0, description="Actual bandwidth in Mbps")
    packet_loss_rate: float = Field(..., ge=0, le=1, description="Packet loss rate")
    jitter_ms: int = Field(..., ge=0, description="Jitter in milliseconds")


class NodeRegistration(BaseModel):
    """Register a new mesh node"""
    aura_id: str
    node_address: str
    node_type: str = Field(default="peer", description="Node type: peer, relay, edge, super_node")
    region: Optional[str] = None
    country_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    supports_aic_protocol: bool = False


class NodeHeartbeat(BaseModel):
    """Node heartbeat update"""
    node_id: str
    current_connections: int
    current_bandwidth_usage_mbps: int
    avg_latency_ms: float
    packet_loss_rate: float


# API Endpoints

@router.post("/routes/find-optimal", response_model=RouteResponse, status_code=status.HTTP_200_OK)
async def find_optimal_route(
    request: RouteRequest,
    db_pool=Depends(get_db_pool),
    current_user=Depends(get_current_user)
):
    """
    Find optimal route between two AuraIDs using AI optimization
    
    This endpoint uses AI to predict the best path through the mesh network,
    considering factors like latency, bandwidth, node reputation, and network conditions.
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
                detail=f"No route found between {request.source_aura_id} and {request.destination_aura_id}"
            )
        
        return route
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find optimal route: {str(e)}"
        )


@router.put("/routes/{route_id}/performance", status_code=status.HTTP_200_OK)
async def update_route_performance(
    route_id: str,
    performance: RoutePerformanceUpdate,
    db_pool=Depends(get_db_pool),
    current_user=Depends(get_current_user)
):
    """
    Update route with actual performance metrics
    
    This data is used to improve AI predictions and route selection over time.
    """
    try:
        routing_service = MeshRoutingService(db_pool)
        
        await routing_service.update_route_performance(
            route_id=route_id,
            actual_latency_ms=performance.actual_latency_ms,
            actual_bandwidth_mbps=performance.actual_bandwidth_mbps,
            packet_loss_rate=performance.packet_loss_rate,
            jitter_ms=performance.jitter_ms
        )
        
        return {
            "route_id": route_id,
            "message": "Performance metrics updated successfully",
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update route performance: {str(e)}"
        )


@router.get("/routes/analytics", status_code=status.HTTP_200_OK)
async def get_route_analytics(
    time_range_hours: int = 24,
    db_pool=Depends(get_db_pool),
    current_user=Depends(get_current_user)
):
    """
    Get analytics for mesh routing performance
    
    Provides insights into AI prediction accuracy and route quality.
    """
    try:
        routing_service = MeshRoutingService(db_pool)
        
        analytics = await routing_service.get_route_analytics(time_range_hours)
        
        return {
            "time_range_hours": time_range_hours,
            "analytics": analytics,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get route analytics: {str(e)}"
        )


@router.post("/nodes/register", status_code=status.HTTP_201_CREATED)
async def register_mesh_node(
    node: NodeRegistration,
    db_pool=Depends(get_db_pool),
    current_user=Depends(get_current_user)
):
    """
    Register a new mesh node
    
    Nodes can be peers, relays, edge nodes, or super nodes.
    """
    try:
        async with db_pool.acquire() as conn:
            node_id = await conn.fetchval("""
                INSERT INTO mesh_nodes (
                    aura_id, node_address, node_type, region, country_code,
                    latitude, longitude, supports_aic_protocol,
                    is_online, is_accepting_connections
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING node_id
            """,
                node.aura_id,
                node.node_address,
                node.node_type,
                node.region,
                node.country_code,
                node.latitude,
                node.longitude,
                node.supports_aic_protocol,
                True,  # is_online
                True   # is_accepting_connections
            )
            
            return {
                "node_id": str(node_id),
                "aura_id": node.aura_id,
                "node_type": node.node_type,
                "message": "Node registered successfully",
                "registered_at": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register node: {str(e)}"
        )


@router.post("/nodes/heartbeat", status_code=status.HTTP_200_OK)
async def node_heartbeat(
    heartbeat: NodeHeartbeat,
    db_pool=Depends(get_db_pool),
    current_user=Depends(get_current_user)
):
    """
    Update node heartbeat and metrics
    
    Nodes should send heartbeats every 30 seconds to maintain online status.
    """
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE mesh_nodes
                SET 
                    current_connections = $2,
                    current_bandwidth_usage_mbps = $3,
                    avg_latency_ms = $4,
                    packet_loss_rate = $5,
                    last_heartbeat_at = NOW(),
                    is_online = TRUE,
                    updated_at = NOW()
                WHERE node_id = $1
            """,
                heartbeat.node_id,
                heartbeat.current_connections,
                heartbeat.current_bandwidth_usage_mbps,
                heartbeat.avg_latency_ms,
                heartbeat.packet_loss_rate
            )
            
            return {
                "node_id": heartbeat.node_id,
                "message": "Heartbeat received",
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process heartbeat: {str(e)}"
        )


@router.get("/nodes/{node_id}", status_code=status.HTTP_200_OK)
async def get_node_info(
    node_id: str,
    db_pool=Depends(get_db_pool),
    current_user=Depends(get_current_user)
):
    """Get information about a specific mesh node"""
    try:
        async with db_pool.acquire() as conn:
            node = await conn.fetchrow("""
                SELECT 
                    node_id, aura_id, node_address, node_type, region, country_code,
                    latitude, longitude, avg_latency_ms, packet_loss_rate,
                    uptime_percentage, reputation_score, trust_level,
                    current_connections, max_connections, 
                    bandwidth_capacity_mbps, current_bandwidth_usage_mbps,
                    is_online, is_accepting_connections, supports_aic_protocol,
                    last_heartbeat_at, created_at, updated_at
                FROM mesh_nodes
                WHERE node_id = $1
            """, node_id)
            
            if not node:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Node {node_id} not found"
                )
            
            return dict(node)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get node info: {str(e)}"
        )


@router.get("/nodes/aura/{aura_id}", status_code=status.HTTP_200_OK)
async def get_nodes_by_aura_id(
    aura_id: str,
    db_pool=Depends(get_db_pool),
    current_user=Depends(get_current_user)
):
    """Get all mesh nodes for a specific AuraID"""
    try:
        async with db_pool.acquire() as conn:
            nodes = await conn.fetch("""
                SELECT 
                    node_id, aura_id, node_address, node_type, region,
                    is_online, reputation_score, trust_level,
                    current_connections, max_connections,
                    supports_aic_protocol, last_heartbeat_at
                FROM mesh_nodes
                WHERE aura_id = $1
                ORDER BY is_online DESC, reputation_score DESC
            """, aura_id)
            
            return {
                "aura_id": aura_id,
                "nodes": [dict(node) for node in nodes],
                "count": len(nodes)
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get nodes: {str(e)}"
        )


@router.get("/network/status", status_code=status.HTTP_200_OK)
async def get_network_status(
    db_pool=Depends(get_db_pool),
    current_user=Depends(get_current_user)
):
    """Get overall mesh network status and statistics"""
    try:
        async with db_pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_nodes,
                    COUNT(*) FILTER (WHERE is_online = TRUE) as online_nodes,
                    COUNT(*) FILTER (WHERE trust_level = 'verified') as verified_nodes,
                    COUNT(*) FILTER (WHERE trust_level = 'trusted') as trusted_nodes,
                    AVG(reputation_score) as avg_reputation,
                    AVG(avg_latency_ms) FILTER (WHERE is_online = TRUE) as avg_network_latency,
                    SUM(current_connections) as total_active_connections,
                    COUNT(*) FILTER (WHERE supports_aic_protocol = TRUE) as aic_enabled_nodes
                FROM mesh_nodes
            """)
            
            route_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_routes,
                    COUNT(*) FILTER (WHERE is_optimal = TRUE) as optimal_routes,
                    AVG(ai_score) as avg_ai_score,
                    AVG(success_rate) as avg_success_rate
                FROM mesh_routes
                WHERE created_at >= NOW() - INTERVAL '24 hours'
            """)
            
            return {
                "network_stats": dict(stats) if stats else {},
                "route_stats": dict(route_stats) if route_stats else {},
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get network status: {str(e)}"
        )


@router.delete("/nodes/{node_id}", status_code=status.HTTP_200_OK)
async def deregister_node(
    node_id: str,
    db_pool=Depends(get_db_pool),
    current_user=Depends(get_current_user)
):
    """Deregister a mesh node (mark as offline)"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE mesh_nodes
                SET 
                    is_online = FALSE,
                    is_accepting_connections = FALSE,
                    updated_at = NOW()
                WHERE node_id = $1
            """, node_id)
            
            return {
                "node_id": node_id,
                "message": "Node deregistered successfully",
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deregister node: {str(e)}"
        )
