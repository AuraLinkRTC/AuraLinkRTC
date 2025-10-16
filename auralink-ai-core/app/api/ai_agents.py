"""
AI Agents API endpoints
"""

from fastapi import APIRouter, Depends, Header, status
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.core.exceptions import AuraError, ErrorCode
from app.api.deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


# Request/Response models
class AgentConfig(BaseModel):
    """Agent configuration"""
    name: str = Field(..., description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    model: str = Field("gpt-4", description="LLM model to use")
    temperature: float = Field(0.7, ge=0, le=2, description="Model temperature")
    max_tokens: int = Field(2000, gt=0, description="Maximum tokens")
    system_prompt: Optional[str] = Field(None, description="System prompt")
    auto_join_rooms: bool = Field(False, description="Auto-join new rooms")
    memory_enabled: bool = Field(True, description="Enable memory")


class AgentResponse(BaseModel):
    """Agent response"""
    agent_id: str
    user_id: str
    name: str
    description: Optional[str]
    config: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AgentMessage(BaseModel):
    """Message to agent"""
    message: str = Field(..., description="Message text")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class AgentReply(BaseModel):
    """Agent reply"""
    agent_id: str
    message: str
    timestamp: datetime
    tokens_used: int


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=AgentResponse)
async def create_agent(
    config: AgentConfig,
    user: Dict[str, Any] = Depends(get_current_user)
) -> AgentResponse:
    """
    Create a new AI agent
    """
    from uuid import UUID
    from app.core.dependencies import get_agent_service
    
    logger.info(f"Creating AI agent for user {user['user_id']}")
    
    agent_service = get_agent_service()
    
    agent = await agent_service.create_agent(
        user_id=UUID(user["user_id"]),
        name=config.name,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        system_prompt=config.system_prompt,
        description=config.description,
        memory_enabled=config.memory_enabled,
        auto_join_rooms=config.auto_join_rooms
    )
    
    return AgentResponse(
        agent_id=str(agent["agent_id"]),
        user_id=user["user_id"],
        name=agent["name"],
        description=agent["description"],
        config=config.model_dump(),
        is_active=agent["is_active"],
        created_at=agent["created_at"],
        updated_at=agent["updated_at"]
    )


@router.get("/", response_model=List[AgentResponse])
async def list_agents(
    user: Dict[str, Any] = Depends(get_current_user),
    skip: int = 0,
    limit: int = 10
) -> List[AgentResponse]:
    """
    List user's AI agents
    """
    from uuid import UUID
    from app.core.dependencies import get_agent_service
    
    logger.info(f"Listing agents for user {user['user_id']}")
    
    agent_service = get_agent_service()
    agents = await agent_service.list_agents(
        user_id=UUID(user["user_id"]),
        skip=skip,
        limit=limit
    )
    
    return [
        AgentResponse(
            agent_id=str(a["agent_id"]),
            user_id=user["user_id"],
            name=a["name"],
            description=a.get("description"),
            config={"model": a["model"]},
            is_active=a["is_active"],
            created_at=a["created_at"],
            updated_at=a.get("created_at")
        )
        for a in agents
    ]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
) -> AgentResponse:
    """
    Get agent details
    """
    logger.info(f"Getting agent {agent_id} for user {user['user_id']}")
    
    # TODO: Implement database query
    raise AuraError(
        code=ErrorCode.NOT_FOUND,
        message="Agent not found",
        status_code=404
    )


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    config: AgentConfig,
    user: Dict[str, Any] = Depends(get_current_user)
) -> AgentResponse:
    """
    Update agent configuration
    """
    logger.info(f"Updating agent {agent_id} for user {user['user_id']}")
    
    # TODO: Implement database update
    raise AuraError(
        code=ErrorCode.NOT_FOUND,
        message="Agent not found",
        status_code=404
    )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete an agent
    """
    logger.info(f"Deleting agent {agent_id} for user {user['user_id']}")
    
    # TODO: Implement database deletion
    return


@router.post("/{agent_id}/chat", response_model=AgentReply)
async def chat_with_agent(
    agent_id: str,
    message: AgentMessage,
    user: Dict[str, Any] = Depends(get_current_user)
) -> AgentReply:
    """
    Send a message to an agent and get a reply
    """
    from uuid import UUID
    from app.core.dependencies import get_agent_service
    
    logger.info(f"Chat with agent {agent_id} from user {user['user_id']}")
    
    agent_service = get_agent_service()
    
    result = await agent_service.chat_with_agent(
        user_id=UUID(user["user_id"]),
        agent_id=UUID(agent_id),
        message=message.message,
        context=message.context
    )
    
    return AgentReply(
        agent_id=agent_id,
        message=result["message"],
        timestamp=datetime.fromisoformat(result["timestamp"]),
        tokens_used=result["tokens_used"]
    )


@router.post("/{agent_id}/join-room")
async def agent_join_room(
    agent_id: str,
    room_name: str,
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Make agent join a room
    """
    logger.info(f"Agent {agent_id} joining room {room_name}")
    
    # TODO: Implement WebRTC room joining logic
    return {
        "agent_id": agent_id,
        "room_name": room_name,
        "status": "joined"
    }
