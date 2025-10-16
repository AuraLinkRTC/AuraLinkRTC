"""
Memory API endpoints
Adapted from SuperMemory.ai architecture
"""

from fastapi import APIRouter, Depends, status
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.api.deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


class MemoryStore(BaseModel):
    """Store memory"""
    content: str = Field(..., description="Memory content")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata")


class MemoryQuery(BaseModel):
    """Query memory"""
    query: str = Field(..., description="Search query")
    limit: int = Field(5, gt=0, le=50, description="Number of results")
    threshold: float = Field(0.7, ge=0, le=1, description="Similarity threshold")


class MemoryResult(BaseModel):
    """Memory search result"""
    memory_id: str
    content: str
    score: float
    context: Optional[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime


@router.post("/store", status_code=status.HTTP_201_CREATED)
async def store_memory(
    memory: MemoryStore,
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Store memory for a user
    Implements the Connect→Ingest→Embed→Index pipeline
    """
    from uuid import UUID
    from app.core.dependencies import get_memory_service
    
    logger.info(f"Storing memory for user {user['user_id']}")
    
    memory_service = get_memory_service()
    
    # Store memory through complete pipeline
    chunk_ids = await memory_service.store_memory(
        content=memory.content,
        user_id=UUID(user["user_id"]),
        source_type="external",
        context=memory.context,
        metadata=memory.metadata
    )
    
    return {
        "memory_ids": [str(cid) for cid in chunk_ids],
        "chunks_created": len(chunk_ids),
        "user_id": user["user_id"],
        "status": "stored",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/recall", response_model=List[MemoryResult])
async def recall_memory(
    query: MemoryQuery,
    user: Dict[str, Any] = Depends(get_current_user)
) -> List[MemoryResult]:
    """
    Recall memories using semantic search
    Implements the Recall step from SuperMemory.ai
    """
    from uuid import UUID
    from app.core.dependencies import get_memory_service
    
    logger.info(f"Recalling memory for user {user['user_id']}: {query.query}")
    
    memory_service = get_memory_service()
    
    results = await memory_service.recall(
        query=query.query,
        user_id=UUID(user["user_id"]),
        limit=query.limit,
        threshold=query.threshold
    )
    
    return [
        MemoryResult(
            memory_id=str(r["chunk_id"]),
            content=r["content"],
            score=float(r.get("score", 0.0)),
            context=r.get("context"),
            metadata=r.get("metadata"),
            created_at=r["created_at"]
        )
        for r in results
    ]


@router.get("/", response_model=List[MemoryResult])
async def list_memories(
    user: Dict[str, Any] = Depends(get_current_user),
    skip: int = 0,
    limit: int = 10
) -> List[MemoryResult]:
    """
    List user's memories
    """
    from uuid import UUID
    from app.core.dependencies import get_memory_service
    
    logger.info(f"Listing memories for user {user['user_id']}")
    
    memory_service = get_memory_service()
    
    memories = await memory_service.list_memories(
        user_id=UUID(user["user_id"]),
        skip=skip,
        limit=limit
    )
    
    return [
        MemoryResult(
            memory_id=str(m["chunk_id"]),
            content=m["content"],
            score=1.0,
            context=m.get("context"),
            metadata=m.get("metadata"),
            created_at=m["created_at"]
        )
        for m in memories
    ]


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete a memory (GDPR compliance)
    """
    from uuid import UUID
    from app.core.dependencies import get_memory_service
    
    logger.info(f"Deleting memory {memory_id} for user {user['user_id']}")
    
    memory_service = get_memory_service()
    
    await memory_service.delete_memory(
        chunk_id=UUID(memory_id),
        user_id=UUID(user["user_id"])
    )
    
    return


@router.post("/evolve", status_code=status.HTTP_200_OK)
async def evolve_memories(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Evolve memories (update, extend, derive, expire)
    Implements the Evolve step from SuperMemory.ai
    """
    from uuid import UUID
    from app.core.dependencies import get_memory_service
    
    logger.info(f"Evolving memories for user {user['user_id']}")
    
    memory_service = get_memory_service()
    
    stats = await memory_service.evolve_memories(
        user_id=UUID(user["user_id"])
    )
    
    return {
        "status": "evolved",
        "stats": stats,
        "timestamp": datetime.utcnow().isoformat()
    }
