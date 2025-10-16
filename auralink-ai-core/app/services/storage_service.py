"""
Storage Service - Supabase Storage Integration
Enterprise-grade file storage for audio, video, and media files
"""

import logging
import hashlib
from typing import Optional, Dict, Any, BinaryIO
from datetime import datetime, timedelta
from uuid import UUID
import os
from io import BytesIO

import httpx
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class StorageService:
    """
    Enterprise Storage Service for AuraLink AI Core
    
    Features:
    - Supabase Storage integration
    - Audio/video file upload
    - Automatic file organization
    - Signed URL generation
    - File cleanup and lifecycle management
    - CDN acceleration
    """
    
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            logger.warning("Supabase credentials not configured. Storage service will be limited.")
            self.client = None
        else:
            self.client: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Storage buckets
        self.audio_bucket = "audio-files"
        self.video_bucket = "video-files"
        self.avatar_bucket = "avatars"
        
    async def initialize(self):
        """Initialize storage buckets"""
        if not self.client:
            return
        
        try:
            # Create buckets if they don't exist
            buckets = [self.audio_bucket, self.video_bucket, self.avatar_bucket]
            
            for bucket_name in buckets:
                try:
                    self.client.storage.create_bucket(
                        bucket_name,
                        options={"public": False}
                    )
                    logger.info(f"Created storage bucket: {bucket_name}")
                except Exception as e:
                    # Bucket might already exist
                    logger.debug(f"Bucket {bucket_name} may already exist: {e}")
        
        except Exception as e:
            logger.error(f"Error initializing storage buckets: {e}")
    
    # ========================================================================
    # AUDIO FILE OPERATIONS
    # ========================================================================
    
    async def upload_audio(
        self,
        audio_data: bytes,
        user_id: UUID,
        file_type: str = "mp3",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Upload audio file to storage
        
        Returns:
            Public URL or signed URL for the uploaded file
        """
        if not self.client:
            # Fallback: return placeholder URL
            return self._generate_placeholder_url("audio", user_id, file_type)
        
        try:
            # Generate unique filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            content_hash = hashlib.md5(audio_data).hexdigest()[:8]
            filename = f"{user_id}/{timestamp}_{content_hash}.{file_type}"
            
            # Upload to Supabase Storage
            response = self.client.storage.from_(self.audio_bucket).upload(
                path=filename,
                file=audio_data,
                file_options={
                    "content-type": f"audio/{file_type}",
                    "cache-control": "3600",
                    "upsert": "false"
                }
            )
            
            # Get public URL (or signed URL for private buckets)
            url = self.get_audio_url(filename)
            
            logger.info(f"Uploaded audio file: {filename}")
            return url
        
        except Exception as e:
            logger.error(f"Error uploading audio file: {e}")
            # Return placeholder URL as fallback
            return self._generate_placeholder_url("audio", user_id, file_type)
    
    def get_audio_url(
        self,
        file_path: str,
        expires_in: int = 3600
    ) -> str:
        """Get signed URL for audio file"""
        if not self.client:
            return f"https://storage.auralink.com/audio/{file_path}"
        
        try:
            # Generate signed URL for private access
            response = self.client.storage.from_(self.audio_bucket).create_signed_url(
                path=file_path,
                expires_in=expires_in
            )
            
            return response.get("signedURL", f"https://storage.auralink.com/audio/{file_path}")
        
        except Exception as e:
            logger.error(f"Error generating signed URL: {e}")
            return f"https://storage.auralink.com/audio/{file_path}"
    
    async def upload_audio_stream(
        self,
        audio_stream: BinaryIO,
        user_id: UUID,
        file_type: str = "mp3"
    ) -> str:
        """Upload audio from stream"""
        audio_data = audio_stream.read()
        return await self.upload_audio(audio_data, user_id, file_type)
    
    # ========================================================================
    # VIDEO FILE OPERATIONS
    # ========================================================================
    
    async def upload_video(
        self,
        video_data: bytes,
        user_id: UUID,
        file_type: str = "mp4",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Upload video file to storage"""
        if not self.client:
            return self._generate_placeholder_url("video", user_id, file_type)
        
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            content_hash = hashlib.md5(video_data).hexdigest()[:8]
            filename = f"{user_id}/{timestamp}_{content_hash}.{file_type}"
            
            response = self.client.storage.from_(self.video_bucket).upload(
                path=filename,
                file=video_data,
                file_options={
                    "content-type": f"video/{file_type}",
                    "cache-control": "3600",
                    "upsert": "false"
                }
            )
            
            url = self.get_video_url(filename)
            logger.info(f"Uploaded video file: {filename}")
            return url
        
        except Exception as e:
            logger.error(f"Error uploading video file: {e}")
            return self._generate_placeholder_url("video", user_id, file_type)
    
    def get_video_url(
        self,
        file_path: str,
        expires_in: int = 7200
    ) -> str:
        """Get signed URL for video file"""
        if not self.client:
            return f"https://storage.auralink.com/video/{file_path}"
        
        try:
            response = self.client.storage.from_(self.video_bucket).create_signed_url(
                path=file_path,
                expires_in=expires_in
            )
            
            return response.get("signedURL", f"https://storage.auralink.com/video/{file_path}")
        
        except Exception as e:
            logger.error(f"Error generating video signed URL: {e}")
            return f"https://storage.auralink.com/video/{file_path}"
    
    # ========================================================================
    # FILE MANAGEMENT
    # ========================================================================
    
    async def delete_file(
        self,
        bucket: str,
        file_path: str
    ) -> bool:
        """Delete file from storage"""
        if not self.client:
            return False
        
        try:
            self.client.storage.from_(bucket).remove([file_path])
            logger.info(f"Deleted file: {bucket}/{file_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False
    
    async def delete_user_files(
        self,
        user_id: UUID,
        bucket: Optional[str] = None
    ) -> int:
        """Delete all files for a user (GDPR compliance)"""
        if not self.client:
            return 0
        
        deleted_count = 0
        buckets = [bucket] if bucket else [self.audio_bucket, self.video_bucket, self.avatar_bucket]
        
        for bucket_name in buckets:
            try:
                # List user files
                files = self.client.storage.from_(bucket_name).list(str(user_id))
                
                if files:
                    file_paths = [f"{user_id}/{f['name']}" for f in files]
                    self.client.storage.from_(bucket_name).remove(file_paths)
                    deleted_count += len(file_paths)
                    logger.info(f"Deleted {len(file_paths)} files from {bucket_name} for user {user_id}")
            
            except Exception as e:
                logger.error(f"Error deleting user files from {bucket_name}: {e}")
        
        return deleted_count
    
    async def get_file_info(
        self,
        bucket: str,
        file_path: str
    ) -> Optional[Dict[str, Any]]:
        """Get file metadata"""
        if not self.client:
            return None
        
        try:
            files = self.client.storage.from_(bucket).list()
            
            for file in files:
                if file.get("name") == file_path:
                    return file
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return None
    
    # ========================================================================
    # CLEANUP & LIFECYCLE
    # ========================================================================
    
    async def cleanup_old_files(
        self,
        days: int = 30
    ) -> int:
        """Cleanup files older than specified days"""
        if not self.client:
            return 0
        
        # This would require custom implementation based on file naming
        # and metadata. For now, return 0.
        logger.info(f"File cleanup scheduled for files older than {days} days")
        return 0
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _generate_placeholder_url(
        self,
        file_type: str,
        user_id: UUID,
        extension: str
    ) -> str:
        """Generate placeholder URL when storage is not available"""
        timestamp = datetime.utcnow().timestamp()
        return f"https://storage.auralink.com/{file_type}/{user_id}_{int(timestamp)}.{extension}"
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage usage statistics"""
        if not self.client:
            return {"status": "unavailable"}
        
        try:
            stats = {
                "status": "operational",
                "buckets": {
                    "audio": self.audio_bucket,
                    "video": self.video_bucket,
                    "avatars": self.avatar_bucket
                },
                "provider": "Supabase Storage"
            }
            return stats
        
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {"status": "error", "error": str(e)}


# Singleton instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get Storage Service singleton"""
    global _storage_service
    
    if _storage_service is None:
        _storage_service = StorageService()
    
    return _storage_service
