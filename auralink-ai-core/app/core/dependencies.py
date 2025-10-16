"""
Dependency injection for services
"""

import os
import logging
from functools import lru_cache
from typing import Optional

import asyncpg
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

from app.services.memory_service import MemoryService
from app.services.ai_provider_service import AIProviderService
from app.services.speech_service import SpeechService
from app.services.translation_service import TranslationService
from app.services.workflow_service import WorkflowService
from app.services.agent_service import AgentService
from app.services.storage_service import StorageService
from app.services.vector_service import VectorService

# Phase 5 Services
from app.services.mcp_service import MCPService
from app.services.langgraph_agent_service import LangGraphAgentService
from app.services.crewai_service import CrewAIService
from app.services.autogen_service import AutoGenService
from app.services.llm_selection_service import LLMSelectionService
from app.services.prefect_workflow_service import PrefectWorkflowService


# Global service instances
_db_pool: Optional[asyncpg.Pool] = None
_memory_service: Optional[MemoryService] = None
_ai_provider_service: Optional[AIProviderService] = None
_speech_service: Optional[SpeechService] = None
_translation_service: Optional[TranslationService] = None
_workflow_service: Optional[WorkflowService] = None
_agent_service: Optional[AgentService] = None
_storage_service: Optional[StorageService] = None
_vector_service: Optional[VectorService] = None

# Phase 5 Service Instances
_mcp_service: Optional[MCPService] = None
_langgraph_service: Optional[LangGraphAgentService] = None
_crewai_service: Optional[CrewAIService] = None
_autogen_service: Optional[AutoGenService] = None
_llm_selection_service: Optional[LLMSelectionService] = None
_prefect_service: Optional[PrefectWorkflowService] = None


async def get_db_pool() -> asyncpg.Pool:
    """Get database connection pool"""
    global _db_pool
    
    if _db_pool is None:
        from app.core.database import get_database
        db = get_database()
        await db.connect()
        _db_pool = db.pool
    
    return _db_pool


def get_memory_service() -> MemoryService:
    """Get Memory Service instance"""
    global _memory_service
    
    if _memory_service is None:
        # Initialize with placeholder (should be async init in reality)
        # For now, we'll initialize services lazily
        openai_client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Note: This is a simplified initialization
        # In production, initialize in lifespan startup
        _memory_service = MemoryService(
            db_pool=None,  # Will be set in startup
            openai_client=openai_client
        )
    
    return _memory_service


def get_ai_provider_service() -> AIProviderService:
    """Get AI Provider Service instance"""
    global _ai_provider_service
    
    if _ai_provider_service is None:
        _ai_provider_service = AIProviderService(db_pool=None)
    
    return _ai_provider_service


def get_speech_service() -> SpeechService:
    """Get Speech Service instance"""
    global _speech_service
    
    if _speech_service is None:
        _speech_service = SpeechService(
            db_pool=None,
            ai_provider_service=get_ai_provider_service(),
            storage_client=None
        )
    
    return _speech_service


def get_translation_service() -> TranslationService:
    """Get Translation Service instance"""
    global _translation_service
    
    if _translation_service is None:
        _translation_service = TranslationService(
            db_pool=None,
            ai_provider_service=get_ai_provider_service()
        )
    
    return _translation_service


def get_workflow_service() -> WorkflowService:
    """Get Workflow Service instance"""
    global _workflow_service
    
    if _workflow_service is None:
        _workflow_service = WorkflowService(db_pool=None)
    
    return _workflow_service


def get_agent_service() -> AgentService:
    """Get Agent Service instance"""
    global _agent_service
    
    if _agent_service is None:
        _agent_service = AgentService(
            db_pool=None,
            ai_provider_service=get_ai_provider_service(),
            memory_service=get_memory_service(),
            speech_service=get_speech_service(),
            translation_service=get_translation_service()
        )
    
    return _agent_service


def get_mcp_service() -> MCPService:
    """Get MCP Service instance"""
    global _mcp_service
    if _mcp_service is None:
        _mcp_service = MCPService(db_pool=None)
    return _mcp_service


def get_langgraph_service() -> LangGraphAgentService:
    """Get LangGraph Agent Service instance"""
    global _langgraph_service
    if _langgraph_service is None:
        _langgraph_service = LangGraphAgentService(
            db_pool=None,
            ai_provider_service=get_ai_provider_service(),
            memory_service=get_memory_service(),
            mcp_service=get_mcp_service(),
            speech_service=get_speech_service(),
            translation_service=get_translation_service()
        )
    return _langgraph_service


