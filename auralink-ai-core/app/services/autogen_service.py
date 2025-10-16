"""
AutoGen Service - Multi-Agent Conversations
Autonomous multi-agent collaboration and problem-solving
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime

import asyncpg
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

logger = logging.getLogger(__name__)


class AutoGenService:
    """
    AutoGen Integration Service for multi-agent conversations
    
    Features:
    - Autonomous agent conversations
    - Group chat coordination
    - Collaborative problem-solving
    - Dynamic agent interactions
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        ai_provider_service: Any,
        memory_service: Any
    ):
        self.db_pool = db_pool
        self.ai_provider = ai_provider_service
        self.memory = memory_service
        
        # Active group chats
        self.active_chats: Dict[str, GroupChat] = {}
    
    # ========================================================================
    # GROUP CHAT CREATION
    # ========================================================================
    
    async def create_group_chat(
        self,
        team_id: UUID,
        user_id: UUID,
        max_rounds: int = 10,
        admin_name: str = "Admin"
    ) -> Dict[str, Any]:
        """Create an AutoGen group chat for agent team"""
        logger.info(f"Creating AutoGen group chat for team {team_id}")
        
        # Get team members
        async with self.db_pool.acquire() as conn:
            members = await conn.fetch(
                """
                SELECT 
                    tm.agent_id,
                    tm.role,
                    tm.role_description,
                    a.name,
                    a.model,
                    a.provider,
                    a.system_prompt,
                    a.temperature
                FROM team_members tm
                JOIN ai_agents a ON tm.agent_id = a.agent_id
                WHERE tm.team_id = $1
                ORDER BY tm.execution_order
                """,
                team_id
            )
        
        if not members:
            raise ValueError(f"No members found for team {team_id}")
        
        # Create AutoGen agents
        agents = []
        
        for member in members:
            # Configure LLM
            llm_config = {
                "model": member['model'],
                "temperature": member['temperature'] or 0.7,
                "api_key": await self._get_api_key(member['provider'])
            }
            
            # Create assistant agent
            agent = AssistantAgent(
                name=member['name'],
                system_message=member['system_prompt'] or f"You are a {member['role']}.",
                llm_config=llm_config
            )
            
            agents.append(agent)
        
        # Create user proxy for human interaction
        user_proxy = UserProxyAgent(
            name=admin_name,
            human_input_mode="NEVER",
            max_consecutive_auto_reply=10,
            code_execution_config={"use_docker": False}
        )
        
        # Create group chat
        group_chat = GroupChat(
            agents=agents + [user_proxy],
            messages=[],
            max_round=max_rounds
        )
        
        # Create manager
        manager = GroupChatManager(
            groupchat=group_chat,
            llm_config={"model": "gpt-4", "temperature": 0.7}
        )
        
        # Store reference
        chat_id = str(team_id)
        self.active_chats[chat_id] = group_chat
        
        return {
            'chat_id': chat_id,
            'team_id': team_id,
            'agents': [m['name'] for m in members],
            'max_rounds': max_rounds,
            'status': 'ready'
        }
    
    async def start_conversation(
        self,
        team_id: UUID,
        user_id: UUID,
        initial_message: str,
        room_id: Optional[str] = None,
        call_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Start an AutoGen conversation"""
        logger.info(f"Starting AutoGen conversation for team {team_id}")
        
        start_time = datetime.now()
        
        # Create conversation record
        async with self.db_pool.acquire() as conn:
            conversation_id = await conn.fetchval(
                """
                INSERT INTO team_conversations (
                    team_id, room_id, call_id, task_description,
                    conversation_status
                ) VALUES ($1, $2, $3, $4, 'active')
                RETURNING conversation_id
                """,
                team_id, room_id, call_id, initial_message
            )
        
        try:
            # Get or create group chat
            chat_id = str(team_id)
            if chat_id not in self.active_chats:
                await self.create_group_chat(team_id, user_id)
            
            group_chat = self.active_chats[chat_id]
            
            # In a real implementation, we would:
            # 1. Start the group chat with the initial message
            # 2. Let agents converse autonomously
            # 3. Collect all messages
            # 4. Return results
            
            # Simulated conversation for now
            conversation_log = [
                {
                    'speaker': 'User',
                    'message': initial_message,
                    'timestamp': start_time.isoformat()
                },
                {
                    'speaker': 'Agent1',
                    'message': f"I'll help with: {initial_message}",
                    'timestamp': datetime.now().isoformat()
                }
            ]
            
            end_time = datetime.now()
            
            # Update conversation record
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE team_conversations
                    SET 
                        conversation_status = 'completed',
                        conversation_log = $1,
                        completed_at = NOW(),
                        total_messages = $2
                    WHERE conversation_id = $3
                    """,
                    conversation_log,
                    len(conversation_log),
                    conversation_id
                )
            
            logger.info(f"AutoGen conversation completed: {conversation_id}")
            
            return {
                'conversation_id': conversation_id,
                'team_id': team_id,
                'status': 'completed',
                'message_count': len(conversation_log),
                'conversation_log': conversation_log,
                'duration_seconds': (end_time - start_time).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"AutoGen conversation failed: {e}")
            
            # Update conversation with error
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE team_conversations
                    SET 
                        conversation_status = 'failed',
                        completed_at = NOW()
                    WHERE conversation_id = $1
                    """,
                    conversation_id
                )
            
            raise
    
    # ========================================================================
    # SPECIALIZED CONVERSATION PATTERNS
    # ========================================================================
    
    async def run_debate(
        self,
        team_id: UUID,
        user_id: UUID,
        topic: str,
        rounds: int = 5
    ) -> Dict[str, Any]:
        """Run a debate between agents"""
        logger.info(f"Starting debate on topic: {topic}")
        
        return await self.start_conversation(
            team_id=team_id,
            user_id=user_id,
            initial_message=f"Let's debate: {topic}. Each agent should present their perspective."
        )
    
    async def run_brainstorm(
        self,
        team_id: UUID,
        user_id: UUID,
        challenge: str
    ) -> Dict[str, Any]:
        """Run a brainstorming session"""
        logger.info(f"Starting brainstorm on: {challenge}")
        
        return await self.start_conversation(
            team_id=team_id,
            user_id=user_id,
            initial_message=f"Brainstorming session: {challenge}. Each agent contributes creative ideas."
        )
    
    async def run_problem_solving(
        self,
        team_id: UUID,
        user_id: UUID,
        problem: str
    ) -> Dict[str, Any]:
        """Run collaborative problem solving"""
        logger.info(f"Starting problem solving: {problem}")
        
        return await self.start_conversation(
            team_id=team_id,
            user_id=user_id,
            initial_message=f"Problem to solve: {problem}. Let's collaborate on a solution."
        )
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    async def _get_api_key(self, provider: str) -> str:
        """Get API key for provider"""
        # TODO: Implement secure API key retrieval
        return "dummy_api_key"
    
    async def get_conversation_summary(
        self,
        conversation_id: UUID
    ) -> Dict[str, Any]:
        """Get summary of an AutoGen conversation"""
        async with self.db_pool.acquire() as conn:
            conversation = await conn.fetchrow(
                """
                SELECT 
                    c.conversation_id,
                    c.task_description,
                    c.conversation_status,
                    c.conversation_log,
                    c.total_messages,
                    c.started_at,
                    c.completed_at,
                    t.team_name
                FROM team_conversations c
                JOIN agent_teams t ON c.team_id = t.team_id
                WHERE c.conversation_id = $1
                """,
                conversation_id
            )
            
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
            
            return dict(conversation)
    
    async def list_team_conversations(
        self,
        team_id: UUID,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List recent conversations for a team"""
        async with self.db_pool.acquire() as conn:
            conversations = await conn.fetch(
                """
                SELECT 
                    conversation_id,
                    task_description,
                    conversation_status,
                    total_messages,
                    started_at,
                    completed_at
                FROM team_conversations
                WHERE team_id = $1
                ORDER BY started_at DESC
                LIMIT $2
                """,
                team_id, limit
            )
            
            return [dict(c) for c in conversations]
