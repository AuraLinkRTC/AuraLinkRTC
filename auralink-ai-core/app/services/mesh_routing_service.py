"""
Mesh Routing Service with AI-Optimized Path Selection
Phase 6: AuraID & Mesh Network
"""

import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MeshNode:
    """Represents a mesh network node"""
    node_id: str
    aura_id: str
    node_address: str
    node_type: str
    region: str
    country_code: str
    latitude: float
    longitude: float
    avg_latency_ms: float
    packet_loss_rate: float
    uptime_percentage: float
    reputation_score: float
    trust_level: str
    current_connections: int
    max_connections: int
    bandwidth_capacity_mbps: int
    current_bandwidth_usage_mbps: int
    is_online: bool
    supports_aic_protocol: bool


@dataclass
class RouteCandidate:
    """Represents a potential route"""
    path_nodes: List[str]
    predicted_latency_ms: int
    predicted_bandwidth_mbps: int
    ai_score: float
    trust_score: float
    path_length: int


class MeshRoutingService:
    """AI-powered mesh network routing optimization"""
    
    def __init__(self, db_pool):
        self.db = db_pool
        self.route_cache = {}
        self.cache_ttl = 300  # 5 minutes
        
        # AI model weights for route scoring (learned from historical data)
        self.weights = {
            'latency': -0.40,      # Lower is better
            'bandwidth': 0.25,     # Higher is better
            'reputation': 0.15,    # Higher is better
            'hop_count': -0.10,    # Lower is better
            'aic_support': 0.05,   # Bonus for AIC support
            'uptime': 0.05         # Higher is better
        }
    
    async def find_optimal_route(
        self, 
        source_aura_id: str, 
        destination_aura_id: str,
        media_type: str = "audio_video",
        require_aic: bool = False
    ) -> Optional[Dict]:
        """
        Find optimal route between two AuraIDs using AI prediction
        
        Args:
            source_aura_id: Source AuraID
            destination_aura_id: Destination AuraID
            media_type: Type of media (audio, video, audio_video)
            require_aic: Whether AIC Protocol support is required
            
        Returns:
            Optimal route information or None
        """
        try:
            # Check cache first
            cache_key = f"{source_aura_id}:{destination_aura_id}:{media_type}"
            if cache_key in self.route_cache:
                cached_route, cached_time = self.route_cache[cache_key]
                if (datetime.now() - cached_time).seconds < self.cache_ttl:
                    logger.info(f"Returning cached route for {cache_key}")
                    return cached_route
            
            # Get source and destination nodes
            source_nodes = await self._get_nodes_for_aura_id(source_aura_id)
            dest_nodes = await self._get_nodes_for_aura_id(destination_aura_id)
            
            if not source_nodes or not dest_nodes:
                logger.warning(f"No nodes found for route: {source_aura_id} -> {destination_aura_id}")
                return None
            
            # Select best source and destination nodes
            source_node = self._select_best_node(source_nodes, require_aic)
            dest_node = self._select_best_node(dest_nodes, require_aic)
            
            if not source_node or not dest_node:
                return None
            
            # Check if direct connection is possible
            if await self._can_connect_directly(source_node, dest_node):
                route = await self._create_direct_route(source_node, dest_node, media_type)
            else:
                # Find best path through relay nodes
                route = await self._find_relay_route(source_node, dest_node, media_type, require_aic)
            
            if route:
                # Cache the route
                self.route_cache[cache_key] = (route, datetime.now())
                
                # Store in database for analytics
                await self._store_route(route, source_aura_id, destination_aura_id)
            
            return route
            
        except Exception as e:
            logger.error(f"Error finding optimal route: {e}")
            return None
    
    async def _get_nodes_for_aura_id(self, aura_id: str) -> List[MeshNode]:
        """Get all active nodes for a given AuraID"""
        async with self.db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    node_id, aura_id, node_address, node_type, region, country_code,
                    latitude, longitude, avg_latency_ms, packet_loss_rate, uptime_percentage,
                    reputation_score, trust_level, current_connections, max_connections,
                    bandwidth_capacity_mbps, current_bandwidth_usage_mbps, 
                    is_online, supports_aic_protocol
                FROM mesh_nodes
                WHERE aura_id = $1 AND is_online = TRUE AND is_accepting_connections = TRUE
                ORDER BY reputation_score DESC, avg_latency_ms ASC
            """, aura_id)
            
            return [MeshNode(**dict(row)) for row in rows]
    
    def _select_best_node(self, nodes: List[MeshNode], require_aic: bool) -> Optional[MeshNode]:
        """Select the best node from a list based on multiple factors"""
        if require_aic:
            nodes = [n for n in nodes if n.supports_aic_protocol]
        
        if not nodes:
            return None
        
        # Score each node
        scored_nodes = []
        for node in nodes:
            # Check capacity
            if node.current_connections >= node.max_connections:
                continue
            
            # Calculate composite score
            score = (
                node.reputation_score * 0.4 +
                (100 - node.avg_latency_ms / 10) * 0.3 +
                (100 - node.packet_loss_rate * 1000) * 0.2 +
                node.uptime_percentage * 0.1
            )
            
            scored_nodes.append((node, score))
        
        if not scored_nodes:
            return nodes[0]  # Fallback to first node
        
        # Return node with highest score
        scored_nodes.sort(key=lambda x: x[1], reverse=True)
        return scored_nodes[0][0]
    
    async def _can_connect_directly(self, source: MeshNode, dest: MeshNode) -> bool:
        """Check if two nodes can connect directly (P2P)"""
        # Check if both nodes are in same region (better for P2P)
        if source.region == dest.region:
            return True
        
        # Calculate distance
        distance = self._calculate_distance(
            source.latitude, source.longitude,
            dest.latitude, dest.longitude
        )
        
        # Direct connection possible if distance < 5000km and good network conditions
        if distance < 5000 and source.packet_loss_rate < 0.01 and dest.packet_loss_rate < 0.01:
            return True
        
        return False
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two coordinates in km (Haversine formula)"""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Earth's radius in km
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    async def _create_direct_route(
        self, 
        source: MeshNode, 
        dest: MeshNode,
        media_type: str
    ) -> Dict:
        """Create a direct P2P route"""
        # Predict latency and bandwidth
        base_latency = source.avg_latency_ms + dest.avg_latency_ms
        predicted_latency = int(base_latency * 1.1)  # Add 10% overhead
        
        available_bandwidth = min(
            source.bandwidth_capacity_mbps - source.current_bandwidth_usage_mbps,
            dest.bandwidth_capacity_mbps - dest.current_bandwidth_usage_mbps
        )
        
        # Calculate AI score
        ai_score = self._calculate_ai_score(
            predicted_latency,
            available_bandwidth,
            (source.reputation_score + dest.reputation_score) / 2,
            1,  # Direct route, hop count = 1
            source.uptime_percentage,
            source.supports_aic_protocol and dest.supports_aic_protocol
        )
        
        return {
            "route_id": None,  # Will be assigned when stored
            "source_node_id": source.node_id,
            "destination_node_id": dest.node_id,
            "path_nodes": [source.node_id, dest.node_id],
            "path_length": 1,
            "route_type": "direct_p2p",
            "predicted_latency_ms": predicted_latency,
            "predicted_bandwidth_mbps": available_bandwidth,
            "ai_score": ai_score,
            "is_optimal": True,
            "supports_aic": source.supports_aic_protocol and dest.supports_aic_protocol,
            "media_type": media_type,
            "optimization_factors": {
                "direct_connection": True,
                "same_region": source.region == dest.region,
                "trust_score": (source.reputation_score + dest.reputation_score) / 2
            }
        }
    
    async def _find_relay_route(
        self,
        source: MeshNode,
        dest: MeshNode,
        media_type: str,
        require_aic: bool
    ) -> Optional[Dict]:
        """Find best route through relay nodes using AI optimization"""
        # Get potential relay nodes
        relay_nodes = await self._get_relay_nodes(source, dest, require_aic)
        
        if not relay_nodes:
            # No relay nodes available, try direct anyway
            return await self._create_direct_route(source, dest, media_type)
        
        # Generate route candidates
        candidates = []
        
        # Single relay routes
        for relay in relay_nodes[:10]:  # Top 10 relay nodes
            candidate = await self._evaluate_route_candidate(
                [source.node_id, relay['node_id'], dest.node_id],
                [source, relay, dest],
                media_type
            )
            if candidate:
                candidates.append(candidate)
        
        # Two relay routes (if needed for better path)
        if len(relay_nodes) >= 2:
            for i, relay1 in enumerate(relay_nodes[:5]):
                for relay2 in relay_nodes[i+1:6]:
                    # Ensure geographical progression
                    if self._is_geographically_progressive(source, relay1, relay2, dest):
                        candidate = await self._evaluate_route_candidate(
                            [source.node_id, relay1['node_id'], relay2['node_id'], dest.node_id],
                            [source, relay1, relay2, dest],
                            media_type
                        )
                        if candidate:
                            candidates.append(candidate)
        
        if not candidates:
            return None
        
        # Select best candidate based on AI score
        best_candidate = max(candidates, key=lambda x: x['ai_score'])
        
        return {
            "route_id": None,
            "source_node_id": source.node_id,
            "destination_node_id": dest.node_id,
            "path_nodes": best_candidate['path_nodes'],
            "path_length": len(best_candidate['path_nodes']) - 1,
            "route_type": "relay",
            "predicted_latency_ms": best_candidate['predicted_latency_ms'],
            "predicted_bandwidth_mbps": best_candidate['predicted_bandwidth_mbps'],
            "ai_score": best_candidate['ai_score'],
            "is_optimal": True,
            "supports_aic": best_candidate.get('supports_aic', False),
            "media_type": media_type,
            "optimization_factors": best_candidate.get('optimization_factors', {})
        }
    
    async def _get_relay_nodes(
        self,
        source: MeshNode,
        dest: MeshNode,
        require_aic: bool
    ) -> List[Dict]:
        """Get suitable relay nodes for routing"""
        async with self.db.acquire() as conn:
            query = """
                SELECT 
                    node_id, aura_id, node_address, node_type, region, country_code,
                    latitude, longitude, avg_latency_ms, packet_loss_rate, 
                    reputation_score, trust_level, current_connections, max_connections,
                    bandwidth_capacity_mbps, current_bandwidth_usage_mbps,
                    supports_aic_protocol
                FROM mesh_nodes
                WHERE 
                    is_online = TRUE 
                    AND is_accepting_connections = TRUE
                    AND node_type IN ('relay', 'super_node', 'edge')
                    AND trust_level IN ('trusted', 'verified')
                    AND reputation_score >= 70
                    AND current_connections < max_connections * 0.8
                    AND node_id != $1 AND node_id != $2
            """
            
            params = [source.node_id, dest.node_id]
            
            if require_aic:
                query += " AND supports_aic_protocol = TRUE"
            
            query += """
                ORDER BY 
                    reputation_score DESC,
                    avg_latency_ms ASC,
                    (max_connections - current_connections) DESC
                LIMIT 20
            """
            
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    def _is_geographically_progressive(
        self,
        source: MeshNode,
        relay1: Dict,
        relay2: Dict,
        dest: MeshNode
    ) -> bool:
        """Check if relay nodes form a geographically progressive path"""
        # Calculate distances
        d_source_relay1 = self._calculate_distance(
            source.latitude, source.longitude,
            relay1['latitude'], relay1['longitude']
        )
        d_relay1_relay2 = self._calculate_distance(
            relay1['latitude'], relay1['longitude'],
            relay2['latitude'], relay2['longitude']
        )
        d_relay2_dest = self._calculate_distance(
            relay2['latitude'], relay2['longitude'],
            dest.latitude, dest.longitude
        )
        
        # Check if distances are reasonable (not backtracking significantly)
        total_relay_distance = d_source_relay1 + d_relay1_relay2 + d_relay2_dest
        direct_distance = self._calculate_distance(
            source.latitude, source.longitude,
            dest.latitude, dest.longitude
        )
        
        # Allow up to 50% overhead in distance
        return total_relay_distance <= direct_distance * 1.5
    
    async def _evaluate_route_candidate(
        self,
        path_node_ids: List[str],
        path_nodes: List,
        media_type: str
    ) -> Optional[Dict]:
        """Evaluate a route candidate and calculate metrics"""
        try:
            # Calculate cumulative latency
            total_latency = sum(
                node.get('avg_latency_ms', node.avg_latency_ms if hasattr(node, 'avg_latency_ms') else 0) 
                for node in path_nodes
            )
            
            # Add inter-node latency (estimate based on distance)
            for i in range(len(path_nodes) - 1):
                node1 = path_nodes[i]
                node2 = path_nodes[i + 1]
                
                lat1 = node1.get('latitude', node1.latitude if hasattr(node1, 'latitude') else 0)
                lon1 = node1.get('longitude', node1.longitude if hasattr(node1, 'longitude') else 0)
                lat2 = node2.get('latitude', node2.latitude if hasattr(node2, 'latitude') else 0)
                lon2 = node2.get('longitude', node2.longitude if hasattr(node2, 'longitude') else 0)
                
                distance = self._calculate_distance(lat1, lon1, lat2, lon2)
                # Estimate 1ms per 200km
                total_latency += distance / 200
            
            # Calculate minimum available bandwidth (bottleneck)
            min_bandwidth = min(
                node.get('bandwidth_capacity_mbps', node.bandwidth_capacity_mbps if hasattr(node, 'bandwidth_capacity_mbps') else 100) -
                node.get('current_bandwidth_usage_mbps', node.current_bandwidth_usage_mbps if hasattr(node, 'current_bandwidth_usage_mbps') else 0)
                for node in path_nodes
            )
            
            # Calculate average reputation
            avg_reputation = np.mean([
                node.get('reputation_score', node.reputation_score if hasattr(node, 'reputation_score') else 50)
                for node in path_nodes
            ])
            
            # Calculate average uptime
            avg_uptime = np.mean([
                node.get('uptime_percentage', getattr(node, 'uptime_percentage', 100))
                for node in path_nodes
            ])
            
            # Check AIC support
            supports_aic = all(
                node.get('supports_aic_protocol', getattr(node, 'supports_aic_protocol', False))
                for node in path_nodes
            )
            
            # Calculate AI score
            ai_score = self._calculate_ai_score(
                total_latency,
                min_bandwidth,
                avg_reputation,
                len(path_nodes) - 1,  # Hop count
                avg_uptime,
                supports_aic
            )
            
            return {
                "path_nodes": path_node_ids,
                "predicted_latency_ms": int(total_latency),
                "predicted_bandwidth_mbps": int(min_bandwidth),
                "ai_score": ai_score,
                "supports_aic": supports_aic,
                "optimization_factors": {
                    "avg_reputation": float(avg_reputation),
                    "avg_uptime": float(avg_uptime),
                    "hop_count": len(path_nodes) - 1
                }
            }
            
        except Exception as e:
            logger.error(f"Error evaluating route candidate: {e}")
            return None
    
    def _calculate_ai_score(
        self,
        latency_ms: float,
        bandwidth_mbps: float,
        reputation: float,
        hop_count: int,
        uptime: float,
        aic_support: bool
    ) -> float:
        """
        Calculate AI-based route score (0-100)
        
        Uses weighted factors to predict route quality
        """
        # Normalize inputs to 0-100 scale
        latency_score = max(0, 100 - (latency_ms / 5))  # 0-500ms range
        bandwidth_score = min(100, bandwidth_mbps * 2)   # 0-50 Mbps range
        reputation_score = reputation  # Already 0-100
        hop_score = max(0, 100 - (hop_count * 20))  # Penalize multiple hops
        uptime_score = uptime  # Already 0-100
        aic_bonus = 10 if aic_support else 0
        
        # Calculate weighted score
        score = (
            latency_score * abs(self.weights['latency']) +
            bandwidth_score * self.weights['bandwidth'] +
            reputation_score * self.weights['reputation'] +
            hop_score * abs(self.weights['hop_count']) +
            uptime_score * self.weights['uptime'] +
            aic_bonus
        )
        
        return min(100.0, max(0.0, score))
    
    async def _store_route(self, route: Dict, source_aura_id: str, dest_aura_id: str):
        """Store route in database for analytics"""
        try:
            async with self.db.acquire() as conn:
                route_id = await conn.fetchval("""
                    INSERT INTO mesh_routes (
                        source_node_id, destination_node_id, path_nodes, path_length,
                        ai_score, predicted_latency_ms, predicted_bandwidth_mbps,
                        optimization_factors, is_optimal, expires_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    RETURNING route_id
                """,
                    route['source_node_id'],
                    route['destination_node_id'],
                    route['path_nodes'],
                    route['path_length'],
                    route['ai_score'],
                    route['predicted_latency_ms'],
                    route['predicted_bandwidth_mbps'],
                    route['optimization_factors'],
                    route['is_optimal'],
                    datetime.now() + timedelta(minutes=10)
                )
                
                route['route_id'] = str(route_id)
                
                logger.info(f"Stored route {route_id}: {source_aura_id} -> {dest_aura_id}")
                
        except Exception as e:
            logger.error(f"Error storing route: {e}")
    
    async def update_route_performance(
        self,
        route_id: str,
        actual_latency_ms: int,
        actual_bandwidth_mbps: int,
        packet_loss_rate: float,
        jitter_ms: int
    ):
        """Update route with actual performance metrics for ML learning"""
        try:
            async with self.db.acquire() as conn:
                await conn.execute("""
                    UPDATE mesh_routes
                    SET 
                        actual_latency_ms = $2,
                        actual_bandwidth_mbps = $3,
                        packet_loss_rate = $4,
                        jitter_ms = $5,
                        usage_count = usage_count + 1,
                        last_used_at = NOW(),
                        updated_at = NOW()
                    WHERE route_id = $1
                """, route_id, actual_latency_ms, actual_bandwidth_mbps, packet_loss_rate, jitter_ms)
                
                # Update success rate
                await conn.execute("""
                    UPDATE mesh_routes
                    SET success_rate = (
                        SELECT COUNT(*) * 100.0 / GREATEST(usage_count, 1)
                        FROM mesh_routes
                        WHERE route_id = $1 AND packet_loss_rate < 0.05
                    )
                    WHERE route_id = $1
                """, route_id)
                
                logger.info(f"Updated route performance: {route_id}")
                
        except Exception as e:
            logger.error(f"Error updating route performance: {e}")
    
    async def get_route_analytics(self, time_range_hours: int = 24) -> Dict:
        """Get analytics for mesh routing"""
        try:
            async with self.db.acquire() as conn:
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_routes,
                        COUNT(*) FILTER (WHERE is_optimal = TRUE) as optimal_routes,
                        AVG(ai_score) as avg_ai_score,
                        AVG(predicted_latency_ms) as avg_predicted_latency,
                        AVG(actual_latency_ms) as avg_actual_latency,
                        AVG(ABS(predicted_latency_ms - actual_latency_ms)) as avg_prediction_error,
                        AVG(success_rate) as avg_success_rate
                    FROM mesh_routes
                    WHERE created_at >= NOW() - INTERVAL '$1 hours'
                """, time_range_hours)
                
                return dict(stats) if stats else {}
                
        except Exception as e:
            logger.error(f"Error getting route analytics: {e}")
            return {}
