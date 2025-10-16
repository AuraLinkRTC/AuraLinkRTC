"""
AI Provider Service - BYOK Support
Manages multiple AI providers with fallback and cost tracking
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from uuid import UUID
from datetime import datetime

import asyncpg
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from app.core.encryption import get_encryption_service

logger = logging.getLogger(__name__)


class ProviderType(str, Enum):
    """Provider types"""
    LLM = "llm"
    TTS = "tts"
    STT = "stt"
    TRANSLATION = "translation"
    MODERATION = "moderation"
    EMBEDDINGS = "embeddings"


class ProviderName(str, Enum):
    """Supported providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    ELEVENLABS = "elevenlabs"
    WHISPER = "whisper"
    GOOGLE_CLOUD = "google_cloud"
    AZURE = "azure"
    AWS_POLLY = "aws_polly"


class AIProviderService:
    """
    AI Provider Service with BYOK support
    
    Features:
    - Multi-provider support
    - BYOK (Bring Your Own Keys)
    - Automatic fallback
    - Usage tracking and cost calculation
    - Rate limiting
    """
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self._provider_clients: Dict[str, Any] = {}
        self.encryption_service = get_encryption_service()
        
        # Default managed providers (AuraLink managed)
        self._managed_providers = {
            ProviderName.OPENAI: None,  # Initialized with environment API key
            ProviderName.ANTHROPIC: None,
        }
        
        # Provider fallback order
        self._fallback_order = {
            ProviderType.LLM: [ProviderName.OPENAI, ProviderName.ANTHROPIC],
            ProviderType.TTS: [ProviderName.ELEVENLABS, ProviderName.OPENAI],
            ProviderType.STT: [ProviderName.WHISPER, ProviderName.GOOGLE_CLOUD, ProviderName.AZURE]
        }
    
    # ========================================================================
    # PROVIDER CONFIGURATION MANAGEMENT
    # ========================================================================
    
    async def get_provider_config(
        self,
        user_id: UUID,
        provider_type: ProviderType,
        provider_name: Optional[ProviderName] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get provider configuration for user
        Returns BYOK config if available, otherwise managed config
        """
        async with self.db_pool.acquire() as conn:
            # First, try to get user's BYOK config
            row = await conn.fetchrow(
                """
                SELECT 
                    config_id, provider_name, provider_type,
                    api_key_encrypted, api_endpoint, config, is_default
                FROM ai_provider_configs
                WHERE user_id = $1
                    AND provider_type = $2
                    AND ($3::VARCHAR IS NULL OR provider_name = $3)
                    AND is_active = TRUE
                ORDER BY is_default DESC, created_at DESC
                LIMIT 1
                """,
                user_id, provider_type.value, provider_name.value if provider_name else None
            )
            
            if row:
                return dict(row)
            
            # Fallback to managed provider
            return await self._get_managed_provider_config(provider_type, provider_name)
    
    async def _get_managed_provider_config(
        self,
        provider_type: ProviderType,
        provider_name: Optional[ProviderName]
    ) -> Optional[Dict[str, Any]]:
        """Get AuraLink managed provider configuration"""
        # Default managed configurations
        managed_configs = {
            ProviderType.LLM: {
                "provider_name": ProviderName.OPENAI.value,
                "model": "gpt-4-turbo-preview",
                "is_managed": True
            },
            ProviderType.TTS: {
                "provider_name": ProviderName.ELEVENLABS.value,
                "is_managed": True
            },
            ProviderType.STT: {
                "provider_name": ProviderName.WHISPER.value,
                "model": "whisper-1",
                "is_managed": True
            },
            ProviderType.TRANSLATION: {
                "provider_name": ProviderName.OPENAI.value,
                "model": "gpt-4-turbo-preview",
                "is_managed": True
            },
            ProviderType.EMBEDDINGS: {
                "provider_name": ProviderName.OPENAI.value,
                "model": "text-embedding-ada-002",
                "is_managed": True
            }
        }
        
        return managed_configs.get(provider_type)
    
    async def save_provider_config(
        self,
        user_id: UUID,
        provider_name: ProviderName,
        provider_type: ProviderType,
        api_key: str,
        api_endpoint: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        is_default: bool = False
    ) -> UUID:
        """Save BYOK provider configuration with encrypted API key"""
        # Encrypt API key before storing
        encrypted_key = self.encryption_service.encrypt_api_key(api_key)
        
        async with self.db_pool.acquire() as conn:
            config_id = await conn.fetchval(
                """
                INSERT INTO ai_provider_configs (
                    user_id, provider_name, provider_type,
                    api_key_encrypted, api_endpoint, config, is_default
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING config_id
                """,
                user_id,
                provider_name.value,
                provider_type.value,
                encrypted_key,
                api_endpoint,
                config or {},
                is_default
            )
        
        logger.info(f"Saved provider config {config_id} for user {user_id}")
        return config_id
    
    # ========================================================================
    # PROVIDER CLIENT MANAGEMENT
    # ========================================================================
    
    def _get_client(
        self,
        provider_name: ProviderName,
        api_key: Optional[str] = None
    ) -> Any:
        """Get or create provider client"""
        client_key = f"{provider_name}_{api_key[:8] if api_key else 'managed'}"
        
        if client_key in self._provider_clients:
            return self._provider_clients[client_key]
        
        # Create new client
        client = self._create_client(provider_name, api_key)
        self._provider_clients[client_key] = client
        
        return client
    
    def _create_client(
        self,
        provider_name: ProviderName,
        api_key: Optional[str] = None
    ) -> Any:
        """Create provider client"""
        if provider_name == ProviderName.OPENAI:
            return AsyncOpenAI(api_key=api_key) if api_key else AsyncOpenAI()
        
        elif provider_name == ProviderName.ANTHROPIC:
            return AsyncAnthropic(api_key=api_key) if api_key else AsyncAnthropic()
        
        # Add more providers as needed
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")
    
    # ========================================================================
    # LLM OPERATIONS
    # ========================================================================
    
    async def chat_completion(
        self,
        user_id: UUID,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        provider_name: Optional[ProviderName] = None
    ) -> Dict[str, Any]:
        """
        Generate chat completion using configured provider
        """
        start_time = datetime.utcnow()
        
        # Get provider config
        config = await self.get_provider_config(
            user_id, ProviderType.LLM, provider_name
        )
        
        if not config:
            raise ValueError("No LLM provider configured")
        
        provider = config["provider_name"]
        encrypted_key = config.get("api_key_encrypted")
        
        # Decrypt API key if present
        api_key = None
        if encrypted_key and not config.get("is_managed"):
            try:
                api_key = self.encryption_service.decrypt_api_key(encrypted_key)
            except Exception as e:
                logger.error(f"Error decrypting API key: {e}")
        
        model = model or config.get("model", "gpt-4-turbo-preview")
        
        # Get client
        client = self._get_client(ProviderName(provider), api_key)
        
        try:
            # Call provider API
            if provider == ProviderName.OPENAI.value:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                result = {
                    "content": response.choices[0].message.content,
                    "model": response.model,
                    "usage": {
                        "input_tokens": response.usage.prompt_tokens,
                        "output_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    },
                    "finish_reason": response.choices[0].finish_reason
                }
            
            elif provider == ProviderName.ANTHROPIC.value:
                response = await client.messages.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                result = {
                    "content": response.content[0].text,
                    "model": response.model,
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                        "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                    },
                    "finish_reason": response.stop_reason
                }
            
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")
            
            # Calculate latency
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            result["latency_ms"] = latency_ms
            
            # Track usage
            await self._track_usage(
                user_id=user_id,
                service_type=ProviderType.LLM,
                provider=provider,
                model=model,
                tokens_used=result["usage"]["total_tokens"],
                input_tokens=result["usage"]["input_tokens"],
                output_tokens=result["usage"]["output_tokens"],
                latency_ms=latency_ms
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Error in chat completion with {provider}: {e}")
            
            # Implement fallback to alternative provider
            return await self._chat_completion_with_fallback(
                user_id, messages, model, temperature, max_tokens, provider_name
            )
    
    async def _chat_completion_with_fallback(
        self,
        user_id: UUID,
        messages: List[Dict[str, str]],
        model: Optional[str],
        temperature: float,
        max_tokens: int,
        failed_provider: Optional[ProviderName]
    ) -> Dict[str, Any]:
        """
        Attempt chat completion with fallback providers
        """
        fallback_providers = self._fallback_order.get(ProviderType.LLM, [])
        
        # Remove the failed provider from fallback list
        if failed_provider:
            fallback_providers = [p for p in fallback_providers if p != failed_provider]
        
        for provider in fallback_providers:
            try:
                logger.info(f"Attempting fallback to {provider.value}")
                
                result = await self.chat_completion(
                    user_id=user_id,
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    provider_name=provider
                )
                
                logger.info(f"Successfully completed with fallback provider {provider.value}")
                return result
            
            except Exception as e:
                logger.error(f"Fallback provider {provider.value} also failed: {e}")
                continue
        
        # All providers failed
        raise ValueError("All LLM providers failed. Please check your configuration.")
    
    # ========================================================================
    # EMBEDDING OPERATIONS
    # ========================================================================
    
    async def generate_embeddings(
        self,
        user_id: UUID,
        texts: List[str],
        model: Optional[str] = None,
        provider_name: Optional[ProviderName] = None
    ) -> List[List[float]]:
        """Generate embeddings using configured provider"""
        start_time = datetime.utcnow()
        
        # Get provider config
        config = await self.get_provider_config(
            user_id, ProviderType.EMBEDDINGS, provider_name
        )
        
        if not config:
            raise ValueError("No embeddings provider configured")
        
        provider = config["provider_name"]
        api_key = config.get("api_key_encrypted")
        model = model or config.get("model", "text-embedding-ada-002")
        
        # Get client
        client = self._get_client(ProviderName(provider), api_key)
        
        try:
            if provider == ProviderName.OPENAI.value:
                response = await client.embeddings.create(
                    model=model,
                    input=texts
                )
                
                embeddings = [item.embedding for item in response.data]
                total_tokens = response.usage.total_tokens
            
            else:
                raise ValueError(f"Unsupported embeddings provider: {provider}")
            
            # Calculate latency
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Track usage
            await self._track_usage(
                user_id=user_id,
                service_type=ProviderType.EMBEDDINGS,
                provider=provider,
                model=model,
                tokens_used=total_tokens,
                latency_ms=latency_ms
            )
            
            return embeddings
        
        except Exception as e:
            logger.error(f"Error generating embeddings with {provider}: {e}")
            # Try fallback
            if provider != ProviderName.OPENAI.value:
                logger.info("Falling back to OpenAI for embeddings")
                return await self.generate_embeddings(
                    user_id, texts, model, ProviderName.OPENAI
                )
            raise
    
    # ========================================================================
    # USAGE TRACKING
    # ========================================================================
    
    async def _track_usage(
        self,
        user_id: UUID,
        service_type: ProviderType,
        provider: str,
        model: Optional[str] = None,
        tokens_used: Optional[int] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        characters_processed: Optional[int] = None,
        audio_seconds: Optional[float] = None,
        latency_ms: Optional[int] = None,
        agent_id: Optional[UUID] = None,
        call_id: Optional[str] = None
    ):
        """Track AI service usage"""
        # Calculate estimated cost
        estimated_cost = self._calculate_cost(
            service_type, provider, model,
            tokens_used, characters_processed, audio_seconds
        )
        
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ai_usage_logs (
                    user_id, service_type, provider, model,
                    tokens_used, input_tokens, output_tokens,
                    characters_processed, audio_seconds,
                    estimated_cost_usd, latency_ms,
                    agent_id, call_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                user_id, service_type.value, provider, model,
                tokens_used, input_tokens, output_tokens,
                characters_processed, audio_seconds,
                estimated_cost, latency_ms,
                agent_id, call_id
            )
    
    def _calculate_cost(
        self,
        service_type: ProviderType,
        provider: str,
        model: Optional[str],
        tokens: Optional[int],
        characters: Optional[int],
        audio_seconds: Optional[float]
    ) -> float:
        """Calculate estimated cost in USD"""
        # Pricing as of 2024 (approximate)
        pricing = {
            "openai": {
                "gpt-4-turbo-preview": {
                    "input": 0.01 / 1000,  # per token
                    "output": 0.03 / 1000
                },
                "gpt-4": {
                    "input": 0.03 / 1000,
                    "output": 0.06 / 1000
                },
                "gpt-3.5-turbo": {
                    "input": 0.0005 / 1000,
                    "output": 0.0015 / 1000
                },
                "text-embedding-ada-002": 0.0001 / 1000,
                "whisper-1": 0.006 / 60  # per second
            },
            "elevenlabs": {
                "tts": 0.30 / 1000  # per character
            }
        }
        
        # Simple cost calculation (needs refinement)
        if tokens:
            if provider == "openai" and model in pricing["openai"]:
                if isinstance(pricing["openai"][model], dict):
                    # Assume 50/50 split for simplicity
                    return tokens * (pricing["openai"][model]["input"] + pricing["openai"][model]["output"]) / 2
                else:
                    return tokens * pricing["openai"][model]
        
        if characters and provider == "elevenlabs":
            return characters * pricing["elevenlabs"]["tts"]
        
        if audio_seconds and provider == "openai" and service_type == ProviderType.STT:
            return audio_seconds * pricing["openai"]["whisper-1"]
        
        return 0.0
    
    async def get_usage_summary(
        self,
        user_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get usage summary for user"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(tokens_used) as total_tokens,
                    SUM(estimated_cost_usd) as total_cost_usd,
                    AVG(latency_ms) as avg_latency_ms,
                    COUNT(DISTINCT service_type) as services_used
                FROM ai_usage_logs
                WHERE user_id = $1
                    AND created_at > NOW() - INTERVAL '{days} days'
                """.format(days=days),
                user_id
            )
        
        return dict(row) if row else {}
