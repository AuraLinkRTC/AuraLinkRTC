"""
AuraLink Trust and Reputation Service
Phase 6: AuraID & Mesh Network
Enterprise-grade reputation scoring and trust management
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ReputationEvent:
    """Represents a reputation event"""
    event_type: str
    severity: str
    reputation_change: float
    description: str
    evidence: Dict


class ReputationService:
    """
    Manages node reputation and trust levels
    
    This service uses multiple factors to calculate reputation scores:
    - Call quality metrics
    - Uptime and reliability
    - Abuse reports
    - Community feedback
    - Historical performance
    """
    
    def __init__(self, db_pool):
        self.db = db_pool
        
        # Reputation change weights by event type
        self.event_weights = {
            # Positive events
            'successful_call': 1.0,
            'high_quality_stream': 2.0,
            'helped_relay': 1.5,
            'verified_identity': 5.0,
            'community_contribution': 3.0,
            'consistent_uptime': 2.0,
            
            # Negative events
            'call_dropped': -2.0,
            'poor_quality': -1.5,
            'connection_timeout': -1.0,
            'excessive_latency': -0.5,
            'bandwidth_throttling': -3.0,
            'abuse_report': -5.0,
            'spam_detected': -10.0,
            'malicious_behavior': -20.0,
            'security_violation': -25.0,
        }
        
        # Trust level thresholds
        self.trust_thresholds = {
            'verified': 90,
            'trusted': 70,
            'new': 30,
            'suspicious': 10,
            'banned': 0
        }
    
    async def update_node_reputation(
        self,
        node_id: str,
        event_type: str,
        description: str = None,
        evidence: Dict = None,
        severity: str = 'info'
    ) -> Dict:
        """
        Update node reputation based on an event
        
        Args:
            node_id: UUID of the mesh node
            event_type: Type of event (from event_weights keys)
            description: Human-readable description
            evidence: Additional evidence/metadata
            severity: Event severity (info, warning, critical)
            
        Returns:
            Updated reputation information
        """
        try:
            reputation_change = self.event_weights.get(event_type, 0.0)
            
            # Adjust based on severity
            if severity == 'critical':
                reputation_change *= 2.0
            elif severity == 'warning':
                reputation_change *= 1.5
            
            async with self.db.acquire() as conn:
                # Call database function to update reputation
                result = await conn.fetchrow("""
                    SELECT update_node_reputation($1, $2, $3, $4)
                """, node_id, event_type, reputation_change, description)
                
                # Get updated node info
                node_info = await conn.fetchrow("""
                    SELECT 
                        node_id,
                        aura_id,
                        reputation_score,
                        trust_level,
                        updated_at
                    FROM mesh_nodes
                    WHERE node_id = $1
                """, node_id)
                
                if not node_info:
                    raise ValueError(f"Node {node_id} not found")
                
                # Check if trust level changed
                new_trust_level = self._calculate_trust_level(node_info['reputation_score'])
                if new_trust_level != node_info['trust_level']:
                    await self._handle_trust_level_change(
                        conn,
                        node_id,
                        node_info['trust_level'],
                        new_trust_level
                    )
                
                logger.info(
                    f"Reputation updated for node {node_id}: "
                    f"{event_type} ({reputation_change:+.1f}) -> "
                    f"score: {node_info['reputation_score']:.1f}, "
                    f"trust: {node_info['trust_level']}"
                )
                
                return {
                    'node_id': str(node_info['node_id']),
                    'aura_id': node_info['aura_id'],
                    'reputation_score': float(node_info['reputation_score']),
                    'trust_level': node_info['trust_level'],
                    'reputation_change': reputation_change,
                    'event_type': event_type
                }
                
        except Exception as e:
            logger.error(f"Error updating reputation: {e}")
            raise
    
    def _calculate_trust_level(self, reputation_score: float) -> str:
        """Calculate trust level from reputation score"""
        if reputation_score >= self.trust_thresholds['verified']:
            return 'verified'
        elif reputation_score >= self.trust_thresholds['trusted']:
            return 'trusted'
        elif reputation_score >= self.trust_thresholds['new']:
            return 'new'
        elif reputation_score >= self.trust_thresholds['suspicious']:
            return 'suspicious'
        else:
            return 'banned'
    
    async def _handle_trust_level_change(
        self,
        conn,
        node_id: str,
        old_level: str,
        new_level: str
    ):
        """Handle trust level changes (notifications, actions, etc.)"""
        logger.info(f"Trust level changed for node {node_id}: {old_level} -> {new_level}")
        
        # Take action based on new trust level
        if new_level == 'banned':
            # Automatically suspend node
            await conn.execute("""
                UPDATE mesh_nodes
                SET is_accepting_connections = FALSE
                WHERE node_id = $1
            """, node_id)
            logger.warning(f"Node {node_id} banned and suspended")
            
        elif new_level == 'suspicious':
            # Flag for review
            await conn.execute("""
                INSERT INTO node_reputation_events (
                    node_id, event_type, event_severity, description
                ) VALUES ($1, $2, $3, $4)
            """, node_id, 'trust_level_downgrade', 'warning',
                f"Node trust level downgraded to suspicious")
            
        elif new_level == 'verified' and old_level != 'verified':
            # Celebrate upgrade to verified
            await conn.execute("""
                INSERT INTO node_reputation_events (
                    node_id, event_type, event_severity, description
                ) VALUES ($1, $2, $3, $4)
            """, node_id, 'trust_level_upgrade', 'info',
                f"Node achieved verified trust level")
    
    async def calculate_aggregate_reputation(
        self,
        node_id: str,
        time_range_hours: int = 168  # Last 7 days
    ) -> Dict:
        """
        Calculate aggregate reputation metrics for a node
        
        Returns detailed breakdown of reputation factors
        """
        try:
            async with self.db.acquire() as conn:
                # Get call quality metrics
                call_metrics = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) FILTER (WHERE fc.call_status = 'connected') as successful_calls,
                        COUNT(*) FILTER (WHERE fc.call_status = 'failed') as failed_calls,
                        AVG(fc.quality_score) as avg_call_quality,
                        AVG(fc.avg_latency_ms) as avg_latency
                    FROM federated_calls fc
                    WHERE 
                        (fc.bridge_node_id = $1 OR $1 = ANY(fc.routing_path))
                        AND fc.initiated_at >= NOW() - INTERVAL '$2 hours'
                """, node_id, time_range_hours)
                
                # Get relay performance
                relay_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_relays,
                        AVG(mr.success_rate) as avg_success_rate,
                        AVG(ABS(mr.predicted_latency_ms - mr.actual_latency_ms)) as avg_prediction_error
                    FROM mesh_routes mr
                    WHERE 
                        $1 = ANY(mr.path_nodes)
                        AND mr.created_at >= NOW() - INTERVAL '$2 hours'
                """, node_id, time_range_hours)
                
                # Get abuse reports
                abuse_count = await conn.fetchval("""
                    SELECT COUNT(*)
                    FROM abuse_reports
                    WHERE 
                        reported_node_id = $1
                        AND created_at >= NOW() - INTERVAL '$2 hours'
                        AND status != 'dismissed'
                """, node_id, time_range_hours)
                
                # Get uptime
                node_uptime = await conn.fetchval("""
                    SELECT uptime_percentage
                    FROM mesh_nodes
                    WHERE node_id = $1
                """, node_id)
                
                # Calculate component scores
                call_quality_score = self._calculate_call_quality_score(call_metrics)
                relay_performance_score = self._calculate_relay_score(relay_stats)
                abuse_penalty = min(abuse_count * 5, 30)  # Max 30 point penalty
                uptime_score = node_uptime or 100.0
                
                # Calculate weighted aggregate
                aggregate_score = (
                    call_quality_score * 0.35 +
                    relay_performance_score * 0.25 +
                    uptime_score * 0.20 +
                    (100 - abuse_penalty) * 0.20
                )
                
                return {
                    'aggregate_score': round(aggregate_score, 2),
                    'components': {
                        'call_quality': round(call_quality_score, 2),
                        'relay_performance': round(relay_performance_score, 2),
                        'uptime': round(uptime_score, 2),
                        'abuse_score': round(100 - abuse_penalty, 2)
                    },
                    'metrics': {
                        'successful_calls': call_metrics['successful_calls'] or 0,
                        'failed_calls': call_metrics['failed_calls'] or 0,
                        'avg_call_quality': float(call_metrics['avg_call_quality'] or 0),
                        'total_relays': relay_stats['total_relays'] or 0,
                        'abuse_reports': abuse_count,
                        'uptime_percentage': float(uptime_score)
                    },
                    'time_range_hours': time_range_hours
                }
                
        except Exception as e:
            logger.error(f"Error calculating aggregate reputation: {e}")
            return {}
    
    def _calculate_call_quality_score(self, metrics: Dict) -> float:
        """Calculate score from call quality metrics"""
        if not metrics or not metrics['successful_calls']:
            return 50.0  # Neutral score for new nodes
        
        success_rate = metrics['successful_calls'] / (
            metrics['successful_calls'] + metrics['failed_calls']
        ) if metrics['failed_calls'] else 1.0
        
        quality_score = metrics['avg_call_quality'] or 0.0
        latency_score = max(0, 100 - (metrics['avg_latency'] or 0) / 10)
        
        return (success_rate * 100 * 0.5 + quality_score * 0.3 + latency_score * 0.2)
    
    def _calculate_relay_score(self, stats: Dict) -> float:
        """Calculate score from relay performance"""
        if not stats or not stats['total_relays']:
            return 50.0  # Neutral score
        
        success_rate = stats['avg_success_rate'] or 0.0
        prediction_accuracy = max(0, 100 - (stats['avg_prediction_error'] or 0))
        
        return (success_rate * 0.7 + prediction_accuracy * 0.3)
    
    async def process_abuse_report(
        self,
        reporter_aura_id: str,
        reported_node_id: str,
        report_type: str,
        severity: str,
        description: str,
        evidence: Dict = None
    ) -> Dict:
        """
        Process an abuse report and update reputation accordingly
        
        Args:
            reporter_aura_id: AuraID of reporter
            reported_node_id: Node ID being reported
            report_type: Type of abuse (spam, harassment, malicious_node, etc.)
            severity: low, medium, high, critical
            description: Description of the issue
            evidence: Supporting evidence
            
        Returns:
            Report information
        """
        try:
            async with self.db.acquire() as conn:
                # Create abuse report
                report_id = await conn.fetchval("""
                    INSERT INTO abuse_reports (
                        reporter_aura_id, reported_node_id, report_type, severity,
                        description, evidence, status
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING report_id
                """, reporter_aura_id, reported_node_id, report_type, severity,
                    description, evidence or {}, 'pending')
                
                # Immediate reputation impact for severe reports
                if severity in ['high', 'critical']:
                    await self.update_node_reputation(
                        reported_node_id,
                        'abuse_report' if severity == 'high' else 'malicious_behavior',
                        description=f"Abuse report filed: {report_type}",
                        evidence=evidence,
                        severity=severity
                    )
                
                logger.info(
                    f"Abuse report {report_id} filed against node {reported_node_id}: "
                    f"{report_type} ({severity})"
                )
                
                return {
                    'report_id': str(report_id),
                    'status': 'pending',
                    'message': 'Report submitted successfully and is under review'
                }
                
        except Exception as e:
            logger.error(f"Error processing abuse report: {e}")
            raise
    
    async def get_node_reputation_history(
        self,
        node_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """Get reputation event history for a node"""
        try:
            async with self.db.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        event_id,
                        event_type,
                        event_severity,
                        reputation_change,
                        previous_score,
                        new_score,
                        description,
                        created_at
                    FROM node_reputation_events
                    WHERE node_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """, node_id, limit)
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting reputation history: {e}")
            return []
    
    async def get_trust_distribution(self) -> Dict:
        """Get distribution of nodes across trust levels"""
        try:
            async with self.db.acquire() as conn:
                distribution = await conn.fetch("""
                    SELECT 
                        trust_level,
                        COUNT(*) as node_count,
                        AVG(reputation_score) as avg_reputation
                    FROM mesh_nodes
                    WHERE is_online = TRUE
                    GROUP BY trust_level
                    ORDER BY 
                        CASE trust_level
                            WHEN 'verified' THEN 1
                            WHEN 'trusted' THEN 2
                            WHEN 'new' THEN 3
                            WHEN 'suspicious' THEN 4
                            WHEN 'banned' THEN 5
                        END
                """)
                
                return {
                    row['trust_level']: {
                        'count': row['node_count'],
                        'avg_reputation': float(row['avg_reputation'])
                    }
                    for row in distribution
                }
                
        except Exception as e:
            logger.error(f"Error getting trust distribution: {e}")
            return {}
