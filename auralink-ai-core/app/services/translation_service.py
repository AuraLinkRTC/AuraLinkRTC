"""
Translation Service - Real-time Translation with 10+ Languages
Context-aware translation with cultural adaptation
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime

import asyncpg

logger = logging.getLogger(__name__)


# Supported languages (12 languages as per requirements)
SUPPORTED_LANGUAGES = {
    "en": {"name": "English", "native_name": "English"},
    "es": {"name": "Spanish", "native_name": "Español"},
    "fr": {"name": "French", "native_name": "Français"},
    "de": {"name": "German", "native_name": "Deutsch"},
    "ja": {"name": "Japanese", "native_name": "日本語"},
    "zh": {"name": "Chinese", "native_name": "中文"},
    "ar": {"name": "Arabic", "native_name": "العربية"},
    "pt": {"name": "Portuguese", "native_name": "Português"},
    "ru": {"name": "Russian", "native_name": "Русский"},
    "it": {"name": "Italian", "native_name": "Italiano"},
    "ko": {"name": "Korean", "native_name": "한국어"},
    "hi": {"name": "Hindi", "native_name": "हिन्दी"},
}


class TranslationService:
    """
    Translation Service
    
    Features:
    - Real-time translation for 10+ languages
    - Context preservation
    - Cultural adaptation
    - Conversation history for better translation
    """
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        ai_provider_service: Any
    ):
        self.db_pool = db_pool
        self.ai_provider = ai_provider_service
        self.supported_languages = SUPPORTED_LANGUAGES
    
    # ========================================================================
    # TRANSLATION
    # ========================================================================
    
    async def translate(
        self,
        user_id: UUID,
        text: str,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
        call_id: Optional[str] = None,
        preserve_tone: bool = True
    ) -> Dict[str, Any]:
        """
        Translate text from source to target language
        """
        start_time = datetime.utcnow()
        logger.info(f"Translating {source_language} -> {target_language} for user {user_id}")
        
        # Validate languages
        if source_language not in self.supported_languages:
            raise ValueError(f"Unsupported source language: {source_language}")
        
        if target_language not in self.supported_languages:
            raise ValueError(f"Unsupported target language: {target_language}")
        
        # Build translation prompt
        messages = self._build_translation_prompt(
            text, source_language, target_language, context, preserve_tone
        )
        
        # Get translation using LLM
        from .ai_provider_service import ProviderType
        result = await self.ai_provider.chat_completion(
            user_id=user_id,
            messages=messages,
            temperature=0.3,  # Lower temperature for more consistent translation
            max_tokens=1000
        )
        
        translated_text = result["content"].strip()
        
        # Calculate confidence (based on LLM response quality)
        confidence = self._calculate_confidence(text, translated_text, result)
        
        # Calculate processing time
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        # Store translation
        translation_id = await self._store_translation(
            user_id=user_id,
            call_id=call_id,
            source_text=text,
            source_language=source_language,
            translated_text=translated_text,
            target_language=target_language,
            confidence=confidence,
            provider=result.get("model", "openai"),
            model=result.get("model"),
            processing_time_ms=processing_time_ms,
            context=context,
            metadata={
                "tokens_used": result["usage"]["total_tokens"],
                "preserve_tone": preserve_tone
            }
        )
        
        return {
            "translation_id": str(translation_id),
            "translated_text": translated_text,
            "source_language": source_language,
            "target_language": target_language,
            "confidence": confidence,
            "processing_time_ms": processing_time_ms,
            "metadata": {
                "tokens_used": result["usage"]["total_tokens"]
            }
        }
    
    def _build_translation_prompt(
        self,
        text: str,
        source_language: str,
        target_language: str,
        context: Optional[str],
        preserve_tone: bool
    ) -> List[Dict[str, str]]:
        """Build prompt for translation"""
        source_lang_name = self.supported_languages[source_language]["name"]
        target_lang_name = self.supported_languages[target_language]["name"]
        
        system_prompt = f"""You are a professional translator specializing in {source_lang_name} to {target_lang_name} translation.

