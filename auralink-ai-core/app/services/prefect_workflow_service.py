"""
Prefect Workflow Service - Dynamic MCP Workflow Orchestration
Adaptive workflow processing with Prefect for complex AI pipelines
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
from datetime import datetime

import asyncpg
from prefect import flow, task, get_run_logger
from prefect.deployments import Deployment
from prefect.server.schemas.schedules import CronSchedule

logger = logging.getLogger(__name__)


class PrefectWorkflowService:
    """
    Prefect-powered Workflow Orchestration Service
    
    Features:
    - Dynamic workflow creation
    - Adaptive processing based on runtime conditions
    - MCP integration workflows
    - Scheduled and event-driven execution
    - Comprehensive monitoring
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        mcp_service: Any,
        memory_service: Any,
        agent_service: Any
    ):
        self.db_pool = db_pool
        self.mcp = mcp_service
        self.memory = memory_service
        self.agent = agent_service
    
    # ========================================================================
    # FLOW DEFINITIONS
    # ========================================================================
    
    @flow(name="mcp_data_ingestion")
    async def mcp_data_ingestion_flow(
        self,
        connection_id: UUID,
        data_source: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ingest data from MCP server into memory system"""
        run_logger = get_run_logger()
        run_logger.info(f"Starting MCP data ingestion from {data_source}")
        
        try:
            # Fetch data from MCP
            if data_source == "deepwiki":
                data = await self._fetch_deepwiki_data(connection_id, config)
            elif data_source == "supabase":
                data = await self._fetch_supabase_data(connection_id, config)
            else:
                raise ValueError(f"Unknown data source: {data_source}")
            
            # Process and store in memory
            processed = await self._process_and_store(data, config)
            
            run_logger.info(f"Ingested {processed['chunks_created']} memory chunks")
            
            return {
                'status': 'success',
                'chunks_created': processed['chunks_created'],
                'source': data_source
            }
            
        except Exception as e:
            run_logger.error(f"MCP ingestion failed: {e}")
            raise
    
    @flow(name="agent_coordination")
    async def agent_coordination_flow(
        self,
        agent_ids: List[UUID],
        task_description: str,
        coordination_mode: str = "sequential"
    ) -> Dict[str, Any]:
        """Coordinate multiple agents to complete a task"""
        run_logger = get_run_logger()
        run_logger.info(f"Coordinating {len(agent_ids)} agents")
        
        results = []
        
        if coordination_mode == "sequential":
            # Execute agents sequentially
            for agent_id in agent_ids:
                result = await self._execute_agent_task(agent_id, task_description)
                results.append(result)
                
                # Adapt based on result
                if result.get('needs_escalation'):
                    run_logger.warning(f"Agent {agent_id} requested escalation")
                    # Could add additional agents or change strategy
        
        elif coordination_mode == "parallel":
            # Execute agents in parallel
            import asyncio
            tasks = [
                self._execute_agent_task(agent_id, task_description)
                for agent_id in agent_ids
            ]
            results = await asyncio.gather(*tasks)
        
        return {
            'status': 'completed',
            'agents_executed': len(agent_ids),
            'results': results
        }
    
    @flow(name="adaptive_mcp_processing")
    async def adaptive_mcp_processing_flow(
        self,
        user_id: UUID,
        query: str,
        mcp_servers: List[str]
    ) -> Dict[str, Any]:
        """Adaptively process query across multiple MCP servers"""
        run_logger = get_run_logger()
        run_logger.info(f"Adaptive MCP processing for query: {query}")
        
        results = {}
        
        for server_type in mcp_servers:
            try:
                # Get user's connection to this server
                connection = await self._get_mcp_connection(user_id, server_type)
                
                if not connection:
                    run_logger.warning(f"No connection found for {server_type}")
                    continue
                
                # Execute query based on server type
                if server_type == "deepwiki":
                    result = await self.mcp.deepwiki_ask_question(
                        connection['connection_id'],
                        repo_name="relevant_repo",
                        question=query
                    )
                elif server_type == "memory":
                    result = await self.mcp.memory_search_nodes(
                        connection['connection_id'],
                        query=query
                    )
                elif server_type == "sequential-thinking":
                    result = await self.mcp.sequential_thinking(
                        connection['connection_id'],
                        problem=query
                    )
                else:
                    result = {'status': 'unsupported'}
                
                results[server_type] = result
                
                # Adaptive decision: if we got good results, might skip other servers
                if self._is_satisfactory_result(result):
                    run_logger.info(f"Satisfactory result from {server_type}, skipping remaining")
                    break
                    
            except Exception as e:
                run_logger.error(f"Error with {server_type}: {e}")
                results[server_type] = {'error': str(e)}
        
        return {
            'query': query,
            'servers_queried': list(results.keys()),
            'results': results
        }
    
    @flow(name="meeting_analysis_pipeline")
    async def meeting_analysis_pipeline_flow(
        self,
        call_id: UUID,
        user_id: UUID
    ) -> Dict[str, Any]:
        """Complete meeting analysis pipeline"""
        run_logger = get_run_logger()
        run_logger.info(f"Starting meeting analysis for call {call_id}")
        
        # Fetch transcript
        transcript = await self._fetch_transcript(call_id)
        
        # Generate summary
        summary = await self._generate_summary(transcript)
        
        # Extract action items
        action_items = await self._extract_action_items(transcript)
        
        # Store in memory
        await self._store_meeting_memory(user_id, call_id, summary, action_items)
        
        # Generate insights
        insights = await self._generate_insights(transcript, summary)
        
        return {
            'call_id': call_id,
            'summary': summary,
            'action_items': action_items,
            'insights': insights
        }
    
    # ========================================================================
    # TASK DEFINITIONS
    # ========================================================================
    
    @task
    async def _fetch_deepwiki_data(
        self,
        connection_id: UUID,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fetch data from DeepWiki MCP"""
        repo = config.get('repo_name', 'default/repo')
        return await self.mcp.deepwiki_read_wiki(connection_id, repo)
    
    @task
    async def _fetch_supabase_data(
        self,
        connection_id: UUID,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fetch data from Supabase MCP"""
        project_id = config.get('project_id')
        tables = await self.mcp.supabase_list_tables(connection_id, project_id)
        return {'tables': tables}
    
    @task
    async def _process_and_store(
        self,
        data: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process data and store in memory"""
        # Simulate processing
        return {'chunks_created': 10, 'status': 'success'}
    
    @task
    async def _execute_agent_task(
        self,
        agent_id: UUID,
        task_description: str
    ) -> Dict[str, Any]:
        """Execute a task with a specific agent"""
        # Simulate agent execution
        return {
            'agent_id': str(agent_id),
            'status': 'completed',
            'output': f"Completed: {task_description}",
            'needs_escalation': False
        }
    
    @task
    async def _fetch_transcript(self, call_id: UUID) -> str:
        """Fetch call transcript"""
        # Fetch from database
        async with self.db_pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT content FROM transcriptions WHERE call_id = $1 ORDER BY created_at DESC LIMIT 1",
                call_id
            )
            return result or "No transcript available"
    
    @task
    async def _generate_summary(self, transcript: str) -> Dict[str, Any]:
        """Generate meeting summary"""
        return {
            'key_points': ['Point 1', 'Point 2'],
            'summary_text': 'Meeting summary...'
        }
    
    @task
    async def _extract_action_items(self, transcript: str) -> List[str]:
        """Extract action items from transcript"""
        return ['Action 1', 'Action 2']
    
    @task
    async def _store_meeting_memory(
        self,
        user_id: UUID,
        call_id: UUID,
        summary: Dict[str, Any],
        action_items: List[str]
    ):
        """Store meeting information in memory"""
        if self.memory:
            await self.memory.store_memory(
                user_id=user_id,
                content=f"Meeting summary: {summary['summary_text']}",
                context={'call_id': str(call_id), 'type': 'meeting'}
            )
    
    @task
    async def _generate_insights(
        self,
        transcript: str,
        summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate insights from meeting"""
        return {
            'sentiment': 'positive',
            'engagement_score': 0.85,
            'topics': ['topic1', 'topic2']
        }
    
    # ========================================================================
    # FLOW MANAGEMENT
    # ========================================================================
    
    async def create_flow(
        self,
        flow_name: str,
        description: Optional[str],
        flow_type: str,
        flow_definition: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new Prefect flow definition"""
        logger.info(f"Creating Prefect flow: {flow_name}")
        
        async with self.db_pool.acquire() as conn:
            flow_id = await conn.fetchval(
                """
                INSERT INTO prefect_flows (
                    flow_name, description, flow_type,
                    flow_definition, parameters, is_active
                ) VALUES ($1, $2, $3, $4, $5, true)
                RETURNING flow_id
                """,
                flow_name, description, flow_type,
                flow_definition, parameters or {}
            )
        
        return {
            'flow_id': flow_id,
            'flow_name': flow_name,
            'flow_type': flow_type
        }
    
    async def execute_flow(
        self,
        flow_id: UUID,
        user_id: UUID,
        input_parameters: Dict[str, Any],
        agent_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Execute a Prefect flow"""
        logger.info(f"Executing flow {flow_id}")
        
        start_time = datetime.now()
        
        # Get flow definition
        async with self.db_pool.acquire() as conn:
            flow_def = await conn.fetchrow(
                """
                SELECT flow_name, flow_type, flow_definition, parameters
                FROM prefect_flows
                WHERE flow_id = $1 AND is_active = true
                """,
                flow_id
            )
            
            if not flow_def:
                raise ValueError(f"Flow {flow_id} not found")
            
            # Create run record
            run_id = await conn.fetchval(
                """
                INSERT INTO prefect_flow_runs (
                    flow_id, user_id, agent_id, run_status, input_parameters
                ) VALUES ($1, $2, $3, 'running', $4)
                RETURNING run_id
                """,
                flow_id, user_id, agent_id, input_parameters
            )
        
        try:
            # Execute the appropriate flow
            flow_type = flow_def['flow_type']
            
            if flow_type == 'mcp_processing':
                result = await self.mcp_data_ingestion_flow(
                    connection_id=UUID(input_parameters['connection_id']),
                    data_source=input_parameters['data_source'],
                    config=input_parameters.get('config', {})
                )
            elif flow_type == 'agent_coordination':
                result = await self.agent_coordination_flow(
                    agent_ids=[UUID(id) for id in input_parameters['agent_ids']],
                    task_description=input_parameters['task_description'],
                    coordination_mode=input_parameters.get('coordination_mode', 'sequential')
                )
            else:
                result = {'status': 'unknown_flow_type'}
            
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Update run record
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE prefect_flow_runs
                    SET 
                        run_status = 'completed',
                        output_data = $1,
                        completed_at = NOW(),
                        duration_ms = $2
                    WHERE run_id = $3
                    """,
                    result, duration_ms, run_id
                )
            
            return {
                'run_id': run_id,
                'flow_id': flow_id,
                'status': 'completed',
                'result': result,
                'duration_ms': duration_ms
            }
            
        except Exception as e:
            logger.error(f"Flow execution failed: {e}")
            
            # Update with error
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE prefect_flow_runs
                    SET 
                        run_status = 'failed',
                        error_message = $1,
                        completed_at = NOW()
                    WHERE run_id = $2
                    """,
                    str(e), run_id
                )
            
            raise
    
    async def list_flows(
        self,
        flow_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List available flows"""
        query = "SELECT flow_id, flow_name, description, flow_type, is_active FROM prefect_flows WHERE is_active = true"
        params = []
        
        if flow_type:
            params.append(flow_type)
            query += f" AND flow_type = ${len(params)}"
        
        query += " ORDER BY flow_name"
        
        async with self.db_pool.acquire() as conn:
            flows = await conn.fetch(query, *params)
            return [dict(f) for f in flows]
    
    async def get_flow_runs(
        self,
        flow_id: UUID,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get recent runs of a flow"""
        async with self.db_pool.acquire() as conn:
            runs = await conn.fetch(
                """
                SELECT 
                    run_id, run_status, started_at, completed_at,
                    duration_ms, error_message
                FROM prefect_flow_runs
                WHERE flow_id = $1
                ORDER BY started_at DESC
                LIMIT $2
                """,
                flow_id, limit
            )
            
            return [dict(r) for r in runs]
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    async def _get_mcp_connection(
        self,
        user_id: UUID,
        server_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get user's MCP connection"""
        async with self.db_pool.acquire() as conn:
            connection = await conn.fetchrow(
                """
                SELECT umc.connection_id, umc.credentials
                FROM user_mcp_connections umc
                JOIN mcp_servers ms ON umc.server_id = ms.server_id
                WHERE umc.user_id = $1 
                  AND ms.server_type = $2 
                  AND umc.is_active = true
                """,
                user_id, server_type
            )
            
            return dict(connection) if connection else None
    
    def _is_satisfactory_result(self, result: Dict[str, Any]) -> bool:
        """Determine if result is satisfactory"""
        # Simple heuristic - can be made more sophisticated
        return result.get('status') == 'success' or len(str(result)) > 100
