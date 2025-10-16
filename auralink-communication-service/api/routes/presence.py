"""
Presence Management Routes
Handles online/offline status and presence updates
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class PresenceUpdate(BaseModel):
    aura_id: str
    status: str  # online, offline, away, busy, dnd
    status_message: Optional[str] = None
    device_id: Optional[str] = None


class PresenceResponse(BaseModel):
    aura_id: str
    status: str
    last_seen: datetime
    is_online: bool


@router.post("/update")
async def update_presence(presence: PresenceUpdate):
    """
    Update user presence status
    
    Updates online/offline status and status message
    """
    try:
        # Validate status
        valid_statuses = ["online", "offline", "away", "busy", "dnd"]
        if presence.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        # Update in database and Matrix (placeholder)
        logger.info(f"Presence update: {presence.aura_id} -> {presence.status}")
        
        return {
            "aura_id": presence.aura_id,
            "status": presence.status,
            "updated": True,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Presence update error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{aura_id}", response_model=PresenceResponse)
async def get_presence(aura_id: str):
    """
    Get current presence status for an AuraID
    
    Returns online status and last seen timestamp
    """
    try:
        # Query database and Matrix for presence (placeholder)
        return PresenceResponse(
            aura_id=aura_id,
            status="online",
            last_seen=datetime.utcnow(),
            is_online=True
        )
        
    except Exception as e:
        logger.error(f"Error fetching presence: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bulk")
async def get_bulk_presence(aura_ids: str):
    """
    Get presence for multiple AuraIDs
    
    Query parameter: aura_ids (comma-separated)
    """
    try:
        aura_id_list = aura_ids.split(",")
        
        # Batch query (placeholder)
        results = []
        for aid in aura_id_list:
            results.append({
                "aura_id": aid.strip(),
                "status": "online",
                "is_online": True
            })
        
        return {
            "presence": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Bulk presence error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
