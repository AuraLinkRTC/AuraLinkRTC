"""
Agent Teams API Endpoints - CrewAI & AutoGen Integration
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from uuid import UUID

from app.api.deps import get_current_user, get_crewai_service, get_autogen_service

router = APIRouter()


# ========================================================================
# REQUEST/RESPONSE MODELS
# ========================================================================

class TeamCreateRequest(BaseModel):
    team_name: str
    description: Optional[str] = None
    collaboration_mode: str = Field("sequential", description="sequential, hierarchical, consensus")
    config: Optional[Dict[str, Any]] = None


class TeamMemberRequest(BaseModel):
    team_id: UUID
    agent_id: UUID
    role: str
    role_description: Optional[str] = None
    execution_order: int = 0
    can_delegate: bool = False
    tools: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None


class TeamTaskRequest(BaseModel):
    team_id: UUID
    task_description: str
    room_id: Optional[str] = None
    call_id: Optional[UUID] = None
    additional_context: Optional[Dict[str, Any]] = None


class AutoGenConversationRequest(BaseModel):
    team_id: UUID
    initial_message: str
    room_id: Optional[str] = None
    call_id: Optional[UUID] = None


class AutoGenDebateRequest(BaseModel):
    team_id: UUID
    topic: str
    rounds: int = 5


# ========================================================================
# TEAM MANAGEMENT
# ========================================================================

@router.post("/teams")
async def create_team(
    request: TeamCreateRequest,
    user_id: UUID = Depends(get_current_user),
    crewai_service = Depends(get_crewai_service)
):
    """Create a new agent team"""
    try:
        team = await crewai_service.create_agent_team(
            user_id=user_id,
            team_name=request.team_name,
            description=request.description,
            collaboration_mode=request.collaboration_mode,
            config=request.config
        )
        return team
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/teams/members")
async def add_team_member(
    request: TeamMemberRequest,
    user_id: UUID = Depends(get_current_user),
    crewai_service = Depends(get_crewai_service)
):
    """Add a member to an agent team"""
    try:
        member = await crewai_service.add_team_member(
            team_id=request.team_id,
            agent_id=request.agent_id,
            role=request.role,
            role_description=request.role_description,
            execution_order=request.execution_order,
            can_delegate=request.can_delegate,
            tools=request.tools,
            config=request.config
        )
        return member
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/teams")
async def list_teams(
    user_id: UUID = Depends(get_current_user),
    crewai_service = Depends(get_crewai_service)
):
    """List all teams for user"""
    teams = await crewai_service.list_user_teams(user_id)
    return {"teams": teams, "total": len(teams)}


@router.get("/teams/{team_id}/members")
async def get_team_members(
    team_id: UUID,
    user_id: UUID = Depends(get_current_user),
    crewai_service = Depends(get_crewai_service)
):
    """Get members of a team"""
    members = await crewai_service.get_team_members(team_id)
    return {"members": members, "total": len(members)}


@router.get("/teams/{team_id}/performance")
async def get_team_performance(
    team_id: UUID,
    user_id: UUID = Depends(get_current_user),
    crewai_service = Depends(get_crewai_service)
):
    """Get team performance metrics"""
    performance = await crewai_service.get_team_performance(team_id)
    return performance


@router.get("/teams/{team_id}/conversations")
async def get_team_conversations(
    team_id: UUID,
    limit: int = 10,
    user_id: UUID = Depends(get_current_user),
    crewai_service = Depends(get_crewai_service)
):
    """Get team conversation history"""
    conversations = await crewai_service.get_team_conversation_history(team_id, limit)
    return {"conversations": conversations, "total": len(conversations)}


# ========================================================================
# CREWAI EXECUTION
# ========================================================================

@router.post("/crewai/execute")
async def execute_team_task(
    request: TeamTaskRequest,
    user_id: UUID = Depends(get_current_user),
    crewai_service = Depends(get_crewai_service)
):
    """Execute a task with CrewAI team"""
    try:
        result = await crewai_service.execute_team_task(
            team_id=request.team_id,
            user_id=user_id,
            task_description=request.task_description,
            room_id=request.room_id,
            call_id=request.call_id,
            additional_context=request.additional_context
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========================================================================
# PRE-BUILT TEAM TEMPLATES
# ========================================================================

@router.post("/templates/research")
async def create_research_team(
    team_name: str = "Research Team",
    user_id: UUID = Depends(get_current_user),
    crewai_service = Depends(get_crewai_service)
):
    """Create a research-focused team"""
    team = await crewai_service.create_research_team(user_id, team_name)
    return team


@router.post("/templates/content")
async def create_content_team(
    team_name: str = "Content Team",
    user_id: UUID = Depends(get_current_user),
    crewai_service = Depends(get_crewai_service)
):
    """Create a content creation team"""
    team = await crewai_service.create_content_team(user_id, team_name)
    return team


@router.post("/templates/support")
async def create_support_team(
    team_name: str = "Support Team",
    user_id: UUID = Depends(get_current_user),
    crewai_service = Depends(get_crewai_service)
):
    """Create a customer support team"""
    team = await crewai_service.create_support_team(user_id, team_name)
    return team


# ========================================================================
# AUTOGEN MULTI-AGENT CONVERSATIONS
# ========================================================================

@router.post("/autogen/conversation")
async def start_autogen_conversation(
    request: AutoGenConversationRequest,
    user_id: UUID = Depends(get_current_user),
    autogen_service = Depends(get_autogen_service)
):
    """Start an AutoGen multi-agent conversation"""
    try:
        result = await autogen_service.start_conversation(
            team_id=request.team_id,
            user_id=user_id,
            initial_message=request.initial_message,
            room_id=request.room_id,
            call_id=request.call_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/autogen/debate")
async def run_debate(
    request: AutoGenDebateRequest,
    user_id: UUID = Depends(get_current_user),
    autogen_service = Depends(get_autogen_service)
):
    """Run an AutoGen debate"""
    try:
        result = await autogen_service.run_debate(
            team_id=request.team_id,
            user_id=user_id,
            topic=request.topic,
            rounds=request.rounds
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/autogen/brainstorm/{team_id}")
async def run_brainstorm(
    team_id: UUID,
    challenge: str,
    user_id: UUID = Depends(get_current_user),
    autogen_service = Depends(get_autogen_service)
):
    """Run an AutoGen brainstorming session"""
    try:
        result = await autogen_service.run_brainstorm(
            team_id=team_id,
            user_id=user_id,
            challenge=challenge
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/autogen/conversations/{conversation_id}")
async def get_conversation_summary(
    conversation_id: UUID,
    user_id: UUID = Depends(get_current_user),
    autogen_service = Depends(get_autogen_service)
):
    """Get summary of an AutoGen conversation"""
    try:
        summary = await autogen_service.get_conversation_summary(conversation_id)
        return summary
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/autogen/conversations/team/{team_id}")
async def list_team_conversations_autogen(
    team_id: UUID,
    limit: int = 20,
    user_id: UUID = Depends(get_current_user),
    autogen_service = Depends(get_autogen_service)
):
    """List AutoGen conversations for a team"""
    conversations = await autogen_service.list_team_conversations(team_id, limit)
    return {"conversations": conversations, "total": len(conversations)}
