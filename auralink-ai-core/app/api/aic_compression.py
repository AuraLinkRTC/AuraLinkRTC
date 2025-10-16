"""
AuraLink AIC Protocol - Compression API
FastAPI endpoints for AI-driven compression control and monitoring
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, validator

from app.api.deps import get_current_user, get_db_connection
from app.core.exceptions import AuraError

logger = logging.getLogger(__name__)

router = APIRouter()


# ================================================================
# Request/Response Models
# ================================================================

class AICConfigRequest(BaseModel):
    """Request to update AIC configuration"""
    enabled: bool = True
    mode: str = Field("adaptive", pattern="^(adaptive|aggressive|conservative|off)$")
    target_compression_ratio: float = Field(0.80, ge=0.1, le=0.95)
    max_latency_ms: int = Field(20, ge=5, le=100)
    model_type: str = Field("encodec", pattern="^(encodec|lyra|maxine|hybrid)$")
    min_quality_score: float = Field(0.85, ge=0.5, le=1.0)
    enable_predictive_compression: bool = True
    enable_perceptual_optimization: bool = True
    opt_out: bool = False


class AICConfigResponse(BaseModel):
    """AIC configuration response"""
    config_id: str
    user_id: str
    enabled: bool
    mode: str
    target_compression_ratio: float
    max_latency_ms: int
    model_type: str
    model_version: str
    min_quality_score: float
    created_at: datetime
    updated_at: datetime


class CompressionMetricResponse(BaseModel):
    """Single compression metric"""
    metric_id: str
    call_id: str
    participant_id: str
    original_bandwidth_kbps: int
    compressed_bandwidth_kbps: int
    compression_ratio: float
    bandwidth_savings_percent: float
    inference_latency_ms: float
    quality_score: float
    psnr_db: Optional[float]
    model_used: str
    fallback_triggered: bool
    timestamp: datetime


class SessionStatsResponse(BaseModel):
    """AIC session statistics"""
    session_id: str
    call_id: str
    participant_id: str
    aic_enabled: bool
    current_mode: str
    total_frames_processed: int
    frames_compressed: int
    frames_fallback: int
    avg_compression_ratio: float
    avg_inference_latency_ms: float
    avg_quality_score: float
    total_bandwidth_saved_mb: float
    fallback_count: int
    started_at: datetime
    duration_seconds: int


class PerformanceSummaryResponse(BaseModel):
    """Performance summary for time window"""
    total_frames: int
    avg_compression_ratio: float
    avg_bandwidth_savings: float
    avg_inference_latency: float
    avg_quality_score: float
    fallback_count: int
    fallback_rate_percent: float


class ModelPerformanceResponse(BaseModel):
    """Model performance metrics"""
    model_type: str
    model_version: str
    avg_inference_ms: float
    p95_inference_ms: float
    avg_compression_ratio: float
    avg_quality_score: float
    total_inferences: int
    success_rate: float
    avg_gpu_utilization: float


class AlertResponse(BaseModel):
    """AIC alert"""
    alert_id: str
    alert_type: str
    severity: str
    message: str
    call_id: Optional[str]
    participant_id: Optional[str]
    metric_value: Optional[float]
    threshold_value: Optional[float]
    resolved: bool
    created_at: datetime


# ================================================================
# Configuration Endpoints
# ================================================================

@router.post("/config", response_model=AICConfigResponse, status_code=status.HTTP_200_OK)
async def update_aic_config(
    config: AICConfigRequest,
    current_user: Dict = Depends(get_current_user),
    db = Depends(get_db_connection)
):
    """
    Update AIC Protocol configuration for user
    
    This endpoint allows users to enable/disable AIC compression and configure
    parameters like compression ratio, quality thresholds, and model selection.
    """
    try:
        user_id = current_user["user_id"]
        
        # Check if config exists
        existing = await db.fetchrow(
            "SELECT config_id FROM aic_configs WHERE user_id = $1",
            user_id
        )
        
        if existing:
            # Update existing config
            result = await db.fetchrow("""
                UPDATE aic_configs SET
                    enabled = $1,
                    mode = $2,
                    target_compression_ratio = $3,
                    max_latency_ms = $4,
                    model_type = $5,
                    min_quality_score = $6,
                    enable_predictive_compression = $7,
                    enable_perceptual_optimization = $8,
                    opt_out = $9,
                    updated_at = NOW()
                WHERE user_id = $10
                RETURNING *
            """, 
                config.enabled, config.mode, config.target_compression_ratio,
                config.max_latency_ms, config.model_type, config.min_quality_score,
                config.enable_predictive_compression, config.enable_perceptual_optimization,
                config.opt_out, user_id
            )
        else:
            # Create new config
            result = await db.fetchrow("""
                INSERT INTO aic_configs (
                    user_id, enabled, mode, target_compression_ratio,
                    max_latency_ms, model_type, min_quality_score,
                    enable_predictive_compression, enable_perceptual_optimization,
                    opt_out
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING *
            """,
                user_id, config.enabled, config.mode, config.target_compression_ratio,
                config.max_latency_ms, config.model_type, config.min_quality_score,
                config.enable_predictive_compression, config.enable_perceptual_optimization,
                config.opt_out
            )
        
        logger.info(f"AIC config updated for user {user_id}: enabled={config.enabled}, mode={config.mode}")
        
        return AICConfigResponse(**dict(result))
        
    except Exception as e:
        logger.error(f"Error updating AIC config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update AIC configuration: {str(e)}"
        )


@router.get("/config", response_model=AICConfigResponse)
async def get_aic_config(
    current_user: Dict = Depends(get_current_user),
    db = Depends(get_db_connection)
):
    """Get current AIC configuration for user"""
    try:
        user_id = current_user["user_id"]
        
        result = await db.fetchrow(
            "SELECT * FROM aic_configs WHERE user_id = $1",
            user_id
        )
        
        if not result:
            # Return default config
            return AICConfigResponse(
                config_id="default",
                user_id=user_id,
                enabled=False,
                mode="adaptive",
                target_compression_ratio=0.80,
                max_latency_ms=20,
                model_type="encodec",
                model_version="v1.0",
                min_quality_score=0.85,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        
        return AICConfigResponse(**dict(result))
        
    except Exception as e:
        logger.error(f"Error fetching AIC config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch AIC configuration"
        )


# ================================================================
# Metrics Endpoints
# ================================================================

@router.get("/metrics", response_model=List[CompressionMetricResponse])
async def get_compression_metrics(
    call_id: Optional[str] = Query(None),
    participant_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    current_user: Dict = Depends(get_current_user),
    db = Depends(get_db_connection)
):
    """
    Get compression metrics for calls
    
    Returns detailed metrics about AIC compression performance including
    bandwidth savings, quality scores, and inference latency.
    """
    try:
        user_id = current_user["user_id"]
        
        # Build query based on filters
        query = """
            SELECT m.* FROM aic_metrics m
            JOIN call_participants cp ON m.participant_id = cp.participant_id
            WHERE cp.identity = $1
        """
        params = [user_id]
        
        if call_id:
            query += " AND m.call_id = $2"
            params.append(call_id)
        
        if participant_id:
            param_num = len(params) + 1
            query += f" AND m.participant_id = ${param_num}"
            params.append(participant_id)
        
        query += f" ORDER BY m.timestamp DESC LIMIT ${len(params) + 1}"
        params.append(limit)
        
        results = await db.fetch(query, *params)
        
        return [CompressionMetricResponse(**dict(row)) for row in results]
        
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch compression metrics"
        )


@router.get("/sessions/{session_id}", response_model=SessionStatsResponse)
async def get_session_stats(
    session_id: str,
    current_user: Dict = Depends(get_current_user),
    db = Depends(get_db_connection)
):
    """Get statistics for a specific AIC session"""
    try:
        user_id = current_user["user_id"]
        
        result = await db.fetchrow("""
            SELECT 
                s.*,
                EXTRACT(EPOCH FROM (COALESCE(s.ended_at, NOW()) - s.started_at))::INTEGER as duration_seconds
            FROM aic_sessions s
            JOIN call_participants cp ON s.participant_id = cp.participant_id
            WHERE s.session_id = $1 AND cp.identity = $2
        """, session_id, user_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        return SessionStatsResponse(**dict(result))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching session stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch session statistics"
        )


@router.get("/performance/summary", response_model=PerformanceSummaryResponse)
async def get_performance_summary(
    hours: int = Query(24, ge=1, le=168),
    current_user: Dict = Depends(get_current_user),
    db = Depends(get_db_connection)
):
    """
    Get performance summary for last N hours
    
    Provides aggregated metrics showing overall AIC performance
    """
    try:
        user_id = current_user["user_id"]
        since = datetime.utcnow() - timedelta(hours=hours)
        
        result = await db.fetchrow("""
            SELECT
                COUNT(*) as total_frames,
                AVG(compression_ratio) as avg_compression_ratio,
                AVG(bandwidth_savings_percent) as avg_bandwidth_savings,
                AVG(inference_latency_ms) as avg_inference_latency,
                AVG(quality_score) as avg_quality_score,
                SUM(CASE WHEN fallback_triggered THEN 1 ELSE 0 END) as fallback_count,
                (SUM(CASE WHEN fallback_triggered THEN 1 ELSE 0 END)::DECIMAL / 
                 NULLIF(COUNT(*), 0) * 100) as fallback_rate_percent
            FROM aic_metrics m
            JOIN call_participants cp ON m.participant_id = cp.participant_id
            WHERE cp.identity = $1 AND m.timestamp >= $2
        """, user_id, since)
        
        if not result or result['total_frames'] == 0:
            return PerformanceSummaryResponse(
                total_frames=0,
                avg_compression_ratio=0.0,
                avg_bandwidth_savings=0.0,
                avg_inference_latency=0.0,
                avg_quality_score=0.0,
                fallback_count=0,
                fallback_rate_percent=0.0
            )
        
        return PerformanceSummaryResponse(**dict(result))
        
    except Exception as e:
        logger.error(f"Error fetching performance summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch performance summary"
        )


# ================================================================
# Model Performance Endpoints
# ================================================================

@router.get("/models/performance", response_model=List[ModelPerformanceResponse])
async def get_model_performance(
    hours: int = Query(24, ge=1, le=168),
    db = Depends(get_db_connection)
):
    """Get performance metrics for different AI models"""
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        
        results = await db.fetch("""
            SELECT
                model_type,
                model_version,
                avg_inference_ms,
                p95_inference_ms,
                avg_compression_ratio,
                avg_quality_score,
                total_inferences,
                (success_count::DECIMAL / NULLIF(total_inferences, 0) * 100) as success_rate,
                avg_gpu_utilization
            FROM aic_model_performance
            WHERE window_start >= $1
            ORDER BY window_start DESC, model_type
        """, since)
        
        return [ModelPerformanceResponse(**dict(row)) for row in results]
        
    except Exception as e:
        logger.error(f"Error fetching model performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch model performance"
        )


# ================================================================
# Alert Endpoints
# ================================================================

@router.get("/alerts", response_model=List[AlertResponse])
async def get_aic_alerts(
    resolved: Optional[bool] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict = Depends(get_current_user),
    db = Depends(get_db_connection)
):
    """Get AIC system alerts"""
    try:
        user_id = current_user["user_id"]
        
        query = """
            SELECT a.* FROM aic_alerts a
            LEFT JOIN calls c ON a.call_id = c.call_id
            LEFT JOIN call_participants cp ON c.call_id = cp.call_id
            WHERE (cp.identity = $1 OR a.call_id IS NULL)
        """
        params = [user_id]
        
        if resolved is not None:
            query += f" AND a.resolved = ${len(params) + 1}"
            params.append(resolved)
        
        if severity:
            query += f" AND a.severity = ${len(params) + 1}"
            params.append(severity)
        
        query += f" ORDER BY a.created_at DESC LIMIT ${len(params) + 1}"
        params.append(limit)
        
        results = await db.fetch(query, *params)
        
        return [AlertResponse(**dict(row)) for row in results]
        
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch alerts"
        )


@router.patch("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolution_notes: Optional[str] = None,
    current_user: Dict = Depends(get_current_user),
    db = Depends(get_db_connection)
):
    """Mark an alert as resolved"""
    try:
        result = await db.fetchrow("""
            UPDATE aic_alerts
            SET resolved = TRUE,
                resolved_at = NOW(),
                resolution_notes = $1
            WHERE alert_id = $2
            RETURNING alert_id
        """, resolution_notes, alert_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
        
        return {"status": "resolved", "alert_id": alert_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve alert"
        )


# ================================================================
# Statistics Endpoints
# ================================================================

@router.get("/stats/bandwidth-savings")
async def get_bandwidth_savings(
    call_id: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
    current_user: Dict = Depends(get_current_user),
    db = Depends(get_db_connection)
):
    """
    Calculate total bandwidth savings from AIC compression
    
    Returns cumulative bandwidth saved in MB and estimated cost savings
    """
    try:
        user_id = current_user["user_id"]
        since = datetime.utcnow() - timedelta(days=days)
        
        query = """
            SELECT
                SUM((original_bandwidth_kbps - compressed_bandwidth_kbps) * 1.0 / 8192) as total_saved_mb,
                AVG(bandwidth_savings_percent) as avg_savings_percent,
                COUNT(*) as total_frames
            FROM aic_metrics m
            JOIN call_participants cp ON m.participant_id = cp.participant_id
            WHERE cp.identity = $1 AND m.timestamp >= $2
        """
        params = [user_id, since]
        
        if call_id:
            query += " AND m.call_id = $3"
            params.append(call_id)
        
        result = await db.fetchrow(query, *params)
        
        if not result or result['total_frames'] == 0:
            return {
                "total_saved_mb": 0.0,
                "total_saved_gb": 0.0,
                "avg_savings_percent": 0.0,
                "total_frames": 0,
                "estimated_cost_savings_usd": 0.0,
                "period_days": days
            }
        
        total_mb = float(result['total_saved_mb'] or 0)
        total_gb = total_mb / 1024
        
        # Estimate cost savings (assuming $0.10 per GB)
        estimated_savings = total_gb * 0.10
        
        return {
            "total_saved_mb": round(total_mb, 2),
            "total_saved_gb": round(total_gb, 3),
            "avg_savings_percent": round(float(result['avg_savings_percent'] or 0), 2),
            "total_frames": result['total_frames'],
            "estimated_cost_savings_usd": round(estimated_savings, 2),
            "period_days": days
        }
        
    except Exception as e:
        logger.error(f"Error calculating bandwidth savings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate bandwidth savings"
        )


@router.get("/stats/quality-distribution")
async def get_quality_distribution(
    days: int = Query(7, ge=1, le=90),
    current_user: Dict = Depends(get_current_user),
    db = Depends(get_db_connection)
):
    """Get distribution of quality scores over time"""
    try:
        user_id = current_user["user_id"]
        since = datetime.utcnow() - timedelta(days=days)
        
        result = await db.fetch("""
            SELECT
                CASE
                    WHEN quality_score >= 0.9 THEN 'excellent'
                    WHEN quality_score >= 0.8 THEN 'good'
                    WHEN quality_score >= 0.7 THEN 'fair'
                    ELSE 'poor'
                END as quality_level,
                COUNT(*) as frame_count,
                AVG(quality_score) as avg_score
            FROM aic_metrics m
            JOIN call_participants cp ON m.participant_id = cp.participant_id
            WHERE cp.identity = $1 AND m.timestamp >= $2
            GROUP BY quality_level
            ORDER BY avg_score DESC
        """, user_id, since)
        
        return {
            "distribution": [dict(row) for row in result],
            "period_days": days
        }
        
    except Exception as e:
        logger.error(f"Error fetching quality distribution: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch quality distribution"
        )
