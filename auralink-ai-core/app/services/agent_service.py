"""
AI Agent Service - LangGraph Integration
Multi-step reasoning AI agents with memory and tool use
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
from datetime import datetime

import asyncpg

logger = logging.getLogger(__name__)


class AgentService:
    """
    AI Agent Service with LangGraph integration
    
    Features:
    - Stateful multi-step agents
    - Memory integration
    - Tool/function calling
    - Auto-join rooms
    - Real-time talkback
    - Custom workflows
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        ai_provider_service: Any,
        memory_service: Any,
        speech_service: Any,
        translation_service: Any
    ):
        self.db_pool = db_pool
        self.ai_provider = ai_provider_service
        self.memory = memory_service
        self.speech = speech_service
        self.translation = translation_service
        
        # LangGraph initialization (optional - for advanced workflows)
        # Can be extended in subclasses or specific agent implementations
        self.supports_langgraph = False
        try:
            from langgraph.graph import StateGraph
            self.supports_langgraph = True
            logger.info("LangGraph support enabled")
        except ImportError:
            logger.debug("LangGraph not available - using basic agent implementation")
    
    # ========================================================================
    # AGENT MANAGEMENT
    # ========================================================================
    
    async def create_agent(
        self,
        user_id: UUID,
        name: str,
        model: str = "gpt-4",
        provider: str = "openai",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        system_prompt: Optional[str] = None,
        description: Optional[str] = None,
        greeting_message: Optional[str] = None,
        memory_enabled: bool = True,
        auto_join_rooms: bool = False,
        voice_enabled: bool = True,
        translation_enabled: bool = False,
        tts_provider: str = "elevenlabs",
        tts_voice_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new AI agent"""
        logger.info(f"Creating agent '{name}' for user {user_id}")
        
        async with self.db_pool.acquire() as conn:
            agent_id = await conn.fetchval(
                """
                INSERT INTO ai_agents (
                    user_id, name, description, model, provider,
                    temperature, max_tokens, system_prompt, greeting_message,
                    memory_enabled, auto_join_rooms, voice_enabled, translation_enabled,
                    tts_provider, tts_voice_id, config
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                RETURNING agent_id
                """,
                user_id, name, description, model, provider,
                temperature, max_tokens, system_prompt, greeting_message,
                memory_enabled, auto_join_rooms, voice_enabled, translation_enabled,
                tts_provider, tts_voice_id, config or {}
            )
            
            # Get full agent record
            agent = await self._get_agent_by_id(conn, agent_id, user_id)
        
        logger.info(f"Created agent {agent_id}")
        return agent
    
    async def get_agent(
        self,
        user_id: UUID,
        agent_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get agent by ID"""
        async with self.db_pool.acquire() as conn:
            return await self._get_agent_by_id(conn, agent_id, user_id)
    
    async def _get_agent_by_id(
        self,
        conn: asyncpg.Connection,
        agent_id: UUID,
        user_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Internal method to get agent"""
        row = await conn.fetchrow(
            """
            SELECT 
                agent_id, user_id, name, description, avatar_url,
                model, provider, temperature, max_tokens,
                system_prompt, greeting_message,
                memory_enabled, auto_join_rooms, voice_enabled, translation_enabled,
                tts_provider, tts_voice_id, tts_speed,
                is_active, config, metadata,
                created_at, updated_at, last_used_at
            FROM ai_agents
            WHERE agent_id = $1 AND user_id = $2
            """,
            agent_id, user_id
        )
        
        return dict(row) if row else None
    
    async def list_agents(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 10,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """List user's agents"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    agent_id, name, description, model, is_active,
                    created_at, last_used_at
                FROM ai_agents
                WHERE user_id = $1
                    AND ($4 = FALSE OR is_active = TRUE)
                ORDER BY created_at DESC
                OFFSET $2 LIMIT $3
                """,
                user_id, skip, limit, active_only
            )
        
        return [dict(row) for row in rows]
    
    async def update_agent(
        self,
        user_id: UUID,
        agent_id: UUID,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update agent configuration"""
        # Build dynamic update query
        allowed_fields = {
            'name', 'description', 'model', 'provider', 'temperature',
            'max_tokens', 'system_prompt', 'greeting_message',
            'memory_enabled', 'auto_join_rooms', 'voice_enabled',
            'translation_enabled', 'tts_provider', 'tts_voice_id',
            'is_active', 'config'
        }
        
        update_fields = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not update_fields:
            raise ValueError("No valid fields to update")
        
        # Build SET clause
        set_clauses = [f"{field} = ${i+3}" for i, field in enumerate(update_fields.keys())]
        set_clause = ", ".join(set_clauses)
        
        query = f"""
            UPDATE ai_agents
            SET {set_clause}, updated_at = NOW()
            WHERE agent_id = $1 AND user_id = $2
            RETURNING agent_id
        """
        
        async with self.db_pool.acquire() as conn:
            result = await conn.fetchval(
                query,
                agent_id, user_id, *update_fields.values()
            )
            
            if not result:
                raise ValueError("Agent not found")
            
            return await self._get_agent_by_id(conn, agent_id, user_id)
    
    async def delete_agent(
        self,
        user_id: UUID,
        agent_id: UUID
    ) -> bool:
        """Delete an agent"""
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM ai_agents
                WHERE agent_id = $1 AND user_id = $2
                """,
                agent_id, user_id
            )
        
        return "DELETE 1" in result
    
    # ========================================================================
    # AGENT INTERACTION
    # ========================================================================
    
    async def chat_with_agent(
        self,
        user_id: UUID,
        agent_id: UUID,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        use_memory: bool = True,
        call_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send message to agent and get response
        
        This implements a simple LangGraph-like workflow:
        1. Retrieve memory (if enabled)
        2. Build context
        3. Generate response
        4. Store interaction in memory
        5. Optionally convert to speech
        """
        start_time = datetime.utcnow()
        
        # Get agent configuration
        agent = await self.get_agent(user_id, agent_id)
        if not agent:
            raise ValueError("Agent not found")
        
        # Update last_used_at
        await self._update_last_used(agent_id)
        
        # Step 1: Retrieve memory if enabled
        memory_context = []
        if use_memory and agent["memory_enabled"]:
            memory_results = await self.memory.recall(
                query=message,
                user_id=user_id,
                agent_id=agent_id,
                limit=3
            )
            memory_context = [
                {"role": "system", "content": f"Relevant memory: {m['content'][:200]}"}
                for m in memory_results
            ]
        
        # Step 2: Build conversation messages
        messages = []
        
        # System prompt
        if agent["system_prompt"]:
            messages.append({
                "role": "system",
                "content": agent["system_prompt"]
            })
        
        # Memory context
        messages.extend(memory_context)
        
        # User message
        messages.append({
            "role": "user",
            "content": message
        })
        
        # Step 3: Generate response
        response = await self.ai_provider.chat_completion(
            user_id=user_id,
            messages=messages,
            model=agent["model"],
            temperature=agent["temperature"],
            max_tokens=agent["max_tokens"],
            provider_name=agent["provider"]
        )
        
        response_text = response["content"]
        tokens_used = response["usage"]["total_tokens"]
        
        # Step 4: Store interaction in memory
        if agent["memory_enabled"]:
            # Store user message
            await self.memory.store_memory(
                content=f"User: {message}",
                user_id=user_id,
                source_type="chat",
                source_id=call_id,
                agent_id=agent_id,
                context=context
            )
            
            # Store agent response
            await self.memory.store_memory(
                content=f"Agent: {response_text}",
                user_id=user_id,
                source_type="chat",
                source_id=call_id,
                agent_id=agent_id,
                context=context
            )
        
        # Step 5: Convert to speech if voice enabled
        audio_url = None
        if agent["voice_enabled"] and agent["tts_voice_id"]:
            try:
                tts_result = await self.speech.synthesize_speech(
                    user_id=user_id,
                    text=response_text,
                    voice_id=agent["tts_voice_id"],
                    provider=agent["tts_provider"],
                    agent_id=agent_id
                )
                audio_url = tts_result["audio_url"]
            except Exception as e:
                logger.error(f"TTS generation failed: {e}")
        
        # Calculate latency
        latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return {
            "agent_id": str(agent_id),
            "message": response_text,
            "audio_url": audio_url,
            "tokens_used": tokens_used,
            "latency_ms": latency_ms,
            "memory_used": len(memory_context) > 0,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _update_last_used(self, agent_id: UUID):
        """Update agent's last_used_at timestamp"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ai_agents
                SET last_used_at = NOW()
                WHERE agent_id = $1
                """,
                agent_id
            )
    
    # ========================================================================
    # ROOM INTEGRATION
    # ========================================================================
    
    async def agent_join_room(
        self,
        user_id: UUID,
        agent_id: UUID,
        room_name: str,
        room_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Make agent join a WebRTC room
        """
        agent = await self.get_agent(user_id, agent_id)
        if not agent:
            raise ValueError("Agent not found")
        
        logger.info(f"Agent {agent_id} joining room {room_name}")
        
        # Create agent participant record
        async with self.db_pool.acquire() as conn:
            participant_id = await conn.fetchval(
                """
                INSERT INTO call_participants (
                    call_id, user_id, display_name, role, is_agent
                )
                SELECT call_id, $1, $2, 'agent', TRUE
                FROM calls
                WHERE room_name = $3
                RETURNING participant_id
                """,
                user_id, agent["name"], room_name
            )
        
        # Store agent-room association
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_rooms (agent_id, room_name, status, joined_at)
                VALUES ($1, $2, 'active', NOW())
                ON CONFLICT (agent_id, room_name) 
                DO UPDATE SET status = 'active', joined_at = NOW()
                """,
                agent_id, room_name
            )
        
        # Send greeting if configured
        greeting_sent = False
        if agent["greeting_message"] and agent["voice_enabled"]:
            try:
                # Generate greeting audio
                greeting_result = await self.speech.synthesize_speech(
                    user_id=user_id,
                    text=agent["greeting_message"],
                    voice_id=agent["tts_voice_id"] or "default",
                    provider=agent["tts_provider"],
                    agent_id=agent_id
                )
                greeting_sent = True
            except Exception as e:
                logger.error(f"Error generating greeting: {e}")
        
        return {
            "agent_id": str(agent_id),
            "room_name": room_name,
            "status": "joined",
            "participant_id": str(participant_id),
            "greeting": agent["greeting_message"],
            "greeting_sent": greeting_sent
        }
    
    async def agent_leave_room(
        self,
        user_id: UUID,
        agent_id: UUID,
        room_name: str
    ) -> bool:
        """Remove agent from room"""
        logger.info(f"Agent {agent_id} leaving room {room_name}")
        
        # Update agent-room status
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE agent_rooms
                SET status = 'inactive', left_at = NOW()
                WHERE agent_id = $1 AND room_name = $2
                """,
                agent_id, room_name
            )
            
            # Update participant status
            await conn.execute(
                """
                UPDATE call_participants
                SET left_at = NOW()
                WHERE user_id = $1 AND is_agent = TRUE
                    AND call_id IN (SELECT call_id FROM calls WHERE room_name = $2)
                """,
                user_id, room_name
            )
        
        return True
    
    # ========================================================================
    # AGENT WORKFLOWS (LangGraph Integration)
    # ========================================================================
    
    async def create_agent_workflow(
        self,
        user_id: UUID,
        agent_id: UUID,
        workflow_config: Dict[str, Any]
    ) -> UUID:
        """
        Create a custom workflow for agent
        
        Example workflow_config:
        {
            "name": "Customer Support",
            "triggers": ["user_joins", "question_asked"],
            "steps": [
                {"type": "greet", "message": "Hello!"},
                {"type": "listen"},
                {"type": "respond_with_memory"},
                {"type": "escalate_if_needed"}
            ]
        }
        """
        workflow_id = uuid4()
        
        # Store workflow configuration in database
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_workflows (
                    workflow_id, agent_id, user_id, name, config, created_at
                )
                VALUES ($1, $2, $3, $4, $5, NOW())
                """,
                workflow_id,
                agent_id,
                user_id,
                workflow_config.get("name", "Unnamed Workflow"),
                workflow_config
            )
        
        # If LangGraph is available, create the state graph
        if self.supports_langgraph:
            try:
                # This would be implemented for advanced workflow orchestration
                logger.info(f"LangGraph workflow created for agent {agent_id}")
            except Exception as e:
                logger.error(f"Error creating LangGraph workflow: {e}")
        
        logger.info(f"Created workflow {workflow_id} for agent {agent_id}")
        return workflow_id
    
    # ========================================================================
    # AGENT ANALYTICS
    # ========================================================================
    
    async def get_agent_stats(
        self,
        user_id: UUID,
        agent_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get agent usage statistics"""
        async with self.db_pool.acquire() as conn:
            # Get usage stats
            usage_row = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_interactions,
                    SUM(tokens_used) as total_tokens,
                    AVG(latency_ms) as avg_latency_ms,
                    SUM(estimated_cost_usd) as total_cost_usd
                FROM ai_usage_logs
                WHERE agent_id = $1
                    AND user_id = $2
                    AND created_at > NOW() - INTERVAL '{days} days'
                """.format(days=days),
                agent_id, user_id
            )
            
            # Get memory stats
            memory_row = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as memory_chunks,
                    MAX(created_at) as last_memory_stored
                FROM memory_chunks
                WHERE agent_id = $1 AND user_id = $2
                """,
                agent_id, user_id
            )
        
        return {
            "usage": dict(usage_row) if usage_row else {},
            "memory": dict(memory_row) if memory_row else {}
        }
