"""
Speech processing API endpoints (STT/TTS)
"""

from fastapi import APIRouter, Depends, File, UploadFile, status
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import logging

from app.api.deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


class TTSRequest(BaseModel):
    """Text-to-Speech request"""
    text: str = Field(..., description="Text to convert to speech")
    voice: str = Field("default", description="Voice ID")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speech speed")
    provider: str = Field("elevenlabs", description="TTS provider")


class TTSResponse(BaseModel):
    """Text-to-Speech response"""
    audio_url: str
    duration: float
    provider: str


class STTResponse(BaseModel):
    """Speech-to-Text response"""
    text: str
    language: str
    confidence: float
    duration: float


@router.post("/tts", response_model=TTSResponse)
async def text_to_speech(
    request: TTSRequest,
    user: Dict[str, Any] = Depends(get_current_user)
) -> TTSResponse:
    """
    Convert text to speech
    """
    from uuid import UUID
    from app.core.dependencies import get_speech_service
    
    logger.info(f"TTS request for user {user['user_id']}")
    
    speech_service = get_speech_service()
    
    result = await speech_service.synthesize_speech(
        user_id=UUID(user["user_id"]),
        text=request.text,
        voice_id=request.voice,
        speed=request.speed,
        provider=request.provider
    )
    
    return TTSResponse(
        audio_url=result["audio_url"],
        duration=result.get("duration", 0.0),
        provider=result.get("provider", request.provider)
    )


@router.post("/stt", response_model=STTResponse)
async def speech_to_text(
    audio: UploadFile = File(...),
    language: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user)
) -> STTResponse:
    """
    Convert speech to text
    """
    from uuid import UUID
    from app.core.dependencies import get_speech_service
    
    logger.info(f"STT request for user {user['user_id']}")
    
    # Read audio data
    audio_data = await audio.read()
    
    speech_service = get_speech_service()
    
    result = await speech_service.transcribe_audio(
        user_id=UUID(user["user_id"]),
        audio_data=audio_data,
        language=language
    )
    
    return STTResponse(
        text=result["text"],
        language=result["language"],
        confidence=result["confidence"],
        duration=result.get("duration", 0.0)
    )


@router.post("/transcribe-stream")
async def transcribe_stream(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Real-time speech transcription stream
    """
    logger.info(f"Stream transcription for user {user['user_id']}")
    
    # TODO: Implement WebSocket-based streaming STT
    # - Accept audio chunks
    # - Process in real-time
    # - Return transcription incrementally
    
    return {
        "status": "streaming_not_implemented",
        "message": "WebSocket endpoint needed"
    }
