"""
AuraLink AuraID Module for Matrix Synapse
Handles AuraID registration, verification, and management
Phase 2 Implementation - Production Ready
"""

from typing import Any, Dict, Optional, List
import logging
import re
import asyncpg
import httpx
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


class AuraIDError(Exception):
    """Base exception for AuraID operations"""
    pass


class AuraIDValidationError(AuraIDError):
    """Raised when AuraID format is invalid"""
    pass


class AuraIDAlreadyExistsError(AuraIDError):
    """Raised when AuraID already exists"""
    pass


class AuraIDModule:
    """
    Matrix module for AuraID integration
    
    Provides:
    - AuraID creation during Matrix user registration
    - AuraID resolution (lookup Matrix user by AuraID)
    - Privacy control enforcement
    - Database persistence with transaction safety
    """
    
    # AuraID format: @username.aura (alphanumeric, 3-20 chars)
    AURAID_PATTERN = re.compile(r'^@[a-zA-Z0-9_]{3,20}\.aura$')
    
    def __init__(self, config: Dict[str, Any], api, db_pool: asyncpg.Pool):
        """
        Initialize AuraID module
        
        Args:
            config: Module configuration from homeserver.yaml
            api: Synapse ModuleAPI instance
            db_pool: PostgreSQL connection pool
        """
        self.config = config
        self.api = api
        self.db_pool = db_pool
        self.dashboard_url = config.get("dashboard_api", "http://dashboard-service:8080")
        self.homeserver = config.get("server_name", "auralink.network")
        
        logger.info(f"AuraID Module initialized for homeserver: {self.homeserver}")
    
    def validate_username(self, username: str) -> bool:
        """
        Validate username format for AuraID
        
        Rules:
        - Alphanumeric and underscores only
        - 3-20 characters
        - Cannot start with underscore
        
        Args:
            username: Username to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not username:
            return False
        
        if len(username) < 3 or len(username) > 20:
            return False
        
        if username.startswith('_'):
            return False
        
        return re.match(r'^[a-zA-Z0-9_]+$', username) is not None
    
    def username_to_auraid(self, username: str) -> str:
        """
        Convert username to AuraID format
        
        Args:
            username: Username (e.g., 'alice')
            
        Returns:
            AuraID (e.g., '@alice.aura')
        """
        return f"@{username}.aura"
    
    def auraid_to_matrix_user(self, aura_id: str) -> str:
        """
        Convert AuraID to Matrix user ID
        
        Args:
            aura_id: AuraID (e.g., '@alice.aura')
            
        Returns:
            Matrix user ID (e.g., '@alice_aura:auralink.network')
        """
        # Extract username from AuraID
        username = aura_id[1:-5]  # Remove '@' and '.aura'
        # Replace dots with underscores for Matrix compatibility
        matrix_username = username.replace('.', '_')
        return f"@{matrix_username}_aura:{self.homeserver}"
    
    async def create_auraid(
        self, 
        user_id: str, 
        username: str, 
        display_name: Optional[str] = None,
        matrix_user_id: Optional[str] = None,
        matrix_access_token: Optional[str] = None,
        device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create AuraID and store in database
        
        Args:
            user_id: Supabase user UUID
            username: Username for AuraID
            display_name: User display name
            matrix_user_id: Matrix user ID (if already created)
            matrix_access_token: Matrix access token
            device_id: Matrix device ID
            
        Returns:
            Dict with AuraID, Matrix credentials, and trust score
            
        Raises:
            AuraIDValidationError: Invalid username format
            AuraIDAlreadyExistsError: Username already taken
            AuraIDError: Database or Matrix error
        """
        # Validate username
        if not self.validate_username(username):
            raise AuraIDValidationError(
                f"Invalid username format: {username}. "
                "Must be 3-20 alphanumeric characters, cannot start with underscore."
            )
        
        aura_id = self.username_to_auraid(username)
        
        # Validate AuraID format
        if not self.AURAID_PATTERN.match(aura_id):
            raise AuraIDValidationError(f"Invalid AuraID format: {aura_id}")
        
        # Use provided Matrix user ID or generate one
        if matrix_user_id is None:
            matrix_user_id = self.auraid_to_matrix_user(aura_id)
        
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # Check if AuraID already exists
                    existing = await conn.fetchrow(
                        "SELECT aura_id FROM aura_id_registry WHERE aura_id = $1",
                        aura_id
                    )
                    if existing:
                        raise AuraIDAlreadyExistsError(f"AuraID {aura_id} already exists")
                    
                    # Check if username already exists
                    existing_username = await conn.fetchrow(
                        "SELECT username FROM aura_id_registry WHERE username = $1",
                        username
                    )
                    if existing_username:
                        raise AuraIDAlreadyExistsError(f"Username {username} already taken")
                    
                    # Insert into aura_id_registry
                    registry_row = await conn.fetchrow(
                        """
                        INSERT INTO aura_id_registry (
                            aura_id, user_id, username, display_name, 
                            privacy_level, trust_score, is_active, is_verified
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        RETURNING registry_id, trust_score, created_at
                        """,
                        aura_id, user_id, username, display_name,
                        'public', 50.0, True, False
                    )
                    
                    registry_id = registry_row['registry_id']
                    trust_score = registry_row['trust_score']
                    
                    # Insert into matrix_user_mappings
                    await conn.execute(
                        """
                        INSERT INTO matrix_user_mappings (
                            aura_id, registry_id, matrix_user_id, homeserver,
                            matrix_access_token, device_id
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        aura_id, registry_id, matrix_user_id, self.homeserver,
                        matrix_access_token, device_id
                    )
                    
                    # Initialize trust score entry
                    await conn.execute(
                        "SELECT calculate_trust_score('aura_id', $1)",
                        aura_id
                    )
                    
                    logger.info(f"Created AuraID: {aura_id} for user: {user_id}")
                    
                    return {
                        "aura_id": aura_id,
                        "username": username,
                        "matrix_user_id": matrix_user_id,
                        "homeserver": self.homeserver,
                        "trust_score": float(trust_score),
                        "privacy_level": "public",
                        "is_verified": False,
                        "created_at": registry_row['created_at'].isoformat()
                    }
                    
                except asyncpg.UniqueViolationError as e:
                    logger.error(f"AuraID uniqueness violation: {e}")
                    raise AuraIDAlreadyExistsError(f"AuraID or username already exists")
                except Exception as e:
                    logger.error(f"Error creating AuraID: {e}")
                    raise AuraIDError(f"Failed to create AuraID: {str(e)}")
    
    async def resolve_auraid(self, aura_id: str, requester_aura_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Resolve AuraID to Matrix user with privacy checks
        
        Args:
            aura_id: AuraID to resolve
            requester_aura_id: AuraID of requester (for privacy checks)
            
        Returns:
            Dict with Matrix user info if found and accessible, None otherwise
        """
        async with self.db_pool.acquire() as conn:
            try:
                # Check if AuraID can be discovered
                can_discover = await conn.fetchval(
                    "SELECT can_discover_auraid($1, $2)",
                    aura_id, requester_aura_id or aura_id
                )
                
                if not can_discover:
                    logger.debug(f"AuraID {aura_id} not discoverable by {requester_aura_id}")
                    return None
                
                # Query with RLS policies applied
                result = await conn.fetchrow(
                    """
                    SELECT 
                        r.aura_id, r.username, r.display_name, r.privacy_level,
                        r.is_active, r.is_verified, r.trust_score,
                        m.matrix_user_id, m.homeserver
                    FROM aura_id_registry r
                    JOIN matrix_user_mappings m ON r.registry_id = m.registry_id
                    WHERE r.aura_id = $1 AND r.is_active = true
                    """,
                    aura_id
                )
                
                if not result:
                    return None
                
                return {
                    "aura_id": result['aura_id'],
                    "username": result['username'],
                    "display_name": result['display_name'],
                    "matrix_user_id": result['matrix_user_id'],
                    "homeserver": result['homeserver'],
                    "privacy_level": result['privacy_level'],
                    "is_active": result['is_active'],
                    "is_verified": result['is_verified'],
                    "trust_score": float(result['trust_score'])
                }
                
            except Exception as e:
                logger.error(f"Error resolving AuraID {aura_id}: {e}")
                return None
    
    async def bulk_resolve_auraids(
        self, 
        aura_ids: List[str], 
        requester_aura_id: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Resolve multiple AuraIDs efficiently
        
        Args:
            aura_ids: List of AuraIDs to resolve
            requester_aura_id: AuraID of requester (for privacy checks)
            
        Returns:
            Dict mapping aura_id -> resolved data
        """
        if not aura_ids:
            return {}
        
        results = {}
        
        async with self.db_pool.acquire() as conn:
            try:
                # Batch query with privacy checks
                rows = await conn.fetch(
                    """
                    SELECT 
                        r.aura_id, r.username, r.display_name, r.privacy_level,
                        r.is_active, r.is_verified, r.trust_score,
                        m.matrix_user_id, m.homeserver,
                        can_discover_auraid(r.aura_id, $2) as can_discover
                    FROM aura_id_registry r
                    JOIN matrix_user_mappings m ON r.registry_id = m.registry_id
                    WHERE r.aura_id = ANY($1) AND r.is_active = true
                    """,
                    aura_ids, requester_aura_id or ''
                )
                
                for row in rows:
                    # Only include if discoverable
                    if row['can_discover']:
                        results[row['aura_id']] = {
                            "aura_id": row['aura_id'],
                            "username": row['username'],
                            "display_name": row['display_name'],
                            "matrix_user_id": row['matrix_user_id'],
                            "homeserver": row['homeserver'],
                            "privacy_level": row['privacy_level'],
                            "is_verified": row['is_verified'],
                            "trust_score": float(row['trust_score'])
                        }
                
                logger.debug(f"Resolved {len(results)}/{len(aura_ids)} AuraIDs")
                return results
                
            except Exception as e:
                logger.error(f"Error bulk resolving AuraIDs: {e}")
                return {}
    
    async def update_privacy_level(
        self, 
        aura_id: str, 
        privacy_level: str
    ) -> bool:
        """
        Update AuraID privacy settings
        
        Args:
            aura_id: AuraID to update
            privacy_level: New privacy level ('public', 'friends', 'private')
            
        Returns:
            True if updated successfully, False otherwise
        """
        if privacy_level not in ['public', 'friends', 'private']:
            logger.error(f"Invalid privacy level: {privacy_level}")
            return False
        
        async with self.db_pool.acquire() as conn:
            try:
                result = await conn.execute(
                    """
                    UPDATE aura_id_registry
                    SET privacy_level = $1, updated_at = NOW()
                    WHERE aura_id = $2 AND is_active = true
                    """,
                    privacy_level, aura_id
                )
                
                if result == "UPDATE 1":
                    logger.info(f"Updated privacy for {aura_id} to {privacy_level}")
                    return True
                else:
                    logger.warning(f"AuraID not found or inactive: {aura_id}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error updating privacy for {aura_id}: {e}")
                return False
    
    async def get_auraid_by_user_id(self, user_id: str) -> Optional[str]:
        """
        Get AuraID for a given user_id
        
        Args:
            user_id: Supabase user UUID
            
        Returns:
            AuraID if found, None otherwise
        """
        async with self.db_pool.acquire() as conn:
            try:
                result = await conn.fetchval(
                    "SELECT aura_id FROM aura_id_registry WHERE user_id = $1 AND is_active = true",
                    user_id
                )
                return result
            except Exception as e:
                logger.error(f"Error getting AuraID for user {user_id}: {e}")
                return None
    
    async def check_username_available(self, username: str) -> bool:
        """
        Check if username is available for registration
        
        Args:
            username: Username to check
            
        Returns:
            True if available, False if taken
        """
        if not self.validate_username(username):
            return False
        
        async with self.db_pool.acquire() as conn:
            try:
                exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM aura_id_registry WHERE username = $1)",
                    username
                )
                return not exists
            except Exception as e:
                logger.error(f"Error checking username availability: {e}")
                return False


# Module entry point
def parse_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and validate module configuration"""
    required_keys = ['server_name', 'database_url']
    for key in required_keys:
        if key not in config:
            logger.warning(f"Missing required config key: {key}")
    
    return config


logger.info("AuraID Module loaded - Phase 2 Implementation Complete")
