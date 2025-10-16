"""
MCP API Endpoints - Model Context Protocol Integration
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from uuid import UUID

from app.api.deps import get_current_user, get_mcp_service

router = APIRouter()


# ========================================================================
# REQUEST/RESPONSE MODELS
# ========================================================================

class MCPConnectionRequest(BaseModel):
    server_type: str = Field(..., description="MCP server type")
    credentials: Optional[Dict[str, Any]] = Field(None, description="Optional credentials")


class MCPConnectionResponse(BaseModel):
    connection_id: UUID
    status: str
    server_type: str
    server_name: Optional[str] = None
    capabilities: Optional[List[str]] = None


class DeepWikiQueryRequest(BaseModel):
    connection_id: UUID
    repo_name: str
    question: Optional[str] = None


class MemorySearchRequest(BaseModel):
    connection_id: UUID
    query: str


class SequentialThinkingRequest(BaseModel):
    connection_id: UUID
    problem: str
    max_thoughts: int = Field(10, ge=1, le=50)


class SupabaseQueryRequest(BaseModel):
    connection_id: UUID
    project_id: str
    query: Optional[str] = None


# ========================================================================
# CONNECTION MANAGEMENT
# ========================================================================

@router.post("/connect", response_model=MCPConnectionResponse)
async def connect_mcp_server(
    request: MCPConnectionRequest,
    user_id: UUID = Depends(get_current_user),
    mcp_service = Depends(get_mcp_service)
):
    """Connect to an MCP server"""
    try:
        result = await mcp_service.connect_mcp_server(
            user_id=user_id,
            server_type=request.server_type,
            credentials=request.credentials
        )
        return MCPConnectionResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/disconnect/{connection_id}")
async def disconnect_mcp_server(
    connection_id: UUID,
    user_id: UUID = Depends(get_current_user),
    mcp_service = Depends(get_mcp_service)
):
    """Disconnect from MCP server"""
    success = await mcp_service.disconnect_mcp_server(user_id, connection_id)
    if not success:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"status": "disconnected", "connection_id": connection_id}


@router.get("/connections")
async def list_mcp_connections(
    user_id: UUID = Depends(get_current_user),
    mcp_service = Depends(get_mcp_service)
):
    """List all MCP connections for user"""
    connections = await mcp_service.list_user_connections(user_id)
    return {"connections": connections, "total": len(connections)}


# ========================================================================
# DEEPWIKI MCP
# ========================================================================

@router.post("/deepwiki/read")
async def deepwiki_read_wiki(
    request: DeepWikiQueryRequest,
    user_id: UUID = Depends(get_current_user),
    mcp_service = Depends(get_mcp_service)
):
    """Read wiki/documentation from GitHub repository"""
    try:
        result = await mcp_service.deepwiki_read_wiki(
            connection_id=request.connection_id,
            repo_name=request.repo_name
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deepwiki/ask")
async def deepwiki_ask_question(
    request: DeepWikiQueryRequest,
    user_id: UUID = Depends(get_current_user),
    mcp_service = Depends(get_mcp_service)
):
    """Ask a question about a GitHub repository"""
    if not request.question:
        raise HTTPException(status_code=400, detail="Question is required")
    
    try:
        result = await mcp_service.deepwiki_ask_question(
            connection_id=request.connection_id,
            repo_name=request.repo_name,
            question=request.question
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========================================================================
# MEMORY MCP
# ========================================================================

@router.post("/memory/search")
async def memory_search_nodes(
    request: MemorySearchRequest,
    user_id: UUID = Depends(get_current_user),
    mcp_service = Depends(get_mcp_service)
):
    """Search nodes in knowledge graph"""
    try:
        results = await mcp_service.memory_search_nodes(
            connection_id=request.connection_id,
            query=request.query
        )
        return {"results": results, "total": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/graph/{connection_id}")
async def memory_read_graph(
    connection_id: UUID,
    user_id: UUID = Depends(get_current_user),
    mcp_service = Depends(get_mcp_service)
):
    """Read entire knowledge graph"""
    try:
        result = await mcp_service.memory_read_graph(connection_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========================================================================
# SEQUENTIAL THINKING MCP
# ========================================================================

@router.post("/sequential-thinking/solve")
async def sequential_thinking(
    request: SequentialThinkingRequest,
    user_id: UUID = Depends(get_current_user),
    mcp_service = Depends(get_mcp_service)
):
    """Execute step-by-step reasoning"""
    try:
        result = await mcp_service.sequential_thinking(
            connection_id=request.connection_id,
            problem=request.problem,
            max_thoughts=request.max_thoughts
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========================================================================
# SUPABASE MCP
# ========================================================================

@router.post("/supabase/query")
async def supabase_execute_sql(
    request: SupabaseQueryRequest,
    user_id: UUID = Depends(get_current_user),
    mcp_service = Depends(get_mcp_service)
):
    """Execute SQL query on Supabase"""
    if not request.query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    try:
        result = await mcp_service.supabase_execute_sql(
            connection_id=request.connection_id,
            query=request.query,
            project_id=request.project_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supabase/tables/{connection_id}")
async def supabase_list_tables(
    connection_id: UUID,
    project_id: str,
    user_id: UUID = Depends(get_current_user),
    mcp_service = Depends(get_mcp_service)
):
    """List tables in Supabase database"""
    try:
        tables = await mcp_service.supabase_list_tables(connection_id, project_id)
        return {"tables": tables, "total": len(tables)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========================================================================
# ANALYTICS
# ========================================================================

@router.get("/usage/stats")
async def get_mcp_usage_stats(
    connection_id: Optional[UUID] = None,
    user_id: UUID = Depends(get_current_user),
    mcp_service = Depends(get_mcp_service)
):
    """Get MCP usage statistics"""
    stats = await mcp_service.get_mcp_usage_stats(user_id, connection_id)
    return stats


@router.get("/usage/popular")
async def get_popular_operations(
    limit: int = 10,
    mcp_service = Depends(get_mcp_service)
):
    """Get most popular MCP operations"""
    operations = await mcp_service.get_popular_mcp_operations(limit)
    return {"operations": operations}
