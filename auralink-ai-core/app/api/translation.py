"""
Translation API endpoints
"""

from fastapi import APIRouter, Depends, status
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging

from app.api.deps import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


class TranslationRequest(BaseModel):
    """Translation request"""
    text: str = Field(..., description="Text to translate")
    source_language: str = Field(..., description="Source language code (e.g., 'en')")
    target_language: str = Field(..., description="Target language code (e.g., 'es')")
    context: Optional[str] = Field(None, description="Context for better translation")


class TranslationResponse(BaseModel):
    """Translation response"""
    translated_text: str
    source_language: str
    target_language: str
    confidence: float


class SupportedLanguage(BaseModel):
    """Supported language"""
    code: str
    name: str
    native_name: str


# Supported languages (10+ as per requirements)
SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English", "native_name": "English"},
    {"code": "es", "name": "Spanish", "native_name": "Español"},
    {"code": "fr", "name": "French", "native_name": "Français"},
    {"code": "de", "name": "German", "native_name": "Deutsch"},
    {"code": "ja", "name": "Japanese", "native_name": "日本語"},
    {"code": "zh", "name": "Chinese", "native_name": "中文"},
    {"code": "ar", "name": "Arabic", "native_name": "العربية"},
    {"code": "pt", "name": "Portuguese", "native_name": "Português"},
    {"code": "ru", "name": "Russian", "native_name": "Русский"},
    {"code": "it", "name": "Italian", "native_name": "Italiano"},
    {"code": "ko", "name": "Korean", "native_name": "한국어"},
    {"code": "hi", "name": "Hindi", "native_name": "हिन्दी"},
]


@router.get("/languages", response_model=List[SupportedLanguage])
async def get_supported_languages() -> List[SupportedLanguage]:
    """
    Get list of supported languages
    """
    return [SupportedLanguage(**lang) for lang in SUPPORTED_LANGUAGES]


@router.post("/translate", response_model=TranslationResponse)
async def translate_text(
    request: TranslationRequest,
    user: Dict[str, Any] = Depends(get_current_user)
) -> TranslationResponse:
    """
    Translate text from one language to another
    """
    from uuid import UUID
    from app.core.dependencies import get_translation_service
    
    logger.info(
        f"Translation request: {request.source_language} -> {request.target_language} "
        f"for user {user['user_id']}"
    )
    
    translation_service = get_translation_service()
    
    result = await translation_service.translate(
        user_id=UUID(user["user_id"]),
        text=request.text,
        source_language=request.source_language,
        target_language=request.target_language,
        context=request.context
    )
    
    return TranslationResponse(
        translated_text=result["translated_text"],
        source_language=result["source_language"],
        target_language=result["target_language"],
        confidence=result["confidence"]
    )


@router.post("/translate-realtime")
async def translate_realtime(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Real-time translation stream for calls
    """
    logger.info(f"Real-time translation for user {user['user_id']}")
    
    # TODO: Implement WebSocket-based real-time translation
    # - Receive audio/text stream
    # - Translate in real-time
    # - Maintain conversation context
    
    return {
        "status": "realtime_not_implemented",
        "message": "WebSocket endpoint needed"
    }
