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
        self.enable_aic_grpc = os.getenv("ENABLE_AIC_GRPC", "false").lower() == "true"
        
        # Phase 4 - AI Features
        self.enable_agents = os.getenv("ENABLE_AGENTS", "false").lower() == "true"
        self.enable_speech = os.getenv("ENABLE_SPEECH", "false").lower() == "true"
        self.enable_memory = os.getenv("ENABLE_MEMORY", "false").lower() == "true"
        self.enable_translation = os.getenv("ENABLE_TRANSLATION", "false").lower() == "true"
        self.enable_moderation = os.getenv("ENABLE_MODERATION", "false").lower() == "true"
        self.enable_summarization = os.getenv("ENABLE_SUMMARIZATION", "false").lower() == "true"
        
        # Phase 5 - Advanced AI Features
        self.enable_mcp = os.getenv("ENABLE_MCP", "false").lower() == "true"
        self.enable_workflows = os.getenv("ENABLE_WORKFLOWS", "false").lower() == "true"
        self.enable_langgraph = os.getenv("ENABLE_LANGGRAPH", "false").lower() == "true"
        self.enable_crewai = os.getenv("ENABLE_CREWAI", "false").lower() == "true"
        self.enable_autogen = os.getenv("ENABLE_AUTOGEN", "false").lower() == "true"
        self.enable_llm_selection = os.getenv("ENABLE_LLM_SELECTION", "false").lower() == "true"
        self.enable_prefect = os.getenv("ENABLE_PREFECT", "false").lower() == "true"
        self.enable_temporal = os.getenv("ENABLE_TEMPORAL", "false").lower() == "true"
        
        # Phase 6 - AuraID & Mesh Network
        self.enable_auraid = os.getenv("ENABLE_AURAID", "false").lower() == "true"
        self.enable_mesh = os.getenv("ENABLE_MESH", "false").lower() == "true"
        self.enable_communication_service = os.getenv("ENABLE_COMMUNICATION_SERVICE", "false").lower() == "true"
        self.enable_federated_id = os.getenv("ENABLE_FEDERATED_ID", "false").lower() == "true"
        self.enable_p2p_routing = os.getenv("ENABLE_P2P_ROUTING", "false").lower() == "true"
        
        # Phase 7 - Enterprise Features
        self.enable_sso = os.getenv("ENABLE_SSO", "false").lower() == "true"
        self.enable_rbac = os.getenv("ENABLE_RBAC", "false").lower() == "true"
        self.enable_audit_logging = os.getenv("ENABLE_AUDIT_LOGGING", "false").lower() == "true"
        self.enable_billing = os.getenv("ENABLE_BILLING", "false").lower() == "true"
        self.enable_compliance = os.getenv("ENABLE_COMPLIANCE", "false").lower() == "true"
        self.enable_analytics = os.getenv("ENABLE_ANALYTICS", "false").lower() == "true"
        
        # Infrastructure Features
        self.enable_service_mesh = os.getenv("ENABLE_SERVICE_MESH", "false").lower() == "true"
        self.enable_api_gateway = os.getenv("ENABLE_API_GATEWAY", "false").lower() == "true"
        self.enable_argo_workflows = os.getenv("ENABLE_ARGO_WORKFLOWS", "false").lower() == "true"
        self.enable_airflow = os.getenv("ENABLE_AIRFLOW", "false").lower() == "true"
        
        # External Media Features
        self.enable_sip = os.getenv("ENABLE_SIP", "false").lower() == "true"
        self.enable_streaming = os.getenv("ENABLE_STREAMING", "false").lower() == "true"
        
        # Deployment Mode
        self.first_launch_mode = os.getenv("FIRST_LAUNCH_MODE", "false").lower() == "true"
        
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
