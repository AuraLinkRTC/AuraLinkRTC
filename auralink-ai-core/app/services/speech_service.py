"""
Speech Processing Service - STT/TTS with Multiple Providers
Supports Whisper, ElevenLabs, Google Cloud, Azure, AWS Polly
"""

import logging
import asyncio
import os
from typing import Dict, Any, Optional, BinaryIO
from uuid import UUID
from datetime import datetime
from io import BytesIO

import asyncpg
from openai import AsyncOpenAI
import httpx

from app.services.storage_service import StorageService
from app.services.cloud_providers import GoogleCloudProvider, AzureProvider, AWSProvider

logger = logging.getLogger(__name__)


class SpeechService:
    """
    Speech Processing Service
    
    Features:
    - Speech-to-Text (STT) with multiple providers
    - Text-to-Speech (TTS) with voice customization
    - Real-time transcription support
    - Noise cancellation (future)
    - Searchable archives
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        ai_provider_service: Any,
        storage_client: Optional[Any] = None
    ):
        self.db_pool = db_pool
        self.ai_provider = ai_provider_service
        self.storage_service = StorageService()
        
        # Initialize cloud providers
        self.google_provider = GoogleCloudProvider()
        self.azure_provider = AzureProvider()
        self.aws_provider = AWSProvider()
        
    # ========================================================================
    # SPEECH-TO-TEXT (STT)
    # ========================================================================
    
    async def transcribe_audio(
        self,
        user_id: UUID,
        audio_data: bytes,
        language: Optional[str] = None,
        provider: str = "whisper",
        call_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio to text
        """
        start_time = datetime.utcnow()
        logger.info(f"Transcribing audio for user {user_id} with {provider}")
        
        # Get provider config
        from .ai_provider_service import ProviderType, ProviderName
        config = await self.ai_provider.get_provider_config(
            user_id, ProviderType.STT
        )
        
        if not config:
            raise ValueError("No STT provider configured")
        
        provider_name = config["provider_name"]
        
        # Transcribe based on provider
        if provider_name == "whisper" or provider_name == "openai":
            result = await self._transcribe_whisper(
                user_id, audio_data, language
            )
        elif provider_name == "google_cloud":
            result = await self._transcribe_google_cloud(
                audio_data, language
            )
        elif provider_name == "azure":
            result = await self._transcribe_azure(
                audio_data, language
            )
        else:
            raise ValueError(f"Unsupported STT provider: {provider_name}")
        
        # Calculate processing time
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        result["processing_time_ms"] = processing_time_ms
        
        # Store transcription
        transcription_id = await self._store_transcription(
            user_id=user_id,
            call_id=call_id,
            text=result["text"],
            language=result["language"],
            confidence=result["confidence"],
            provider=provider_name,
            model=result.get("model"),
            processing_time_ms=processing_time_ms,
            audio_duration_seconds=result.get("duration"),
            segments=result.get("segments"),
            metadata=result.get("metadata", {})
        )
        
        result["transcription_id"] = str(transcription_id)
        
        # Track usage
        await self.ai_provider._track_usage(
            user_id=user_id,
            service_type=ProviderType.STT,
            provider=provider_name,
            model=result.get("model"),
            audio_seconds=result.get("duration"),
            latency_ms=processing_time_ms,
            call_id=call_id
        )
        
        return result
    
    async def _transcribe_whisper(
        self,
        user_id: UUID,
        audio_data: bytes,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Transcribe using OpenAI Whisper"""
        # Get provider config
        from .ai_provider_service import ProviderType, ProviderName
        config = await self.ai_provider.get_provider_config(
            user_id, ProviderType.STT
        )
        
        api_key = config.get("api_key_encrypted")
        client = AsyncOpenAI(api_key=api_key) if api_key else AsyncOpenAI()
        
        # Create file-like object
        audio_file = BytesIO(audio_data)
        audio_file.name = "audio.mp3"  # Whisper needs a filename
        
        try:
            # Transcribe
            response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language,
                response_format="verbose_json"
            )
            
            return {
                "text": response.text,
                "language": response.language or language or "en",
                "confidence": 0.95,  # Whisper doesn't provide confidence
                "duration": response.duration,
                "model": "whisper-1",
                "segments": response.segments if hasattr(response, 'segments') else None
            }
        
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            raise
    
    async def _transcribe_google_cloud(
        self,
        audio_data: bytes,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Transcribe using Google Cloud Speech-to-Text"""
        try:
            result = await self.google_provider.transcribe_audio(
                audio_data, language or "en-US"
            )
            return result
        except Exception as e:
            logger.error(f"Google Cloud STT error: {e}")
            raise
    
    async def _transcribe_azure(
        self,
        audio_data: bytes,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Transcribe using Azure Cognitive Services"""
        try:
            result = await self.azure_provider.transcribe_audio(
                audio_data, language or "en-US"
            )
            return result
        except Exception as e:
            logger.error(f"Azure STT error: {e}")
            raise
    
    async def _store_transcription(
        self,
        user_id: UUID,
        text: str,
        language: str,
        confidence: float,
        provider: str,
        call_id: Optional[str] = None,
        audio_url: Optional[str] = None,
        audio_duration_seconds: Optional[float] = None,
        model: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
        segments: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """Store transcription in database"""
        word_count = len(text.split())
        
        async with self.db_pool.acquire() as conn:
            transcription_id = await conn.fetchval(
                """
                INSERT INTO transcriptions (
                    user_id, call_id, audio_url, audio_duration_seconds,
                    text, language, confidence, provider, model,
                    processing_time_ms, word_count, segments, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                RETURNING transcription_id
                """,
                user_id, call_id, audio_url, audio_duration_seconds,
                text, language, confidence, provider, model,
                processing_time_ms, word_count, segments, metadata or {}
            )
        
        return transcription_id
    
    # ========================================================================
    # TEXT-TO-SPEECH (TTS)
    # ========================================================================
    
    async def synthesize_speech(
        self,
        user_id: UUID,
        text: str,
        voice_id: str = "default",
        speed: float = 1.0,
        provider: str = "elevenlabs",
        agent_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Convert text to speech
        """
        start_time = datetime.utcnow()
        logger.info(f"Synthesizing speech for user {user_id} with {provider}")
        
        # Get provider config
        from .ai_provider_service import ProviderType
        config = await self.ai_provider.get_provider_config(
            user_id, ProviderType.TTS
        )
        
        if not config:
            raise ValueError("No TTS provider configured")
        
        provider_name = config["provider_name"]
        
        # Synthesize based on provider
        if provider_name == "elevenlabs":
            result = await self._synthesize_elevenlabs(
                user_id, text, voice_id, config
            )
        elif provider_name == "openai":
            result = await self._synthesize_openai_tts(
                user_id, text, voice_id
            )
        elif provider_name == "google_cloud":
            result = await self._synthesize_google_cloud(
                text, voice_id
            )
        elif provider_name == "aws_polly":
            result = await self._synthesize_aws_polly(
                text, voice_id
            )
        else:
            raise ValueError(f"Unsupported TTS provider: {provider_name}")
        
        # Calculate processing time
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        result["processing_time_ms"] = processing_time_ms
        
        # Store generation record
        generation_id = await self._store_tts_generation(
            user_id=user_id,
            agent_id=agent_id,
            text=text,
            provider=provider_name,
            voice_id=voice_id,
            audio_url=result["audio_url"],
            audio_duration_seconds=result.get("duration"),
            processing_time_ms=processing_time_ms,
            voice_settings={"speed": speed},
            metadata=result.get("metadata", {})
        )
        
        result["generation_id"] = str(generation_id)
        
        # Track usage
        await self.ai_provider._track_usage(
            user_id=user_id,
            service_type=ProviderType.TTS,
            provider=provider_name,
            characters_processed=len(text),
            latency_ms=processing_time_ms,
            agent_id=agent_id
        )
        
        return result
    
    async def _synthesize_elevenlabs(
        self,
        user_id: UUID,
        text: str,
        voice_id: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Synthesize using ElevenLabs"""
        api_key = config.get("api_key_encrypted")
        
        if not api_key:
            # Use managed ElevenLabs account
            managed_key = os.getenv("ELEVENLABS_API_KEY")
            if not managed_key:
                raise ValueError("ElevenLabs API key not configured")
            api_key = managed_key
        
        # ElevenLabs API endpoint
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=data, headers=headers)
                response.raise_for_status()
                
                audio_data = response.content
                
                # Upload to storage
                audio_url = await self.storage_service.upload_audio(
                    audio_data, user_id, "mp3", {"type": "tts", "provider": "elevenlabs"}
                )
                
                # Estimate duration (rough estimate: 150 words per minute)
                word_count = len(text.split())
                estimated_duration = (word_count / 150) * 60
                
                return {
                    "audio_url": audio_url,
                    "duration": estimated_duration,
                    "provider": "elevenlabs",
                    "voice_id": voice_id
                }
        
        except Exception as e:
            logger.error(f"ElevenLabs TTS error: {e}")
            raise
    
    async def _synthesize_openai_tts(
        self,
        user_id: UUID,
        text: str,
        voice_id: str
    ) -> Dict[str, Any]:
        """Synthesize using OpenAI TTS"""
        from .ai_provider_service import ProviderType, ProviderName
        config = await self.ai_provider.get_provider_config(
            user_id, ProviderType.TTS
        )
        
        api_key = config.get("api_key_encrypted")
        client = AsyncOpenAI(api_key=api_key) if api_key else AsyncOpenAI()
        
        # Map voice_id to OpenAI voice names
        voice_map = {
            "default": "alloy",
            "female": "nova",
            "male": "onyx"
        }
        voice = voice_map.get(voice_id, "alloy")
        
        try:
            response = await client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )
            
            audio_data = response.content
            
            # Upload to storage
            audio_url = await self.storage_service.upload_audio(
                audio_data, user_id, "mp3", {"type": "tts", "provider": "openai"}
            )
            
            # Estimate duration
            word_count = len(text.split())
            estimated_duration = (word_count / 150) * 60
            
            return {
                "audio_url": audio_url,
                "duration": estimated_duration,
                "provider": "openai",
                "voice_id": voice
            }
        
        except Exception as e:
            logger.error(f"OpenAI TTS error: {e}")
            raise
    
    async def _synthesize_google_cloud(
        self,
        text: str,
        voice_id: str
    ) -> Dict[str, Any]:
        """Synthesize using Google Cloud Text-to-Speech"""
        try:
            result = await self.google_provider.synthesize_speech(
                text, voice_id, "en-US"
            )
            
            # Upload to storage
            audio_url = await self.storage_service.upload_audio(
                result["audio_data"], UUID("00000000-0000-0000-0000-000000000000"), "mp3",
                {"type": "tts", "provider": "google_cloud"}
            )
            
            return {
                "audio_url": audio_url,
                "duration": len(text) / 150 * 60,  # Estimate
                "provider": "google_cloud"
            }
        except Exception as e:
            logger.error(f"Google Cloud TTS error: {e}")
            raise
    
    async def _synthesize_aws_polly(
        self,
        text: str,
        voice_id: str
    ) -> Dict[str, Any]:
        """Synthesize using AWS Polly"""
        try:
            result = await self.aws_provider.synthesize_speech(
                text, voice_id, "neural"
            )
            
            # Upload to storage
            audio_url = await self.storage_service.upload_audio(
                result["audio_data"], UUID("00000000-0000-0000-0000-000000000000"), "mp3",
                {"type": "tts", "provider": "aws_polly"}
            )
            
            return {
                "audio_url": audio_url,
                "duration": len(text) / 150 * 60,  # Estimate
                "provider": "aws_polly"
            }
        except Exception as e:
            logger.error(f"AWS Polly error: {e}")
            raise
    
    async def _upload_audio(
        self,
        audio_data: bytes,
        user_id: UUID,
        audio_type: str
    ) -> str:
        """Upload audio file to storage (deprecated - use storage_service directly)"""
        return await self.storage_service.upload_audio(
            audio_data, user_id, "mp3", {"type": audio_type}
        )
    
    async def _store_tts_generation(
        self,
        user_id: UUID,
        text: str,
        provider: str,
        voice_id: str,
        audio_url: str,
        agent_id: Optional[UUID] = None,
        audio_duration_seconds: Optional[float] = None,
        processing_time_ms: Optional[int] = None,
        voice_settings: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """Store TTS generation in database"""
        text_length = len(text)
        
        async with self.db_pool.acquire() as conn:
            generation_id = await conn.fetchval(
                """
                INSERT INTO tts_generations (
                    user_id, agent_id, text, text_length,
                    provider, voice_id, voice_settings,
                    audio_url, audio_duration_seconds,
                    processing_time_ms, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING generation_id
                """,
                user_id, agent_id, text, text_length,
                provider, voice_id, voice_settings or {},
                audio_url, audio_duration_seconds,
                processing_time_ms, metadata or {}
            )
        
        return generation_id
    
    # ========================================================================
    # REAL-TIME TRANSCRIPTION (WebSocket)
    # ========================================================================
    
    async def start_realtime_transcription(
        self,
        user_id: UUID,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start real-time transcription stream
        Note: Actual WebSocket implementation is in websocket_handlers.py
        """
        logger.info(f"Starting real-time transcription for user {user_id}")
        
        # Create session in database for tracking
        async with self.db_pool.acquire() as conn:
            session_id = await conn.fetchval(
                """
                INSERT INTO transcription_sessions (user_id, language, status)
                VALUES ($1, $2, 'active')
                RETURNING session_id
                """,
                user_id, language or "en"
            )
        
        return {
            "status": "streaming_ready",
            "session_id": str(session_id),
            "websocket_url": f"wss://ai-core.auralink.com/ws/transcribe/{session_id}",
            "message": "Connect to WebSocket endpoint to start streaming",
            "language": language or "en"
        }
    
    # ========================================================================
    # NOISE CANCELLATION (Future Feature)
    # ========================================================================
    
    async def apply_noise_cancellation(
        self,
        audio_data: bytes
    ) -> bytes:
        """
        Apply noise cancellation to audio using spectral gating
        """
        try:
            import librosa
            import noisereduce as nr
            import soundfile as sf
            
            # Load audio
            audio_array, sample_rate = librosa.load(BytesIO(audio_data), sr=None)
            
            # Apply noise reduction
            reduced_noise = nr.reduce_noise(
                y=audio_array,
                sr=sample_rate,
                stationary=True,
                prop_decrease=0.8
            )
            
            # Convert back to bytes
            output_buffer = BytesIO()
            sf.write(output_buffer, reduced_noise, sample_rate, format='MP3')
            output_buffer.seek(0)
            
            logger.info("Applied noise cancellation to audio")
            return output_buffer.read()
        
        except ImportError:
            logger.warning("Noise reduction libraries not installed (librosa, noisereduce). Returning original audio.")
            return audio_data
        
        except Exception as e:
            logger.error(f"Error applying noise cancellation: {e}")
            return audio_data
    
    # ========================================================================
    # SEARCH & ARCHIVE
    # ========================================================================
    
    async def search_transcriptions(
        self,
        user_id: UUID,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search transcriptions using full-text search"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    transcription_id, text, language, confidence,
                    provider, call_id, created_at,
                    ts_rank(to_tsvector('english', text), plainto_tsquery('english', $1)) as rank
                FROM transcriptions
                WHERE user_id = $2
                    AND to_tsvector('english', text) @@ plainto_tsquery('english', $1)
                ORDER BY rank DESC, created_at DESC
                LIMIT $3
                """,
                query, user_id, limit
            )
        
        return [dict(row) for row in rows]
    
    async def get_transcription(
        self,
        user_id: UUID,
        transcription_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get transcription by ID"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM transcriptions
                WHERE transcription_id = $1 AND user_id = $2
                """,
                transcription_id, user_id
            )
        
        return dict(row) if row else None
