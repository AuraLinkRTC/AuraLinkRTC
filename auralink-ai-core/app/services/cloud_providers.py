"""
Cloud Provider Integrations
Enterprise-grade integrations for Google Cloud, Azure, and AWS
"""

import logging
import os
from typing import Dict, Any, Optional
from io import BytesIO
import base64

import httpx

logger = logging.getLogger(__name__)


class GoogleCloudProvider:
    """
    Google Cloud Platform Integration
    
    Services:
    - Speech-to-Text
    - Text-to-Speech
    - Translation API
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_CLOUD_API_KEY")
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        self.base_url = "https://speech.googleapis.com/v1"
        self.tts_base_url = "https://texttospeech.googleapis.com/v1"
    
    async def transcribe_audio(
        self,
        audio_data: bytes,
        language: str = "en-US"
    ) -> Dict[str, Any]:
        """
        Transcribe audio using Google Cloud Speech-to-Text
        """
        if not self.api_key:
            raise ValueError("Google Cloud API key not configured")
        
        try:
            # Encode audio to base64
            audio_b64 = base64.b64encode(audio_data).decode()
            
            url = f"{self.base_url}/speech:recognize?key={self.api_key}"
            
            payload = {
                "config": {
                    "encoding": "MP3",
                    "sampleRateHertz": 16000,
                    "languageCode": language,
                    "enableAutomaticPunctuation": True,
                    "model": "default"
                },
                "audio": {
                    "content": audio_b64
                }
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                
                if "results" not in result or not result["results"]:
                    return {
                        "text": "",
                        "language": language,
                        "confidence": 0.0,
                        "model": "google-cloud-stt"
                    }
                
                # Extract transcript
                transcript = ""
                max_confidence = 0.0
                
                for result_item in result["results"]:
                    if "alternatives" in result_item and result_item["alternatives"]:
                        alternative = result_item["alternatives"][0]
                        transcript += alternative.get("transcript", "")
                        max_confidence = max(max_confidence, alternative.get("confidence", 0.0))
                
                return {
                    "text": transcript.strip(),
                    "language": language,
                    "confidence": max_confidence,
                    "model": "google-cloud-stt",
                    "raw_response": result
                }
        
        except Exception as e:
            logger.error(f"Google Cloud STT error: {e}")
            raise
    
    async def synthesize_speech(
        self,
        text: str,
        voice_id: str = "en-US-Standard-A",
        language: str = "en-US"
    ) -> Dict[str, Any]:
        """
        Synthesize speech using Google Cloud Text-to-Speech
        """
        if not self.api_key:
            raise ValueError("Google Cloud API key not configured")
        
        try:
            url = f"{self.tts_base_url}/text:synthesize?key={self.api_key}"
            
            payload = {
                "input": {"text": text},
                "voice": {
                    "languageCode": language,
                    "name": voice_id
                },
                "audioConfig": {
                    "audioEncoding": "MP3",
                    "pitch": 0.0,
                    "speakingRate": 1.0
                }
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                
                # Decode audio content
                audio_data = base64.b64decode(result["audioContent"])
                
                return {
                    "audio_data": audio_data,
                    "format": "mp3",
                    "model": "google-cloud-tts"
                }
        
        except Exception as e:
            logger.error(f"Google Cloud TTS error: {e}")
            raise


class AzureProvider:
    """
    Microsoft Azure Integration
    
    Services:
    - Speech Services (STT/TTS)
    - Cognitive Services
    """
    
    def __init__(self, api_key: Optional[str] = None, region: Optional[str] = None):
        self.api_key = api_key or os.getenv("AZURE_SPEECH_KEY")
        self.region = region or os.getenv("AZURE_REGION", "eastus")
        self.base_url = f"https://{self.region}.api.cognitive.microsoft.com/sts/v1.0"
        self.stt_url = f"https://{self.region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
    
    async def transcribe_audio(
        self,
        audio_data: bytes,
        language: str = "en-US"
    ) -> Dict[str, Any]:
        """
        Transcribe audio using Azure Speech Services
        """
        if not self.api_key:
            raise ValueError("Azure Speech API key not configured")
        
        try:
            headers = {
                "Ocp-Apim-Subscription-Key": self.api_key,
                "Content-Type": "audio/wav",
                "Accept": "application/json"
            }
            
            params = {
                "language": language,
                "format": "detailed"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.stt_url,
                    headers=headers,
                    params=params,
                    content=audio_data
                )
                response.raise_for_status()
                
                result = response.json()
                
                return {
                    "text": result.get("DisplayText", ""),
                    "language": language,
                    "confidence": result.get("Confidence", 0.0),
                    "model": "azure-stt",
                    "raw_response": result
                }
        
        except Exception as e:
            logger.error(f"Azure STT error: {e}")
            raise
    
    async def synthesize_speech(
        self,
        text: str,
        voice_id: str = "en-US-AriaNeural",
        language: str = "en-US"
    ) -> Dict[str, Any]:
        """
        Synthesize speech using Azure Speech Services
        """
        if not self.api_key:
            raise ValueError("Azure Speech API key not configured")
        
        try:
            # Get access token
            token_url = self.base_url + "/issuetoken"
            headers = {"Ocp-Apim-Subscription-Key": self.api_key}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                token_response = await client.post(token_url, headers=headers)
                token_response.raise_for_status()
                access_token = token_response.text
                
                # Synthesize speech
                tts_url = f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1"
                
                ssml = f"""
                <speak version='1.0' xml:lang='{language}'>
                    <voice xml:lang='{language}' name='{voice_id}'>
                        {text}
                    </voice>
                </speak>
                """
                
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3"
                }
                
                response = await client.post(tts_url, headers=headers, content=ssml)
                response.raise_for_status()
                
                audio_data = response.content
                
                return {
                    "audio_data": audio_data,
                    "format": "mp3",
                    "model": "azure-tts"
                }
        
        except Exception as e:
            logger.error(f"Azure TTS error: {e}")
            raise


class AWSProvider:
    """
    Amazon Web Services Integration
    
    Services:
    - Amazon Polly (TTS)
    - Amazon Transcribe (STT)
    """
    
    def __init__(
        self,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: Optional[str] = None
    ):
        self.access_key = access_key or os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        
        # Try to use boto3 if available
        try:
            import boto3
            self.polly_client = boto3.client(
                'polly',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
            self.has_boto3 = True
        except ImportError:
            logger.warning("boto3 not installed. AWS Polly will not be available.")
            self.polly_client = None
            self.has_boto3 = False
    
    async def synthesize_speech(
        self,
        text: str,
        voice_id: str = "Joanna",
        engine: str = "neural"
    ) -> Dict[str, Any]:
        """
        Synthesize speech using AWS Polly
        """
        if not self.has_boto3 or not self.polly_client:
            raise ValueError("AWS Polly not configured or boto3 not installed")
        
        try:
            response = self.polly_client.synthesize_speech(
                Text=text,
                OutputFormat='mp3',
                VoiceId=voice_id,
                Engine=engine
            )
            
            # Read audio stream
            audio_data = response['AudioStream'].read()
            
            return {
                "audio_data": audio_data,
                "format": "mp3",
                "model": f"aws-polly-{engine}"
            }
        
        except Exception as e:
            logger.error(f"AWS Polly error: {e}")
            raise


# Singleton instances
_google_provider: Optional[GoogleCloudProvider] = None
_azure_provider: Optional[AzureProvider] = None
_aws_provider: Optional[AWSProvider] = None


def get_google_provider() -> GoogleCloudProvider:
    """Get Google Cloud Provider singleton"""
    global _google_provider
    if _google_provider is None:
        _google_provider = GoogleCloudProvider()
    return _google_provider


def get_azure_provider() -> AzureProvider:
    """Get Azure Provider singleton"""
    global _azure_provider
    if _azure_provider is None:
        _azure_provider = AzureProvider()
    return _azure_provider


def get_aws_provider() -> AWSProvider:
    """Get AWS Provider singleton"""
    global _aws_provider
    if _aws_provider is None:
        _aws_provider = AWSProvider()
    return _aws_provider