Your task:
1. Translate the given text accurately
2. Preserve the original meaning and nuance
3. {"Maintain the tone and style of the original" if preserve_tone else "Use a neutral, professional tone"}
4. Adapt cultural references appropriately for the target audience
5. Only return the translated text, no explanations

Important:
- Maintain formatting (line breaks, punctuation)
- Keep proper nouns unchanged unless they have standard translations
- Be culturally sensitive and appropriate"""

        if context:
            system_prompt += f"\n\nContext: {context}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Translate this {source_lang_name} text to {target_lang_name}:\n\n{text}"}
        ]
        
        return messages
    
    def _calculate_confidence(
        self,
        source_text: str,
        translated_text: str,
        llm_result: Dict[str, Any]
    ) -> float:
        """Calculate translation confidence score"""
        # Simple heuristic based on:
        # 1. Length ratio (should be somewhat similar)
        # 2. LLM finish reason
        # 3. Presence of translated content
        
        if not translated_text or translated_text == source_text:
            return 0.5
        
        length_ratio = len(translated_text) / len(source_text)
        
        # Expect ratio between 0.5 and 2.0 for most language pairs
        if 0.5 <= length_ratio <= 2.0:
            length_score = 0.95
        else:
            length_score = 0.75
        
        # Check finish reason
        if llm_result.get("finish_reason") == "stop":
            completion_score = 0.95
        else:
            completion_score = 0.75
        
        # Average scores
        confidence = (length_score + completion_score) / 2
        
        return round(confidence, 3)
    
    async def _store_translation(
        self,
        user_id: UUID,
        source_text: str,
        source_language: str,
        translated_text: str,
        target_language: str,
        confidence: float,
        provider: str,
        call_id: Optional[str] = None,
        model: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
        context: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """Store translation in database"""
        async with self.db_pool.acquire() as conn:
            translation_id = await conn.fetchval(
                """
                INSERT INTO translations (
                    user_id, call_id, source_text, source_language,
                    translated_text, target_language, confidence,
                    provider, model, processing_time_ms, context, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING translation_id
                """,
                user_id, call_id, source_text, source_language,
                translated_text, target_language, confidence,
                provider, model, processing_time_ms, context, metadata or {}
            )
        
        return translation_id
    
    # ========================================================================
    # BATCH TRANSLATION
    # ========================================================================
    
    async def translate_batch(
        self,
        user_id: UUID,
        texts: List[str],
        source_language: str,
        target_language: str,
        context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Translate multiple texts efficiently with parallel processing"""
        logger.info(f"Batch translating {len(texts)} texts")
        
        # Process translations in parallel
        import asyncio
        
        async def translate_single(text: str) -> Dict[str, Any]:
            try:
                return await self.translate(
                    user_id, text, source_language, target_language, context
                )
            except Exception as e:
                logger.error(f"Error translating text: {e}")
                return {
                    "error": str(e),
                    "source_text": text
                }
        
        # Execute translations concurrently with limit
        results = []
        batch_size = 5  # Process 5 at a time to avoid rate limits
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[translate_single(text) for text in batch],
                return_exceptions=False
            )
            results.extend(batch_results)
        
        return results
    
    # ========================================================================
    # CONVERSATION CONTEXT
    # ========================================================================
    
    async def translate_with_conversation_context(
        self,
        user_id: UUID,
        text: str,
        source_language: str,
        target_language: str,
        call_id: str,
        max_history: int = 5
    ) -> Dict[str, Any]:
        """
        Translate with conversation history for better context
        """
        # Get recent translations from this call
        history = await self._get_conversation_history(
            user_id, call_id, max_history
        )
        
        # Build context from history
        context_parts = []
        for item in history:
            context_parts.append(
                f"{item['source_text']} -> {item['translated_text']}"
            )
        
        context = "Previous conversation:\n" + "\n".join(context_parts) if context_parts else None
        
        # Translate with context
        return await self.translate(
            user_id, text, source_language, target_language,
            context=context, call_id=call_id
        )
    
    async def _get_conversation_history(
        self,
        user_id: UUID,
        call_id: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Get recent translations from a call"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT source_text, translated_text, source_language, target_language
                FROM translations
                WHERE user_id = $1 AND call_id = $2
                ORDER BY created_at DESC
                LIMIT $3
                """,
                user_id, call_id, limit
            )
        
        return [dict(row) for row in reversed(rows)]  # Chronological order
    
    # ========================================================================
    # REAL-TIME TRANSLATION (WebSocket)
    # ========================================================================
    
    async def start_realtime_translation(
        self,
        user_id: UUID,
        source_language: str,
        target_language: str,
        call_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start real-time translation stream
        Note: Actual WebSocket implementation is in websocket_handlers.py
        """
        logger.info(f"Starting real-time translation {source_language} -> {target_language}")
        
        # Create translation session in database
        async with self.db_pool.acquire() as conn:
            session_id = await conn.fetchval(
                """
                INSERT INTO translation_sessions (
                    user_id, call_id, source_language, target_language, status
                )
                VALUES ($1, $2, $3, $4, 'active')
                RETURNING session_id
                """,
                user_id, call_id, source_language, target_language
            )
        
        return {
            "status": "streaming_ready",
            "session_id": str(session_id),
            "websocket_url": f"wss://ai-core.auralink.com/ws/translate/{session_id}",
            "source_language": source_language,
            "target_language": target_language,
            "message": "Connect to WebSocket endpoint to start streaming"
        }
    
    # ========================================================================
    # LANGUAGE DETECTION
    # ========================================================================
    
    async def detect_language(
        self,
        user_id: UUID,
        text: str
    ) -> Dict[str, Any]:
        """
        Detect language of text
        """
        # Build detection prompt
        languages_list = ", ".join([
            f"{code} ({info['name']})" 
            for code, info in self.supported_languages.items()
        ])
        
        messages = [
            {
                "role": "system",
                "content": f"""Detect the language of the given text. 
                
Supported languages: {languages_list}

Return only the two-letter language code (e.g., 'en', 'es', 'fr')."""
            },
            {"role": "user", "content": text}
        ]
        
        result = await self.ai_provider.chat_completion(
            user_id=user_id,
            messages=messages,
            temperature=0.0,
            max_tokens=10
        )
        
        detected_code = result["content"].strip().lower()
        
        # Validate detected language
        if detected_code not in self.supported_languages:
            detected_code = "en"  # Default to English
        
        return {
            "language_code": detected_code,
            "language_name": self.supported_languages[detected_code]["name"],
            "confidence": 0.9  # LLMs are generally reliable at language detection
        }
    
    # ========================================================================
    # UTILITIES
    # ========================================================================
    
    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Get list of supported languages"""
        return [
            {
                "code": code,
                "name": info["name"],
                "native_name": info["native_name"]
            }
            for code, info in self.supported_languages.items()
        ]
    
    async def get_translation_stats(
        self,
        user_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get translation statistics for user"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_translations,
                    COUNT(DISTINCT source_language) as source_languages_count,
                    COUNT(DISTINCT target_language) as target_languages_count,
                    AVG(confidence) as avg_confidence,
                    AVG(processing_time_ms) as avg_processing_time_ms,
                    SUM(LENGTH(source_text)) as total_characters_translated
                FROM translations
                WHERE user_id = $1
                    AND created_at > NOW() - INTERVAL '{days} days'
                """.format(days=days),
                user_id
            )
        
        return dict(row) if row else {}
    
    async def get_translation(
        self,
        user_id: UUID,
        translation_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get translation by ID"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM translations
                WHERE translation_id = $1 AND user_id = $2
                """,
                translation_id, user_id
            )
        
        return dict(row) if row else None
