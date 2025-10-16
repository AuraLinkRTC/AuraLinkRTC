"""
Configuration Management for Communication Service
Loads environment variables and provides centralized configuration
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, RedisDsn


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    # Service configuration
    service_name: str = Field(default="auralink-communication-service", env="SERVICE_NAME")
    environment: str = Field(default="development", env="ENVIRONMENT")
    service_port: int = Field(default=8001, env="SERVICE_PORT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Database configuration
    database_url: PostgresDsn = Field(..., env="DATABASE_URL")
    database_pool_min: int = Field(default=5, env="DATABASE_POOL_MIN")
    database_pool_max: int = Field(default=20, env="DATABASE_POOL_MAX")
    database_pool_timeout: int = Field(default=30, env="DATABASE_POOL_TIMEOUT")
    database_command_timeout: int = Field(default=60, env="DATABASE_COMMAND_TIMEOUT")
    
    # Redis configuration
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    redis_max_connections: int = Field(default=50, env="REDIS_MAX_CONNECTIONS")
    
    # Matrix server configuration
    matrix_server_url: str = Field(default="http://localhost:8008", env="MATRIX_SERVER_URL")
    matrix_admin_token: str = Field(..., env="MATRIX_ADMIN_TOKEN")
    matrix_homeserver: str = Field(default="auralink.network", env="MATRIX_HOMESERVER")
    
    # Dashboard service configuration
    dashboard_url: str = Field(default="http://dashboard-service:8080", env="DASHBOARD_URL")
    dashboard_jwt_secret: str = Field(..., env="DASHBOARD_JWT_SECRET")
    
    # AI Core service configuration
    ai_core_url: str = Field(default="http://ai-core:8000", env="AI_CORE_URL")
    ai_core_grpc_url: str = Field(default="ai-core:50051", env="AI_CORE_GRPC_URL")
    
    # WebRTC server configuration
    webrtc_server_url: str = Field(default="http://webrtc-server:7880", env="WEBRTC_SERVER_URL")
    livekit_url: Optional[str] = Field(default=None, env="LIVEKIT_URL")
    livekit_api_key: Optional[str] = Field(default=None, env="LIVEKIT_API_KEY")
    livekit_api_secret: Optional[str] = Field(default=None, env="LIVEKIT_API_SECRET")
    
    # External services configuration
    sendgrid_api_key: Optional[str] = Field(default=None, env="SENDGRID_API_KEY")
    twilio_account_sid: Optional[str] = Field(default=None, env="TWILIO_ACCOUNT_SID")
    twilio_auth_token: Optional[str] = Field(default=None, env="TWILIO_AUTH_TOKEN")
    twilio_phone_number: Optional[str] = Field(default=None, env="TWILIO_PHONE_NUMBER")
    stripe_secret_key: Optional[str] = Field(default=None, env="STRIPE_SECRET_KEY")
    
    # JWT configuration
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expiration_minutes: int = Field(default=60, env="JWT_EXPIRATION_MINUTES")
    
    # Rate limiting configuration
    rate_limit_per_user: int = Field(default=100, env="RATE_LIMIT_PER_USER")
    rate_limit_per_service: int = Field(default=1000, env="RATE_LIMIT_PER_SERVICE")
    rate_limit_window_seconds: int = Field(default=60, env="RATE_LIMIT_WINDOW_SECONDS")
    
    # Mesh routing configuration
    route_cache_ttl: int = Field(default=300, env="ROUTE_CACHE_TTL")
    mesh_heartbeat_interval: int = Field(default=30, env="MESH_HEARTBEAT_INTERVAL")
    mesh_node_offline_threshold: int = Field(default=120, env="MESH_NODE_OFFLINE_THRESHOLD")
    
    # Trust system configuration
    trust_base_score: float = Field(default=50.0, env="TRUST_BASE_SCORE")
    trust_suspension_threshold: float = Field(default=20.0, env="TRUST_SUSPENSION_THRESHOLD")
    trust_abuse_penalty: float = Field(default=20.0, env="TRUST_ABUSE_PENALTY")
    
    # CORS configuration
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        env="CORS_ORIGINS"
    )
    
    # Monitoring configuration
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    enable_tracing: bool = Field(default=True, env="ENABLE_TRACING")
    jaeger_endpoint: Optional[str] = Field(default=None, env="JAEGER_ENDPOINT")
    
    # Feature flags
    enable_aic_protocol: bool = Field(default=True, env="ENABLE_AIC_PROTOCOL")
    enable_mesh_routing: bool = Field(default=True, env="ENABLE_MESH_ROUTING")
    enable_ai_optimization: bool = Field(default=True, env="ENABLE_AI_OPTIMIZATION")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment.lower() in ["development", "dev", "local"]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment.lower() in ["production", "prod"]
    
    @property
    def redis_connection_url(self) -> str:
        """Get Redis connection URL with password if configured"""
        if self.redis_password:
            # Parse redis_url and inject password
            parts = self.redis_url.split("://")
            if len(parts) == 2:
                return f"{parts[0]}://:{self.redis_password}@{parts[1]}"
        return self.redis_url


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get global settings instance (singleton pattern)
    
    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Force reload settings from environment
    
    Returns:
        New settings instance
    """
    global _settings
    _settings = Settings()
    return _settings