def get_crewai_service() -> CrewAIService:
    """Get CrewAI Service instance"""
    global _crewai_service
    if _crewai_service is None:
        _crewai_service = CrewAIService(
            db_pool=None,
            ai_provider_service=get_ai_provider_service(),
            memory_service=get_memory_service(),
            mcp_service=get_mcp_service()
        )
    return _crewai_service


def get_autogen_service() -> AutoGenService:
    """Get AutoGen Service instance"""
    global _autogen_service
    if _autogen_service is None:
        _autogen_service = AutoGenService(
            db_pool=None,
            ai_provider_service=get_ai_provider_service(),
            memory_service=get_memory_service()
        )
    return _autogen_service


def get_llm_selection_service() -> LLMSelectionService:
    """Get LLM Selection Service instance"""
    global _llm_selection_service
    if _llm_selection_service is None:
        _llm_selection_service = LLMSelectionService(db_pool=None)
    return _llm_selection_service


def get_prefect_service() -> PrefectWorkflowService:
    """Get Prefect Workflow Service instance"""
    global _prefect_service
    if _prefect_service is None:
        _prefect_service = PrefectWorkflowService(
            db_pool=None,
            mcp_service=get_mcp_service(),
            memory_service=get_memory_service(),
            agent_service=get_agent_service()
        )
    return _prefect_service


async def initialize_services():
    """
    Initialize all services with database pool
    Should be called during application startup
    """
    global _memory_service, _ai_provider_service, _speech_service
    global _translation_service, _workflow_service, _agent_service
    global _mcp_service, _langgraph_service, _crewai_service
    global _autogen_service, _llm_selection_service, _prefect_service
    
    # Get database pool
    db_pool = await get_db_pool()
    
    # Initialize OpenAI client
    openai_client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Initialize Phase 1-4 services (in correct dependency order)
    _ai_provider_service = AIProviderService(db_pool=db_pool)
    
    # Initialize storage service
    _storage_service = StorageService()
    await _storage_service.initialize()
    logger.info("✓ Storage service initialized")
    
    # Initialize vector service
    _vector_service = VectorService(db_pool)
    await _vector_service.initialize()
    logger.info(f"✓ Vector service initialized (pgvector: {_vector_service.has_pgvector})")
    
    # Initialize memory service with vector service
    _memory_service = MemoryService(
        db_pool=db_pool,
        openai_client=openai_client
    )
    _memory_service.vector_service = _vector_service
    
    _speech_service = SpeechService(
        db_pool=db_pool,
        ai_provider_service=_ai_provider_service,
        storage_client=_storage_service
    )
    
    _translation_service = TranslationService(
        db_pool=db_pool,
        ai_provider_service=_ai_provider_service
    )
    
    _workflow_service = WorkflowService(db_pool=db_pool)
    
    _agent_service = AgentService(
        db_pool=db_pool,
        ai_provider_service=_ai_provider_service,
        memory_service=_memory_service,
        speech_service=_speech_service,
        translation_service=_translation_service
    )
    
    # Initialize Phase 5 services
    _mcp_service = MCPService(db_pool=db_pool)
    await _mcp_service.initialize()
    
    _llm_selection_service = LLMSelectionService(db_pool=db_pool)
    
    _langgraph_service = LangGraphAgentService(
        db_pool=db_pool,
        ai_provider_service=_ai_provider_service,
        memory_service=_memory_service,
        mcp_service=_mcp_service,
        speech_service=_speech_service,
        translation_service=_translation_service
    )
    
    _crewai_service = CrewAIService(
        db_pool=db_pool,
        ai_provider_service=_ai_provider_service,
        memory_service=_memory_service,
        mcp_service=_mcp_service
    )
    
    _autogen_service = AutoGenService(
        db_pool=db_pool,
        ai_provider_service=_ai_provider_service,
        memory_service=_memory_service
    )
    
    _prefect_service = PrefectWorkflowService(
        db_pool=db_pool,
        mcp_service=_mcp_service,
        memory_service=_memory_service,
        agent_service=_agent_service
    )


async def cleanup_services():
    """Cleanup services during application shutdown"""
    global _db_pool
    
    if _db_pool:
        await _db_pool.close()
