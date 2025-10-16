"""
CrewAI Service - Role-Based Agent Teams
Multi-agent collaboration with specialized roles and workflows
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime

import asyncpg
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

logger = logging.getLogger(__name__)


class CrewAIService:
    """
    CrewAI Integration Service for multi-agent collaboration
    
    Features:
    - Role-based agent teams
    - Collaborative task execution
    - Sequential and hierarchical workflows
    - Specialized agent roles (researcher, writer, reviewer, etc.)
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        ai_provider_service: Any,
        memory_service: Any,
        mcp_service: Any
    ):
        self.db_pool = db_pool
        self.ai_provider = ai_provider_service
        self.memory = memory_service
        self.mcp = mcp_service
        
        # Active crews cache
        self.active_crews: Dict[str, Crew] = {}
    
    # ========================================================================
    # TEAM MANAGEMENT
    # ========================================================================
    
    async def create_agent_team(
        self,
        user_id: UUID,
        team_name: str,
        description: Optional[str] = None,
        collaboration_mode: str = "sequential",
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new agent team"""
        logger.info(f"Creating agent team '{team_name}' for user {user_id}")
        
        async with self.db_pool.acquire() as conn:
            team_id = await conn.fetchval(
                """
                INSERT INTO agent_teams (
                    user_id, team_name, description, team_type,
                    collaboration_mode, config, is_active
                ) VALUES ($1, $2, $3, 'crewai', $4, $5, true)
                RETURNING team_id
                """,
                user_id, team_name, description,
                collaboration_mode, config or {}
            )
        
        return {
            'team_id': team_id,
            'team_name': team_name,
            'collaboration_mode': collaboration_mode,
            'status': 'created'
        }
    
    async def add_team_member(
        self,
        team_id: UUID,
        agent_id: UUID,
        role: str,
        role_description: Optional[str] = None,
        execution_order: int = 0,
        can_delegate: bool = False,
        tools: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add an agent to a team with specific role"""
        logger.info(f"Adding agent {agent_id} to team {team_id} as {role}")
        
        async with self.db_pool.acquire() as conn:
            member_id = await conn.fetchval(
                """
                INSERT INTO team_members (
                    team_id, agent_id, role, role_description,
                    execution_order, can_delegate, tools, config
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING member_id
                """,
                team_id, agent_id, role, role_description,
                execution_order, can_delegate, tools or [], config or {}
            )
        
        return {
            'member_id': member_id,
            'team_id': team_id,
            'agent_id': agent_id,
            'role': role
        }
    
    async def get_team_members(
        self,
        team_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get all members of a team"""
        async with self.db_pool.acquire() as conn:
            members = await conn.fetch(
                """
                SELECT 
                    tm.member_id,
                    tm.agent_id,
                    tm.role,
                    tm.role_description,
                    tm.execution_order,
                    tm.can_delegate,
                    tm.tools,
                    a.name AS agent_name,
                    a.model,
                    a.provider
                FROM team_members tm
                JOIN ai_agents a ON tm.agent_id = a.agent_id
                WHERE tm.team_id = $1
                ORDER BY tm.execution_order ASC
                """,
                team_id
            )
            
            return [dict(m) for m in members]
    
    # ========================================================================
    # CREW EXECUTION
    # ========================================================================
    
    async def execute_team_task(
        self,
        team_id: UUID,
        user_id: UUID,
        task_description: str,
        room_id: Optional[str] = None,
        call_id: Optional[UUID] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a collaborative task with agent team"""
        logger.info(f"Executing team task for team {team_id}")
        
        start_time = datetime.now()
        
        # Get team configuration
        async with self.db_pool.acquire() as conn:
            team_config = await conn.fetchrow(
                """
                SELECT 
                    team_name, collaboration_mode, config
                FROM agent_teams
                WHERE team_id = $1 AND user_id = $2 AND is_active = true
                """,
                team_id, user_id
            )
            
            if not team_config:
                raise ValueError(f"Team {team_id} not found or inactive")
            
            # Create conversation record
            conversation_id = await conn.fetchval(
                """
                INSERT INTO team_conversations (
                    team_id, room_id, call_id, task_description,
                    conversation_status
                ) VALUES ($1, $2, $3, $4, 'active')
                RETURNING conversation_id
                """,
                team_id, room_id, call_id, task_description
            )
        
        try:
            # Get team members
            members = await self.get_team_members(team_id)
            
            if not members:
                raise ValueError(f"Team {team_id} has no members")
            
            # Build CrewAI agents and tasks
            crew_agents = []
            crew_tasks = []
            
            for member in members:
                # Create CrewAI agent
                agent = await self._create_crew_agent(member)
                crew_agents.append(agent)
                
                # Create task for this agent
                task = await self._create_crew_task(
                    agent=agent,
                    member=member,
                    task_description=task_description,
                    context=additional_context
                )
                crew_tasks.append(task)
            
            # Determine process type
            process = Process.sequential
            if team_config['collaboration_mode'] == 'hierarchical':
                process = Process.hierarchical
            
            # Create and execute crew
            crew = Crew(
                agents=crew_agents,
                tasks=crew_tasks,
                process=process,
                verbose=True
            )
            
            # Execute crew tasks
            result = crew.kickoff()
            
            # Process results
            end_time = datetime.now()
            
            # Update conversation record
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE team_conversations
                    SET 
                        conversation_status = 'completed',
                        result_data = $1,
                        completed_at = NOW(),
                        total_messages = $2
                    WHERE conversation_id = $3
                    """,
                    {'result': str(result)},
                    len(crew_agents),
                    conversation_id
                )
            
            logger.info(f"Team task completed: {conversation_id}")
            
            return {
                'conversation_id': conversation_id,
                'team_id': team_id,
                'status': 'completed',
                'result': str(result),
                'agents_involved': len(crew_agents),
                'duration_seconds': (end_time - start_time).total_seconds()
            }
            
        except Exception as e:
            logger.error(f"Team task execution failed: {e}")
            
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
    
    async def _create_crew_agent(
        self,
        member: Dict[str, Any]
    ) -> Agent:
        """Create a CrewAI agent from team member configuration"""
        
        # Get LLM for this agent
        llm = await self._get_llm_for_agent(member)
        
        agent = Agent(
            role=member['role'],
            goal=member.get('role_description', f"Execute {member['role']} tasks"),
            backstory=f"An AI agent specialized in {member['role']} responsibilities",
            verbose=True,
            allow_delegation=member.get('can_delegate', False),
            llm=llm,
            tools=await self._get_agent_tools(member)
        )
        
        return agent
    
    async def _create_crew_task(
        self,
        agent: Agent,
        member: Dict[str, Any],
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Task:
        """Create a CrewAI task for an agent"""
        
        # Customize task description based on role
        role_specific_description = f"""
        As a {member['role']}, your task is to:
        {task_description}
        
        Additional context: {context or 'None'}
        """
        
        task = Task(
            description=role_specific_description,
            agent=agent,
            expected_output=f"Completed {member['role']} analysis and recommendations"
        )
        
        return task
    
    async def _get_llm_for_agent(
        self,
        member: Dict[str, Any]
    ) -> Any:
        """Get LLM instance for agent"""
        provider = member.get('provider', 'openai')
        model = member.get('model', 'gpt-4')
        
        if provider == 'openai':
            return ChatOpenAI(model=model, temperature=0.7)
        elif provider == 'anthropic':
            return ChatAnthropic(model=model, temperature=0.7)
        else:
            return ChatOpenAI(model='gpt-4', temperature=0.7)
    
    async def _get_agent_tools(
        self,
        member: Dict[str, Any]
    ) -> List[Any]:
        """Get tools available to agent based on configuration"""
        from langchain.tools import Tool
        from langchain_community.tools import DuckDuckGoSearchRun
        
        tools = []
        configured_tools = member.get('tools', [])
        
        # Load tools based on configuration
        for tool_name in configured_tools:
            try:
                if tool_name == 'web_search':
                    # Web search tool
                    search = DuckDuckGoSearchRun()
                    tools.append(Tool(
                        name="WebSearch",
                        func=search.run,
                        description="Search the web for current information. Input should be a search query."
                    ))
                
                elif tool_name == 'calculator':
                    # Calculator tool
                    def calculator(expression: str) -> str:
                        try:
                            return str(eval(expression))
                        except Exception as e:
                            return f"Error: {str(e)}"
                    
                    tools.append(Tool(
                        name="Calculator",
                        func=calculator,
                        description="Perform mathematical calculations. Input should be a mathematical expression."
                    ))
                
                elif tool_name == 'memory_search':
                    # Memory search tool (if memory service is available)
                    if self.memory:
                        async def memory_search(query: str) -> str:
                            try:
                                results = await self.memory.recall(
                                    user_id=member['agent_id'],
                                    query=query,
                                    limit=3
                                )
                                return str(results)
                            except Exception as e:
                                return f"Memory search failed: {str(e)}"
                        
                        tools.append(Tool(
                            name="MemorySearch",
                            func=lambda q: asyncio.run(memory_search(q)),
                            description="Search the agent's memory for relevant information."
                        ))
                
                elif tool_name == 'mcp_deepwiki':
                    # MCP DeepWiki tool (if MCP service is available)
                    if self.mcp:
                        async def deepwiki_search(query: str) -> str:
                            try:
                                # This would need a connection_id - placeholder for now
                                return f"DeepWiki search for: {query}"
                            except Exception as e:
                                return f"DeepWiki search failed: {str(e)}"
                        
                        tools.append(Tool(
                            name="DeepWikiSearch",
                            func=lambda q: asyncio.run(deepwiki_search(q)),
                            description="Search GitHub repositories and documentation."
                        ))
                
                elif tool_name == 'code_analyzer':
                    # Code analysis tool
                    def analyze_code(code: str) -> str:
                        lines = code.split('\n')
                        return f"Code analysis: {len(lines)} lines, approximately {len(code)} characters"
                    
                    tools.append(Tool(
                        name="CodeAnalyzer",
                        func=analyze_code,
                        description="Analyze code structure and provide insights."
                    ))
                
                else:
                    logger.warning(f"Unknown tool type: {tool_name}")
                    
            except Exception as e:
                logger.error(f"Failed to load tool {tool_name}: {e}")
        
        return tools
    
    # ========================================================================
    # PRE-BUILT TEAM TEMPLATES
    # ========================================================================
    
    async def create_research_team(
        self,
        user_id: UUID,
        team_name: str = "Research Team"
    ) -> Dict[str, Any]:
        """Create a research-focused agent team"""
        
        # Create team
        team = await self.create_agent_team(
            user_id=user_id,
            team_name=team_name,
            description="Collaborative research team with specialized roles",
            collaboration_mode="sequential"
        )
        
        team_id = team['team_id']
        
        # We would add agents here in a real implementation
        # For now, return the team structure
        
        return {
            'team_id': team_id,
            'team_name': team_name,
            'template': 'research',
            'roles': ['researcher', 'analyst', 'writer'],
            'description': 'Team configured for research and analysis tasks'
        }
    
    async def create_content_team(
        self,
        user_id: UUID,
        team_name: str = "Content Team"
    ) -> Dict[str, Any]:
        """Create a content creation team"""
        
        team = await self.create_agent_team(
            user_id=user_id,
            team_name=team_name,
            description="Content creation team with writer, editor, and reviewer",
            collaboration_mode="sequential"
        )
        
        return {
            'team_id': team['team_id'],
            'team_name': team_name,
            'template': 'content',
            'roles': ['writer', 'editor', 'reviewer'],
            'description': 'Team configured for content creation and review'
        }
    
    async def create_support_team(
        self,
        user_id: UUID,
        team_name: str = "Support Team"
    ) -> Dict[str, Any]:
        """Create a customer support team"""
        
        team = await self.create_agent_team(
            user_id=user_id,
            team_name=team_name,
            description="Customer support team with triage, specialist, and escalation agents",
            collaboration_mode="hierarchical"
        )
        
        return {
            'team_id': team['team_id'],
            'team_name': team_name,
            'template': 'support',
            'roles': ['triage', 'specialist', 'escalation'],
            'description': 'Team configured for customer support workflows'
        }
    
    # ========================================================================
    # ANALYTICS & INSIGHTS
    # ========================================================================
    
    async def get_team_performance(
        self,
        team_id: UUID
    ) -> Dict[str, Any]:
        """Get team performance metrics"""
        async with self.db_pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) AS total_conversations,
                    AVG(total_messages) AS avg_messages,
                    COUNT(CASE WHEN conversation_status = 'completed' THEN 1 END) AS completed,
                    COUNT(CASE WHEN conversation_status = 'failed' THEN 1 END) AS failed,
                    SUM(total_tokens) AS total_tokens,
                    SUM(total_cost_usd) AS total_cost_usd,
                    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) AS avg_duration_seconds
                FROM team_conversations
                WHERE team_id = $1
                """,
                team_id
            )
            
            return dict(stats) if stats else {}
    
    async def list_user_teams(
        self,
        user_id: UUID
    ) -> List[Dict[str, Any]]:
        """List all teams for a user"""
        async with self.db_pool.acquire() as conn:
            teams = await conn.fetch(
                """
                SELECT 
                    team_id,
                    team_name,
                    description,
                    team_type,
                    collaboration_mode,
                    is_active,
                    created_at,
                    (SELECT COUNT(*) FROM team_members WHERE team_id = at.team_id) AS member_count
                FROM agent_teams at
                WHERE user_id = $1
                ORDER BY created_at DESC
                """,
                user_id
            )
            
            return [dict(t) for t in teams]
    
    async def get_team_conversation_history(
        self,
        team_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent team conversations"""
        async with self.db_pool.acquire() as conn:
            conversations = await conn.fetch(
                """
                SELECT 
                    conversation_id,
                    task_description,
                    conversation_status,
                    started_at,
                    completed_at,
                    total_messages,
                    total_tokens
                FROM team_conversations
                WHERE team_id = $1
                ORDER BY started_at DESC
                LIMIT $2
                """,
                team_id, limit
            )
            
            return [dict(c) for c in conversations]
