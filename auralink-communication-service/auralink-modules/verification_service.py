"""
AuraLink Verification Service
Handles multi-method identity verification for AuraIDs
Supports: email, phone, document, social, biometric
Phase 2 Implementation
"""

from typing import Any, Dict, Optional, List
import logging
import secrets
import string
from datetime import datetime, timedelta
import asyncpg
import httpx
from enum import Enum

logger = logging.getLogger(__name__)


class VerificationMethod(str, Enum):
    """Supported verification methods"""
    EMAIL = "email"
    PHONE = "phone"
    DOCUMENT = "document"
    SOCIAL = "social"
    BIOMETRIC = "biometric"


class VerificationStatus(str, Enum):
    """Verification status"""
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"


class VerificationError(Exception):
    """Base exception for verification operations"""
    pass


class VerificationCodeInvalidError(VerificationError):
    """Raised when verification code is invalid"""
    pass


class VerificationExpiredError(VerificationError):
    """Raised when verification has expired"""
    pass


class VerificationService:
    """
    Multi-method identity verification service
    
    Verification Methods:
    - Email: 6-digit code via Twilio SendGrid
    - Phone: 6-digit code via Twilio SMS
    - Document: ID scan via Stripe Identity
    - Social: OAuth via Twitter/LinkedIn
    - Biometric: Device-based verification
    
    Trust Score Bonuses:
    - Email: +10
    - Phone: +15
    - Document: +25
    - Social: +5
    - Biometric: +20
    """
    
    # Trust score bonuses for each verification method
    TRUST_BONUSES = {
        VerificationMethod.EMAIL: 10.0,
        VerificationMethod.PHONE: 15.0,
        VerificationMethod.DOCUMENT: 25.0,
        VerificationMethod.SOCIAL: 5.0,
        VerificationMethod.BIOMETRIC: 20.0
    }
    
    def __init__(
        self, 
        config: Dict[str, Any], 
        db_pool: asyncpg.Pool,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        """
        Initialize verification service
        
        Args:
            config: Configuration with API keys
            db_pool: PostgreSQL connection pool
            http_client: HTTP client for API calls
        """
        self.config = config
        self.db_pool = db_pool
        self.http_client = http_client or httpx.AsyncClient()
        
        # External service configuration
        self.sendgrid_api_key = config.get("sendgrid_api_key")
        self.twilio_account_sid = config.get("twilio_account_sid")
        self.twilio_auth_token = config.get("twilio_auth_token")
        self.twilio_phone_number = config.get("twilio_phone_number")
        self.stripe_secret_key = config.get("stripe_secret_key")
        
        logger.info("Verification Service initialized")
    
    def generate_verification_code(self, length: int = 6) -> str:
        """
        Generate random verification code
        
        Args:
            length: Code length (default 6 digits)
            
        Returns:
            Numeric verification code
        """
        return ''.join(secrets.choice(string.digits) for _ in range(length))
    
    async def initiate_verification(
        self,
        aura_id: str,
        method: VerificationMethod,
        contact_info: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Initiate verification process
        
        Args:
            aura_id: AuraID to verify
            method: Verification method
            contact_info: Email/phone for code delivery
            metadata: Additional metadata
            
        Returns:
            Dict with verification_id and next_step instructions
            
        Raises:
            VerificationError: If verification cannot be initiated
        """
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # Get registry_id for aura_id
                    registry_row = await conn.fetchrow(
                        "SELECT registry_id FROM aura_id_registry WHERE aura_id = $1",
                        aura_id
                    )
                    
                    if not registry_row:
                        raise VerificationError(f"AuraID {aura_id} not found")
                    
                    registry_id = registry_row['registry_id']
                    
                    # Generate verification code
                    verification_code = self.generate_verification_code()
                    
                    # Insert verification record
                    verification_row = await conn.fetchrow(
                        """
                        INSERT INTO aura_id_verifications (
                            aura_id, registry_id, verification_method,
                            verification_code, status, attempts, max_attempts,
                            metadata, expires_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        RETURNING verification_id, expires_at
                        """,
                        aura_id, registry_id, method.value,
                        verification_code, VerificationStatus.PENDING.value,
                        0, 3,
                        metadata or {},
                        datetime.utcnow() + timedelta(days=7)
                    )
                    
                    verification_id = verification_row['verification_id']
                    expires_at = verification_row['expires_at']
                    
                    # Send verification based on method
                    next_step = await self._send_verification(
                        method, contact_info, verification_code, aura_id
                    )
                    
                    logger.info(f"Initiated {method.value} verification for {aura_id}")
                    
                    return {
                        "verification_id": str(verification_id),
                        "method": method.value,
                        "status": VerificationStatus.PENDING.value,
                        "expires_at": expires_at.isoformat(),
                        "next_step": next_step
                    }
                    
                except Exception as e:
                    logger.error(f"Error initiating verification: {e}")
                    raise VerificationError(f"Failed to initiate verification: {str(e)}")
    
    async def _send_verification(
        self,
        method: VerificationMethod,
        contact_info: str,
        code: str,
        aura_id: str
    ) -> Dict[str, Any]:
        """
        Send verification via appropriate channel
        
        Args:
            method: Verification method
            contact_info: Contact information
            code: Verification code
            aura_id: AuraID being verified
            
        Returns:
            Next step instructions for user
        """
        if method == VerificationMethod.EMAIL:
            await self._send_email_verification(contact_info, code, aura_id)
            return {
                "action": "check_email",
                "message": f"Verification code sent to {contact_info}",
                "instructions": "Enter the 6-digit code from your email"
            }
        
        elif method == VerificationMethod.PHONE:
            await self._send_sms_verification(contact_info, code, aura_id)
            return {
                "action": "check_sms",
                "message": f"Verification code sent to {contact_info}",
                "instructions": "Enter the 6-digit code from SMS"
            }
        
        elif method == VerificationMethod.DOCUMENT:
            session_url = await self._create_identity_verification_session(aura_id)
            return {
                "action": "complete_identity_verification",
                "verification_url": session_url,
                "instructions": "Complete identity verification at the provided URL"
            }
        
        elif method == VerificationMethod.SOCIAL:
            oauth_url = await self._create_oauth_url(contact_info, aura_id)
            return {
                "action": "complete_oauth",
                "oauth_url": oauth_url,
                "instructions": f"Authorize AuraLink via {contact_info}"
            }
        
        elif method == VerificationMethod.BIOMETRIC:
            return {
                "action": "capture_biometric",
                "challenge": code,
                "instructions": "Use your device biometric authentication"
            }
        
        else:
            raise VerificationError(f"Unsupported verification method: {method}")
    
    async def _send_email_verification(
        self,
        email: str,
        code: str,
        aura_id: str
    ) -> None:
        """Send verification email via Twilio SendGrid"""
        if not self.sendgrid_api_key:
            logger.warning("SendGrid API key not configured, skipping email")
            return
        
        try:
            response = await self.http_client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {self.sendgrid_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "personalizations": [{
                        "to": [{"email": email}],
                        "subject": "Verify your AuraID"
                    }],
                    "from": {
                        "email": "verify@auralink.network",
                        "name": "AuraLink"
                    },
                    "content": [{
                        "type": "text/plain",
                        "value": f"Your AuraID verification code is: {code}\n\n"
                                f"This code will expire in 7 days.\n\n"
                                f"AuraID: {aura_id}"
                    }]
                },
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"Sent email verification to {email}")
        except Exception as e:
            logger.error(f"Failed to send email verification: {e}")
            raise VerificationError("Failed to send verification email")
    
    async def _send_sms_verification(
        self,
        phone: str,
        code: str,
        aura_id: str
    ) -> None:
        """Send verification SMS via Twilio"""
        if not self.twilio_account_sid or not self.twilio_auth_token:
            logger.warning("Twilio credentials not configured, skipping SMS")
            return
        
        try:
            auth = (self.twilio_account_sid, self.twilio_auth_token)
            response = await self.http_client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_account_sid}/Messages.json",
                auth=auth,
                data={
                    "From": self.twilio_phone_number,
                    "To": phone,
                    "Body": f"Your AuraID verification code is: {code}\n\nAuraID: {aura_id}"
                },
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"Sent SMS verification to {phone}")
        except Exception as e:
            logger.error(f"Failed to send SMS verification: {e}")
            raise VerificationError("Failed to send verification SMS")
    
    async def _create_identity_verification_session(self, aura_id: str) -> str:
        """Create Stripe Identity verification session"""
        if not self.stripe_secret_key:
            logger.warning("Stripe API key not configured")
            return "https://verify.auralink.network/document"
        
        try:
            response = await self.http_client.post(
                "https://api.stripe.com/v1/identity/verification_sessions",
                headers={
                    "Authorization": f"Bearer {self.stripe_secret_key}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "type": "document",
                    "metadata[aura_id]": aura_id,
                    "return_url": f"https://auralink.network/verify/complete?aura_id={aura_id}"
                },
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("url", "https://verify.auralink.network/document")
        except Exception as e:
            logger.error(f"Failed to create Stripe session: {e}")
            return "https://verify.auralink.network/document"
    
    async def _create_oauth_url(self, provider: str, aura_id: str) -> str:
        """Create OAuth authorization URL"""
        # Placeholder - actual OAuth implementation would use provider-specific endpoints
        base_urls = {
            "twitter": "https://twitter.com/i/oauth2/authorize",
            "linkedin": "https://www.linkedin.com/oauth/v2/authorization"
        }
        
        base_url = base_urls.get(provider.lower(), "https://auralink.network/oauth")
        return f"{base_url}?client_id=auralink&state={aura_id}"
    
    async def complete_verification(
        self,
        verification_id: str,
        code: str
    ) -> Dict[str, Any]:
        """
        Complete verification with code
        
        Args:
            verification_id: Verification ID
            code: Verification code from user
            
        Returns:
            Dict with verification status and updated trust score
            
        Raises:
            VerificationCodeInvalidError: Invalid code
            VerificationExpiredError: Verification expired
        """
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # Get verification record with lock
                    verification = await conn.fetchrow(
                        """
                        SELECT 
                            verification_id, aura_id, registry_id,
                            verification_method, verification_code,
                            status, attempts, max_attempts, expires_at
                        FROM aura_id_verifications
                        WHERE verification_id = $1
                        FOR UPDATE
                        """,
                        verification_id
                    )
                    
                    if not verification:
                        raise VerificationError("Verification not found")
                    
                    # Check if expired
                    if verification['expires_at'] < datetime.utcnow():
                        await conn.execute(
                            "UPDATE aura_id_verifications SET status = $1 WHERE verification_id = $2",
                            VerificationStatus.EXPIRED.value, verification_id
                        )
                        raise VerificationExpiredError("Verification expired")
                    
                    # Check if already verified
                    if verification['status'] == VerificationStatus.VERIFIED.value:
                        raise VerificationError("Already verified")
                    
                    # Increment attempts
                    new_attempts = verification['attempts'] + 1
                    
                    # Check code
                    if code != verification['verification_code']:
                        await conn.execute(
                            "UPDATE aura_id_verifications SET attempts = $1 WHERE verification_id = $2",
                            new_attempts, verification_id
                        )
                        
                        if new_attempts >= verification['max_attempts']:
                            await conn.execute(
                                "UPDATE aura_id_verifications SET status = $1 WHERE verification_id = $2",
                                VerificationStatus.FAILED.value, verification_id
                            )
                            raise VerificationCodeInvalidError("Max attempts exceeded")
                        
                        raise VerificationCodeInvalidError(
                            f"Invalid code. {verification['max_attempts'] - new_attempts} attempts remaining"
                        )
                    
                    # Mark as verified
                    await conn.execute(
                        """
                        UPDATE aura_id_verifications
                        SET status = $1, verified_at = NOW()
                        WHERE verification_id = $2
                        """,
                        VerificationStatus.VERIFIED.value, verification_id
                    )
                    
                    # Update trust score
                    aura_id = verification['aura_id']
                    new_trust_score = await conn.fetchval(
                        "SELECT calculate_trust_score('aura_id', $1)",
                        aura_id
                    )
                    
                    # Mark AuraID as verified if not already
                    await conn.execute(
                        "UPDATE aura_id_registry SET is_verified = true WHERE aura_id = $1",
                        aura_id
                    )
                    
                    logger.info(f"Completed {verification['verification_method']} verification for {aura_id}")
                    
                    return {
                        "verification_id": str(verification_id),
                        "aura_id": aura_id,
                        "method": verification['verification_method'],
                        "status": VerificationStatus.VERIFIED.value,
                        "trust_score": float(new_trust_score),
                        "verified_at": datetime.utcnow().isoformat()
                    }
                    
                except (VerificationCodeInvalidError, VerificationExpiredError):
                    raise
                except Exception as e:
                    logger.error(f"Error completing verification: {e}")
                    raise VerificationError(f"Failed to complete verification: {str(e)}")
    
    async def get_verification_status(
        self,
        aura_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all verifications for an AuraID
        
        Args:
            aura_id: AuraID to query
            
        Returns:
            List of verification records
        """
        async with self.db_pool.acquire() as conn:
            try:
                rows = await conn.fetch(
                    """
                    SELECT 
                        verification_id, verification_method, status,
                        initiated_at, verified_at, expires_at
                    FROM aura_id_verifications
                    WHERE aura_id = $1
                    ORDER BY initiated_at DESC
                    """,
                    aura_id
                )
                
                return [
                    {
                        "verification_id": str(row['verification_id']),
                        "method": row['verification_method'],
                        "status": row['status'],
                        "initiated_at": row['initiated_at'].isoformat(),
                        "verified_at": row['verified_at'].isoformat() if row['verified_at'] else None,
                        "expires_at": row['expires_at'].isoformat()
                    }
                    for row in rows
                ]
            except Exception as e:
                logger.error(f"Error getting verification status: {e}")
                return []


# Module initialization
logger.info("Verification Service module loaded - Phase 2 Implementation")
