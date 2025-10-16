"""
Configuration management for AI Core service
"""

import os
from functools import lru_cache
from typing import List


class Settings:
    """Application settings"""
    
    def __init__(self):
        # Environment
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        # Service
        self.service_name = os.getenv("SERVICE_NAME", "auralink-ai-core")
        self.service_port = int(os.getenv("AI_CORE_PORT", "8000"))
        
        # Database
        self.database_url = os.getenv("DATABASE_URL", "")
        self.supabase_url = os.getenv("SUPABASE_URL", "")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY", "")
        self.supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "")
        
        # Redis
        self.redis_url = os.getenv("REDIS_HOST", "localhost:6379")
        self.redis_password = os.getenv("REDIS_PASSWORD", "")
        
        # External service URLs
        self.webrtc_server_url = os.getenv("WEBRTC_SERVER_URL", "http://localhost:7880")
        self.dashboard_service_url = os.getenv("DASHBOARD_SERVICE_URL", "http://localhost:8080")
        
        # AI Provider Keys (Optional - BYOK)
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        self.whisper_api_key = os.getenv("WHISPER_API_KEY", "")
        
        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        
        # CORS
        cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080")
        self.cors_origins: List[str] = [origin.strip() for origin in cors_origins_str.split(",")]
        
        # AIC Protocol
        self.enable_aic = os.getenv("ENABLE_AIC", "false").lower() == "true"
        
        # Monitoring
        self.prometheus_enabled = True
        self.jaeger_endpoint = os.getenv("JAEGER_ENDPOINT", "")
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment in ["development", "dev"]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment in ["production", "prod"]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
