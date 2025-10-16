"""
Matrix Integration Routes
Handles Matrix user registration and AuraID mapping
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import httpx
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Matrix Admin API configuration
MATRIX_SERVER_URL = os.getenv("MATRIX_SERVER_URL", "http://localhost:8008")
MATRIX_ADMIN_TOKEN = os.getenv("MATRIX_ADMIN_TOKEN", "")


class MatrixRegistrationRequest(BaseModel):
    aura_id: str
    user_id: str
    username: str
    password: Optional[str] = None
    display_name: Optional[str] = None


class MatrixRegistrationResponse(BaseModel):
    matrix_user_id: str
    aura_id: str
    homeserver_url: str
    access_token: str


@router.post("/register", response_model=MatrixRegistrationResponse)
async def register_matrix_user(request: MatrixRegistrationRequest):
    """
    Register a Matrix user for an AuraID
    
    Creates Matrix user via Synapse admin API and stores mapping
    """
    try:
        # Generate Matrix username from AuraID
        # @alice.aura -> alice_aura
        matrix_username = request.aura_id.replace("@", "").replace(".", "_")
        
        # Call Matrix admin API to create user
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MATRIX_SERVER_URL}/_synapse/admin/v2/users/@{matrix_username}:auralink.network",
                json={
                    "password": request.password or generate_secure_password(),
                    "displayname": request.display_name or request.username,
                    "admin": False,
                },
                headers={"Authorization": f"Bearer {MATRIX_ADMIN_TOKEN}"}
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"Matrix registration failed: {response.text}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create Matrix user"
                )
            
            matrix_data = response.json()
            matrix_user_id = f"@{matrix_username}:auralink.network"
        
        # Store mapping in database (placeholder - actual DB integration needed)
        logger.info(f"Matrix user created: {matrix_user_id} for AuraID: {request.aura_id}")
        
        return MatrixRegistrationResponse(
            matrix_user_id=matrix_user_id,
            aura_id=request.aura_id,
            homeserver_url=MATRIX_SERVER_URL,
            access_token=matrix_data.get("access_token", "")
        )
        
    except Exception as e:
        logger.error(f"Matrix registration error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resolve/{aura_id}")
async def resolve_aura_id_to_matrix(aura_id: str):
    """
    Resolve AuraID to Matrix user ID
    
    Returns Matrix user information for a given AuraID
    """
    try:
        # Query database for Matrix mapping (placeholder)
        matrix_username = aura_id.replace("@", "").replace(".", "_")
        matrix_user_id = f"@{matrix_username}:auralink.network"
        
        # Check if user exists in Matrix
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{MATRIX_SERVER_URL}/_matrix/client/v3/profile/{matrix_user_id}",
            )
            
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Matrix user not found")
            
            profile = response.json()
        
        return {
            "aura_id": aura_id,
            "matrix_user_id": matrix_user_id,
            "display_name": profile.get("displayname"),
            "avatar_url": profile.get("avatar_url"),
            "homeserver": "auralink.network"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resolution error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def generate_secure_password() -> str:
    """Generate a secure random password for Matrix user"""
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(32))
