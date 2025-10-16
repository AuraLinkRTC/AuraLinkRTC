"""
LLM Selection API Endpoints - Multiple LLM Provider Management
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from uuid import UUID
from decimal import Decimal

from app.api.deps import get_current_user, get_llm_selection_service

router = APIRouter()


# ========================================================================
# REQUEST/RESPONSE MODELS
# ========================================================================

class SetDefaultModelRequest(BaseModel):
    model_id: UUID
    custom_api_key: Optional[str] = None


class AddModelPreferenceRequest(BaseModel):
    model_id: UUID
    priority: int = Field(0, ge=0, le=100)
    custom_api_key: Optional[str] = None
    usage_limit_tokens: Optional[int] = None
    cost_limit_usd: Optional[Decimal] = None


class LogPerformanceRequest(BaseModel):
    model_id: UUID
    request_type: str
    latency_ms: int
    tokens_input: int
    tokens_output: int
    cost_usd: Decimal
    success: bool = True
    error_type: Optional[str] = None
    quality_score: Optional[Decimal] = None


class CompareModelsRequest(BaseModel):
    model_ids: List[UUID] = Field(..., min_items=2, max_items=10)
    days: int = Field(30, ge=1, le=90)


# ========================================================================
# PROVIDER & MODEL DISCOVERY
# ========================================================================

@router.get("/providers")
async def list_providers(
    llm_service = Depends(get_llm_selection_service)
):
    """List all available LLM providers"""
    providers = await llm_service.list_available_providers()
    return {"providers": providers, "total": len(providers)}


@router.get("/models")
async def list_models(
    provider_id: Optional[UUID] = None,
    model_type: Optional[str] = None,
    performance_tier: Optional[str] = None,
    llm_service = Depends(get_llm_selection_service)
):
    """List available LLM models with filters"""
    models = await llm_service.list_available_models(
        provider_id=provider_id,
        model_type=model_type,
        performance_tier=performance_tier
    )
    return {"models": models, "total": len(models)}


@router.get("/models/{model_id}")
async def get_model_details(
    model_id: UUID,
    llm_service = Depends(get_llm_selection_service)
):
    """Get detailed information about a model"""
    model = await llm_service.get_model_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


# ========================================================================
# USER PREFERENCES
# ========================================================================

@router.post("/preferences/default")
async def set_default_model(
    request: SetDefaultModelRequest,
    user_id: UUID = Depends(get_current_user),
    llm_service = Depends(get_llm_selection_service)
):
    """Set user's default LLM model"""
    try:
        result = await llm_service.set_user_default_model(
            user_id=user_id,
            model_id=request.model_id,
            custom_api_key=request.custom_api_key
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/preferences/add")
async def add_model_preference(
    request: AddModelPreferenceRequest,
    user_id: UUID = Depends(get_current_user),
    llm_service = Depends(get_llm_selection_service)
):
    """Add a model to user's preferences"""
    try:
        result = await llm_service.add_user_model_preference(
            user_id=user_id,
            model_id=request.model_id,
            priority=request.priority,
            custom_api_key=request.custom_api_key,
            usage_limit_tokens=request.usage_limit_tokens,
            cost_limit_usd=request.cost_limit_usd
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/preferences")
async def get_user_preferences(
    user_id: UUID = Depends(get_current_user),
    llm_service = Depends(get_llm_selection_service)
):
    """Get user's preferred models"""
    preferences = await llm_service.get_user_preferred_models(user_id)
    return {"preferences": preferences, "total": len(preferences)}


@router.get("/preferences/best")
async def select_best_model(
    task_type: str = "chat",
    consider_cost: bool = True,
    consider_performance: bool = True,
    user_id: UUID = Depends(get_current_user),
    llm_service = Depends(get_llm_selection_service)
):
    """Intelligently select the best model for user"""
    selection = await llm_service.select_best_model(
        user_id=user_id,
        task_type=task_type,
        consider_cost=consider_cost,
        consider_performance=consider_performance
    )
    return selection


# ========================================================================
# PERFORMANCE TRACKING
# ========================================================================

@router.post("/performance/log")
async def log_performance(
    request: LogPerformanceRequest,
    user_id: UUID = Depends(get_current_user),
    llm_service = Depends(get_llm_selection_service)
):
    """Log performance metrics for a model"""
    try:
        metric_id = await llm_service.log_model_performance(
            model_id=request.model_id,
            user_id=user_id,
            request_type=request.request_type,
            latency_ms=request.latency_ms,
            tokens_input=request.tokens_input,
            tokens_output=request.tokens_output,
            cost_usd=request.cost_usd,
            success=request.success,
            error_type=request.error_type,
            quality_score=request.quality_score
        )
        return {"metric_id": metric_id, "status": "logged"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/models/{model_id}")
async def get_model_performance(
    model_id: UUID,
    days: int = 30,
    llm_service = Depends(get_llm_selection_service)
):
    """Get performance statistics for a model"""
    stats = await llm_service.get_model_performance_stats(model_id, days)
    return stats


@router.post("/performance/compare")
async def compare_models(
    request: CompareModelsRequest,
    llm_service = Depends(get_llm_selection_service)
):
    """Compare performance across multiple models"""
    comparisons = await llm_service.compare_models(
        model_ids=request.model_ids,
        days=request.days
    )
    return {"comparisons": comparisons, "total": len(comparisons)}


# ========================================================================
# COST ANALYSIS
# ========================================================================

@router.get("/cost/analysis")
async def get_cost_analysis(
    days: int = 30,
    user_id: UUID = Depends(get_current_user),
    llm_service = Depends(get_llm_selection_service)
):
    """Get cost analysis for user's LLM usage"""
    analysis = await llm_service.get_cost_analysis(user_id, days)
    return analysis


# ========================================================================
# RECOMMENDATIONS
# ========================================================================

@router.get("/recommendations")
async def get_recommendations(
    use_case: str = "general",
    user_id: UUID = Depends(get_current_user),
    llm_service = Depends(get_llm_selection_service)
):
    """Get model recommendations for user"""
    recommendations = await llm_service.get_model_recommendations(user_id, use_case)
    return {"recommendations": recommendations, "total": len(recommendations)}
