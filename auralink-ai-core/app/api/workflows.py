"""
Workflow API Endpoints - Agent Workflows & Prefect Integration
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from uuid import UUID

from app.api.deps import get_current_user, get_langgraph_service, get_prefect_service

router = APIRouter()


# ========================================================================
# REQUEST/RESPONSE MODELS
# ========================================================================

class WorkflowCreateRequest(BaseModel):
    agent_id: UUID
    workflow_name: str
    workflow_type: str = Field(..., description="auto_join, summarization, moderation, qa, custom")
    description: Optional[str] = None
    trigger_conditions: Optional[List[Dict[str, Any]]] = None
    workflow_steps: Optional[Dict[str, Any]] = None
    mcp_integrations: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None


class WorkflowExecuteRequest(BaseModel):
    workflow_id: UUID
    agent_id: UUID
    input_data: Dict[str, Any]
    room_id: Optional[str] = None
    call_id: Optional[UUID] = None


class PrefectFlowCreateRequest(BaseModel):
    flow_name: str
    description: Optional[str] = None
    flow_type: str = Field(..., description="mcp_processing, agent_coordination, data_pipeline")
    flow_definition: Dict[str, Any]
    parameters: Optional[Dict[str, Any]] = None


class PrefectFlowExecuteRequest(BaseModel):
    flow_id: UUID
    input_parameters: Dict[str, Any]
    agent_id: Optional[UUID] = None


# ========================================================================
# AGENT WORKFLOWS (LangGraph)
# ========================================================================

@router.post("/agent-workflows")
async def create_agent_workflow(
    request: WorkflowCreateRequest,
    user_id: UUID = Depends(get_current_user),
    langgraph_service = Depends(get_langgraph_service)
):
    """Create a new agent workflow"""
    try:
        workflow = await langgraph_service.create_workflow(
            agent_id=request.agent_id,
            workflow_name=request.workflow_name,
            workflow_type=request.workflow_type,
            description=request.description,
            trigger_conditions=request.trigger_conditions,
            workflow_steps=request.workflow_steps,
            mcp_integrations=request.mcp_integrations,
            config=request.config
        )
        return workflow
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/agent-workflows/execute")
async def execute_workflow(
    request: WorkflowExecuteRequest,
    user_id: UUID = Depends(get_current_user),
    langgraph_service = Depends(get_langgraph_service)
):
    """Execute an agent workflow"""
    try:
        result = await langgraph_service.execute_workflow(
            workflow_id=request.workflow_id,
            agent_id=request.agent_id,
            user_id=user_id,
            input_data=request.input_data,
            room_id=request.room_id,
            call_id=request.call_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent-workflows/agent/{agent_id}")
async def list_agent_workflows(
    agent_id: UUID,
    user_id: UUID = Depends(get_current_user),
    langgraph_service = Depends(get_langgraph_service)
):
    """List workflows for an agent"""
    workflows = await langgraph_service.list_agent_workflows(agent_id)
    return {"workflows": workflows, "total": len(workflows)}


@router.get("/agent-workflows/{workflow_id}/stats")
async def get_workflow_stats(
    workflow_id: UUID,
    user_id: UUID = Depends(get_current_user),
    langgraph_service = Depends(get_langgraph_service)
):
    """Get workflow execution statistics"""
    stats = await langgraph_service.get_workflow_stats(workflow_id)
    return stats


# ========================================================================
# PREFECT FLOWS
# ========================================================================

@router.post("/prefect-flows")
async def create_prefect_flow(
    request: PrefectFlowCreateRequest,
    user_id: UUID = Depends(get_current_user),
    prefect_service = Depends(get_prefect_service)
):
    """Create a new Prefect flow"""
    try:
        flow = await prefect_service.create_flow(
            flow_name=request.flow_name,
            description=request.description,
            flow_type=request.flow_type,
            flow_definition=request.flow_definition,
            parameters=request.parameters
        )
        return flow
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/prefect-flows/execute")
async def execute_prefect_flow(
    request: PrefectFlowExecuteRequest,
    user_id: UUID = Depends(get_current_user),
    prefect_service = Depends(get_prefect_service)
):
    """Execute a Prefect flow"""
    try:
        result = await prefect_service.execute_flow(
            flow_id=request.flow_id,
            user_id=user_id,
            input_parameters=request.input_parameters,
            agent_id=request.agent_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prefect-flows")
async def list_prefect_flows(
    flow_type: Optional[str] = None,
    prefect_service = Depends(get_prefect_service)
):
    """List available Prefect flows"""
    flows = await prefect_service.list_flows(flow_type)
    return {"flows": flows, "total": len(flows)}


@router.get("/prefect-flows/{flow_id}/runs")
async def get_flow_runs(
    flow_id: UUID,
    limit: int = 20,
    prefect_service = Depends(get_prefect_service)
):
    """Get recent runs of a flow"""
    runs = await prefect_service.get_flow_runs(flow_id, limit)
    return {"runs": runs, "total": len(runs)}
