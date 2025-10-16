"""
LLM Selection Service - Multiple LLM Provider Management
Dynamic LLM selection with performance tracking and cost optimization
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal

import asyncpg

logger = logging.getLogger(__name__)


class LLMSelectionService:
    """
    LLM Selection and Management Service
    
    Features:
    - Multiple LLM provider support
    - Dynamic model selection
    - Performance comparison
    - Cost optimization
    - BYOK (Bring Your Own Keys)
    - Automatic failover
    """
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.model_cache: Dict[str, Dict[str, Any]] = {}
    
    # ========================================================================
    # LLM PROVIDER & MODEL MANAGEMENT
    # ========================================================================
    
    async def list_available_providers(self) -> List[Dict[str, Any]]:
        """List all available LLM providers"""
        async with self.db_pool.acquire() as conn:
            providers = await conn.fetch(
                """
                SELECT 
                    provider_id,
                    provider_name,
                    provider_type,
                    is_enabled,
                    supports_streaming,
                    supports_function_calling,
                    (SELECT COUNT(*) FROM llm_models WHERE provider_id = lp.provider_id AND is_available = true) AS model_count
                FROM llm_providers lp
                WHERE is_enabled = true
                ORDER BY provider_name
                """
            )
            
            return [dict(p) for p in providers]
    
    async def list_available_models(
        self,
        provider_id: Optional[UUID] = None,
        model_type: Optional[str] = None,
        performance_tier: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List available LLM models with filters"""
        query = """
            SELECT 
                m.model_id,
                m.model_name,
                m.display_name,
                m.model_type,
                m.context_window,
                m.max_tokens,
                m.cost_per_1k_input_tokens,
                m.cost_per_1k_output_tokens,
                m.performance_tier,
                m.capabilities,
                p.provider_name,
                p.provider_type
            FROM llm_models m
            JOIN llm_providers p ON m.provider_id = p.provider_id
            WHERE m.is_available = true AND p.is_enabled = true
        """
        
        params = []
        if provider_id:
            params.append(provider_id)
            query += f" AND m.provider_id = ${len(params)}"
        
        if model_type:
            params.append(model_type)
            query += f" AND m.model_type = ${len(params)}"
        
        if performance_tier:
            params.append(performance_tier)
            query += f" AND m.performance_tier = ${len(params)}"
        
        query += " ORDER BY p.provider_name, m.display_name"
        
        async with self.db_pool.acquire() as conn:
            models = await conn.fetch(query, *params)
            return [dict(m) for m in models]
    
    async def get_model_by_id(self, model_id: UUID) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific model"""
        async with self.db_pool.acquire() as conn:
            model = await conn.fetchrow(
                """
                SELECT 
                    m.*,
                    p.provider_name,
                    p.provider_type,
                    p.api_endpoint,
                    p.supports_streaming,
                    p.supports_function_calling
                FROM llm_models m
                JOIN llm_providers p ON m.provider_id = p.provider_id
                WHERE m.model_id = $1
                """,
                model_id
            )
            
            return dict(model) if model else None
    
    # ========================================================================
    # USER LLM PREFERENCES
    # ========================================================================
    
    async def set_user_default_model(
        self,
        user_id: UUID,
        model_id: UUID,
        custom_api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set user's default LLM model"""
        logger.info(f"Setting default model for user {user_id}")
        
        async with self.db_pool.acquire() as conn:
            # Unset previous default
            await conn.execute(
                """
                UPDATE user_llm_preferences
                SET is_default = false
                WHERE user_id = $1
                """,
                user_id
            )
            
            # Set new default
            preference_id = await conn.fetchval(
                """
                INSERT INTO user_llm_preferences (
                    user_id, model_id, is_default, priority,
                    custom_api_key, is_active
                ) VALUES ($1, $2, true, 100, $3, true)
                ON CONFLICT (user_id, model_id) 
                DO UPDATE SET 
                    is_default = true,
                    priority = 100,
                    custom_api_key = COALESCE(EXCLUDED.custom_api_key, user_llm_preferences.custom_api_key),
                    is_active = true,
                    updated_at = NOW()
                RETURNING preference_id
                """,
                user_id, model_id, custom_api_key
            )
        
        return {
            'preference_id': preference_id,
            'user_id': user_id,
            'model_id': model_id,
            'is_default': True
        }
    
    async def add_user_model_preference(
        self,
        user_id: UUID,
        model_id: UUID,
        priority: int = 0,
        custom_api_key: Optional[str] = None,
        usage_limit_tokens: Optional[int] = None,
        cost_limit_usd: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """Add a model to user's preferences"""
        async with self.db_pool.acquire() as conn:
            preference_id = await conn.fetchval(
                """
                INSERT INTO user_llm_preferences (
                    user_id, model_id, priority, custom_api_key,
                    usage_limit_tokens, cost_limit_usd, is_active
                ) VALUES ($1, $2, $3, $4, $5, $6, true)
                ON CONFLICT (user_id, model_id)
                DO UPDATE SET
                    priority = EXCLUDED.priority,
                    custom_api_key = COALESCE(EXCLUDED.custom_api_key, user_llm_preferences.custom_api_key),
                    usage_limit_tokens = COALESCE(EXCLUDED.usage_limit_tokens, user_llm_preferences.usage_limit_tokens),
                    cost_limit_usd = COALESCE(EXCLUDED.cost_limit_usd, user_llm_preferences.cost_limit_usd),
                    is_active = true,
                    updated_at = NOW()
                RETURNING preference_id
                """,
                user_id, model_id, priority, custom_api_key,
                usage_limit_tokens, cost_limit_usd
            )
        
        return {'preference_id': preference_id, 'model_id': model_id}
    
    async def get_user_preferred_models(
        self,
        user_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get user's preferred models"""
        async with self.db_pool.acquire() as conn:
            preferences = await conn.fetch(
                """
                SELECT 
                    p.preference_id,
                    p.is_default,
                    p.priority,
                    p.usage_limit_tokens,
                    p.cost_limit_usd,
                    m.model_id,
                    m.model_name,
                    m.display_name,
                    m.performance_tier,
                    pr.provider_name
                FROM user_llm_preferences p
                JOIN llm_models m ON p.model_id = m.model_id
                JOIN llm_providers pr ON m.provider_id = pr.provider_id
                WHERE p.user_id = $1 AND p.is_active = true
                ORDER BY p.is_default DESC, p.priority DESC
                """,
                user_id
            )
            
            return [dict(pref) for pref in preferences]
    
    async def select_best_model(
        self,
        user_id: UUID,
        task_type: str = "chat",
        consider_cost: bool = True,
        consider_performance: bool = True
    ) -> Dict[str, Any]:
        """Intelligently select the best model for user"""
        logger.info(f"Selecting best model for user {user_id}, task: {task_type}")
        
        # Get user preferences
        preferences = await self.get_user_preferred_models(user_id)
        
        if not preferences:
            # Fallback to system default
            return await self._get_system_default_model(task_type)
        
        # Get default model
        default_model = next((p for p in preferences if p['is_default']), None)
        
        if default_model:
            model_details = await self.get_model_by_id(default_model['model_id'])
            return {
                'model_id': default_model['model_id'],
                'model_name': model_details['model_name'],
                'provider': model_details['provider_name'],
                'selection_reason': 'user_default'
            }
        
        # Select by priority
        highest_priority = preferences[0]
        model_details = await self.get_model_by_id(highest_priority['model_id'])
        
        return {
            'model_id': highest_priority['model_id'],
            'model_name': model_details['model_name'],
            'provider': model_details['provider_name'],
            'selection_reason': 'highest_priority'
        }
    
    async def _get_system_default_model(self, task_type: str) -> Dict[str, Any]:
        """Get system default model"""
        async with self.db_pool.acquire() as conn:
            model = await conn.fetchrow(
                """
                SELECT 
                    m.model_id,
                    m.model_name,
                    p.provider_name
                FROM llm_models m
                JOIN llm_providers p ON m.provider_id = p.provider_id
                WHERE m.model_type = $1 
                  AND m.is_available = true
                  AND p.is_enabled = true
                  AND m.performance_tier = 'standard'
                ORDER BY m.cost_per_1k_input_tokens ASC
                LIMIT 1
                """,
                task_type
            )
            
            if model:
                return {
                    'model_id': model['model_id'],
                    'model_name': model['model_name'],
                    'provider': model['provider_name'],
                    'selection_reason': 'system_default'
                }
            
            # Ultimate fallback
            return {
                'model_id': None,
                'model_name': 'gpt-3.5-turbo',
                'provider': 'openai',
                'selection_reason': 'hardcoded_fallback'
            }
    
    # ========================================================================
    # PERFORMANCE TRACKING
    # ========================================================================
    
    async def log_model_performance(
        self,
        model_id: UUID,
        user_id: UUID,
        request_type: str,
        latency_ms: int,
        tokens_input: int,
        tokens_output: int,
        cost_usd: Decimal,
        success: bool = True,
        error_type: Optional[str] = None,
        quality_score: Optional[Decimal] = None
    ) -> UUID:
        """Log performance metrics for a model"""
        async with self.db_pool.acquire() as conn:
            metric_id = await conn.fetchval(
                """
                INSERT INTO llm_performance_metrics (
                    model_id, user_id, request_type, latency_ms,
                    tokens_input, tokens_output, cost_usd,
                    success, error_type, quality_score
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING metric_id
                """,
                model_id, user_id, request_type, latency_ms,
                tokens_input, tokens_output, cost_usd,
                success, error_type, quality_score
            )
            
            return metric_id
    
    async def get_model_performance_stats(
        self,
        model_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get performance statistics for a model"""
        async with self.db_pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) AS total_requests,
                    AVG(latency_ms) AS avg_latency_ms,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY latency_ms) AS median_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms,
                    AVG(quality_score) AS avg_quality_score,
                    AVG(cost_usd) AS avg_cost_per_request,
                    SUM(cost_usd) AS total_cost_usd,
                    COUNT(CASE WHEN success = true THEN 1 END)::FLOAT / COUNT(*) AS success_rate
                FROM llm_performance_metrics
                WHERE model_id = $1
                  AND created_at > NOW() - INTERVAL '1 day' * $2
                """,
                model_id, days
            )
            
            return dict(stats) if stats else {}
    
    async def compare_models(
        self,
        model_ids: List[UUID],
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Compare performance across multiple models"""
        comparisons = []
        
        for model_id in model_ids:
            model_info = await self.get_model_by_id(model_id)
            perf_stats = await self.get_model_performance_stats(model_id, days)
            
            if model_info:
                comparisons.append({
                    'model_id': model_id,
                    'model_name': model_info['model_name'],
                    'display_name': model_info['display_name'],
                    'provider': model_info['provider_name'],
                    'performance': perf_stats
                })
        
        return comparisons
    
    async def get_cost_analysis(
        self,
        user_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get cost analysis for user's LLM usage"""
        async with self.db_pool.acquire() as conn:
            analysis = await conn.fetchrow(
                """
                SELECT 
                    SUM(lpm.cost_usd) AS total_cost_usd,
                    COUNT(*) AS total_requests,
                    SUM(lpm.tokens_input + lpm.tokens_output) AS total_tokens,
                    COUNT(DISTINCT lpm.model_id) AS models_used
                FROM llm_performance_metrics lpm
                WHERE lpm.user_id = $1
                  AND lpm.created_at > NOW() - INTERVAL '1 day' * $2
                """,
                user_id, days
            )
            
            # Get breakdown by model
            breakdown = await conn.fetch(
                """
                SELECT 
                    m.model_name,
                    p.provider_name,
                    SUM(lpm.cost_usd) AS cost_usd,
                    COUNT(*) AS request_count
                FROM llm_performance_metrics lpm
                JOIN llm_models m ON lpm.model_id = m.model_id
                JOIN llm_providers p ON m.provider_id = p.provider_id
                WHERE lpm.user_id = $1
                  AND lpm.created_at > NOW() - INTERVAL '1 day' * $2
                GROUP BY m.model_name, p.provider_name
                ORDER BY cost_usd DESC
                """,
                user_id, days
            )
            
            return {
                'summary': dict(analysis) if analysis else {},
                'breakdown_by_model': [dict(b) for b in breakdown]
            }
    
    # ========================================================================
    # RECOMMENDATIONS
    # ========================================================================
    
    async def get_model_recommendations(
        self,
        user_id: UUID,
        use_case: str = "general"
    ) -> List[Dict[str, Any]]:
        """Get model recommendations for user"""
        # Get performance data
        async with self.db_pool.acquire() as conn:
            recommendations = await conn.fetch(
                """
                SELECT 
                    m.model_id,
                    m.model_name,
                    m.display_name,
                    p.provider_name,
                    m.performance_tier,
                    m.cost_per_1k_input_tokens,
                    m.cost_per_1k_output_tokens,
                    COALESCE(AVG(lpm.latency_ms), 0) AS avg_latency,
                    COALESCE(AVG(lpm.quality_score), 0) AS avg_quality,
                    COUNT(lpm.metric_id) AS usage_count
                FROM llm_models m
                JOIN llm_providers p ON m.provider_id = p.provider_id
                LEFT JOIN llm_performance_metrics lpm ON m.model_id = lpm.model_id
                    AND lpm.created_at > NOW() - INTERVAL '30 days'
                WHERE m.is_available = true AND p.is_enabled = true
                GROUP BY m.model_id, m.model_name, m.display_name, 
                         p.provider_name, m.performance_tier,
                         m.cost_per_1k_input_tokens, m.cost_per_1k_output_tokens
                ORDER BY avg_quality DESC, avg_latency ASC
                LIMIT 5
                """)
            
            return [dict(rec) for rec in recommendations]
