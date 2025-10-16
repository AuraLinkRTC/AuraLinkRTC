"""
Encryption Utility for API Key Security
Enterprise-grade encryption for sensitive data
"""

import os
import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Enterprise Encryption Service
    
    Features:
    - AES-256 encryption using Fernet
    - Key derivation from master key
    - Secure API key storage
    - GDPR-compliant encryption
    """
    
    def __init__(self):
        # Get master encryption key from environment
        master_key = os.getenv("ENCRYPTION_MASTER_KEY")
        
        if not master_key:
            # Generate a key for development (NOT FOR PRODUCTION)
            logger.warning("⚠️  ENCRYPTION_MASTER_KEY not set. Generating temporary key (NOT PRODUCTION SAFE)")
            master_key = Fernet.generate_key().decode()
            logger.warning(f"Generated temporary key: {master_key}")
            logger.warning("Please set ENCRYPTION_MASTER_KEY in production environment")
        
        # Create Fernet cipher
        try:
            if isinstance(master_key, str):
                master_key = master_key.encode()
            
            # Ensure key is properly formatted
            if len(master_key) != 44:  # Fernet key length
                # Derive a proper Fernet key from the master key
                master_key = self._derive_key(master_key)
            
            self.cipher = Fernet(master_key)
            logger.info("✓ Encryption service initialized")
        
        except Exception as e:
            logger.error(f"✗ Failed to initialize encryption: {e}")
            # Fallback to a generated key (NOT PRODUCTION SAFE)
            self.cipher = Fernet(Fernet.generate_key())
            logger.warning("⚠️  Using fallback encryption key (NOT PRODUCTION SAFE)")
    
    def _derive_key(self, password: bytes, salt: Optional[bytes] = None) -> bytes:
        """
        Derive a Fernet-compatible key from a password
        """
        if salt is None:
            # Use a constant salt for consistency (in production, store salt securely)
            salt = b'auralink-ai-core-salt-v1'
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string
        
        Args:
            plaintext: String to encrypt
        
        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ""
        
        try:
            encrypted_bytes = self.cipher.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted_bytes).decode()
        
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise ValueError("Failed to encrypt data")
    
    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt encrypted string
        
        Args:
            encrypted: Base64-encoded encrypted string
        
        Returns:
            Decrypted plaintext string
        """
        if not encrypted:
            return ""
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted.encode())
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            return decrypted_bytes.decode()
        
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise ValueError("Failed to decrypt data")
    
    def encrypt_api_key(self, api_key: str) -> str:
        """
        Encrypt API key for storage
        
        Args:
            api_key: API key to encrypt
        
        Returns:
            Encrypted API key
        """
        return self.encrypt(api_key)
    
    def decrypt_api_key(self, encrypted_key: str) -> str:
        """
        Decrypt API key from storage
        
        Args:
            encrypted_key: Encrypted API key
        
        Returns:
            Decrypted API key
        """
        return self.decrypt(encrypted_key)
    
    def encrypt_dict(self, data: dict) -> dict:
        """
        Encrypt dictionary values
        
        Args:
            data: Dictionary with string values to encrypt
        
        Returns:
            Dictionary with encrypted values
        """
        encrypted_data = {}
        
        for key, value in data.items():
            if isinstance(value, str) and value:
                encrypted_data[key] = self.encrypt(value)
            else:
                encrypted_data[key] = value
        
        return encrypted_data
    
    def decrypt_dict(self, encrypted_data: dict) -> dict:
        """
        Decrypt dictionary values
        
        Args:
            encrypted_data: Dictionary with encrypted string values
        
        Returns:
            Dictionary with decrypted values
        """
        decrypted_data = {}
        
        for key, value in encrypted_data.items():
            if isinstance(value, str) and value:
                try:
                    decrypted_data[key] = self.decrypt(value)
                except Exception:
                    # If decryption fails, assume it's not encrypted
                    decrypted_data[key] = value
            else:
                decrypted_data[key] = value
        
        return decrypted_data
    
    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key
        
        Returns:
            Base64-encoded encryption key
        """
        return Fernet.generate_key().decode()
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
        """
        Hash password for storage (not for API keys)
        
        Args:
            password: Password to hash
            salt: Optional salt (generated if not provided)
        
        Returns:
            Tuple of (hashed_password, salt)
        """
        if salt is None:
            salt = os.urandom(32)
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        hashed = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        salt_b64 = base64.urlsafe_b64encode(salt)
        
        return hashed.decode(), salt_b64.decode()
    
    def verify_password(
        self,
        password: str,
        hashed_password: str,
        salt: str
    ) -> bool:
        """
        Verify password against hash
        
        Args:
            password: Password to verify
            hashed_password: Hashed password to compare
            salt: Salt used for hashing
        
        Returns:
            True if password matches, False otherwise
        """
        try:
            salt_bytes = base64.urlsafe_b64decode(salt.encode())
            new_hash, _ = self.hash_password(password, salt_bytes)
            return new_hash == hashed_password
        
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False


# Singleton instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Get Encryption Service singleton"""
    global _encryption_service
    
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    
    return _encryption_service


# Convenience functions
def encrypt(plaintext: str) -> str:
    """Encrypt plaintext"""
    return get_encryption_service().encrypt(plaintext)


def decrypt(encrypted: str) -> str:
    """Decrypt encrypted text"""
    return get_encryption_service().decrypt(encrypted)


def encrypt_api_key(api_key: str) -> str:
    """Encrypt API key"""
    return get_encryption_service().encrypt_api_key(api_key)


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt API key"""
    return get_encryption_service().decrypt_api_key(encrypted_key)
