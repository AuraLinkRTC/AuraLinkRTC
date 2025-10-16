"""
Configuration management for AuraLink Python services
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class DatabaseConfig:
    """Database configuration"""
    provider: str = "supabase"
    host: str = ""
    port: int = 5432
    database: str = "postgres"
    max_connections: int = 100
    
    @property
    def url(self) -> str:
        """Get database URL from environment or construct it"""
        env_url = os.getenv("DATABASE_URL")
        if env_url:
            return env_url
        return f"postgresql://postgres@{self.host}:{self.port}/{self.database}"


@dataclass
class RedisConfig:
    """Redis configuration"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    max_retries: int = 3
    pool_size: int = 10
    
    @property
    def url(self) -> str:
        """Get Redis URL"""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class AuthConfig:
    """Authentication configuration"""
    provider: str = "supabase"
    jwt_expiration: int = 24  # hours
    refresh_token_expiration: int = 168  # hours (7 days)


@dataclass
class ServiceConfig:
    """Service configuration"""
    name: str = "auralink-service"
    port: int = 8000
    host: str = "0.0.0.0"
    health_check_path: str = "/health"
    timeout: int = 30


@dataclass
class MonitoringConfig:
    """Monitoring configuration"""
    log_level: str = "info"
    log_format: str = "json"
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    jaeger_enabled: bool = False
    jaeger_endpoint: str = ""


@dataclass
class AICConfig:
    """AIC Protocol configuration"""
    enabled: bool = False
    compression_ratio: float = 0.8
    fallback_enabled: bool = True
    min_bandwidth: int = 500  # kbps


@dataclass
class Config:
    """Main configuration class"""
    environment: str = "development"
    service: ServiceConfig = field(default_factory=ServiceConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    aic: AICConfig = field(default_factory=AICConfig)
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment in ["development", "dev"]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment in ["production", "prod"]


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from file and environment variables
    
    Args:
        config_path: Path to YAML config file
        
    Returns:
        Config instance
    """
    config_dict: Dict[str, Any] = {}
    
    # Load from YAML file if provided
    if config_path and Path(config_path).exists():
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f) or {}
    
    # Create config with defaults
    config = Config()
    
    # Apply config file values
    if config_dict:
        config.environment = config_dict.get("environment", config.environment)
        
        if "service" in config_dict:
            svc = config_dict["service"]
            config.service = ServiceConfig(
                name=svc.get("name", config.service.name),
                port=svc.get("port", config.service.port),
                host=svc.get("host", config.service.host),
            )
        
        if "database" in config_dict:
            db = config_dict["database"]
            config.database = DatabaseConfig(
                provider=db.get("provider", config.database.provider),
                host=db.get("host", config.database.host),
                port=db.get("port", config.database.port),
                database=db.get("database", config.database.database),
            )
        
        if "redis" in config_dict:
            rd = config_dict["redis"]
            config.redis = RedisConfig(
                host=rd.get("host", config.redis.host),
                port=rd.get("port", config.redis.port),
                db=rd.get("db", config.redis.db),
            )
        
        if "aic" in config_dict:
            aic = config_dict["aic"]
            config.aic = AICConfig(
                enabled=aic.get("enabled", config.aic.enabled),
                compression_ratio=aic.get("compression_ratio", config.aic.compression_ratio),
            )
    
    # Override with environment variables
    _apply_env_overrides(config)
    
    return config


def _apply_env_overrides(config: Config) -> None:
    """Apply environment variable overrides"""
    
    # Environment
    if env := os.getenv("ENVIRONMENT"):
        config.environment = env
    
    # Service
    if port := os.getenv("SERVICE_PORT"):
        config.service.port = int(port)
    if name := os.getenv("SERVICE_NAME"):
        config.service.name = name
    
    # Database
    if host := os.getenv("SUPABASE_URL"):
        config.database.host = host
    
    # Redis
    if host := os.getenv("REDIS_HOST"):
        # Parse host:port format
        if ":" in host:
            parts = host.split(":")
            config.redis.host = parts[0]
            config.redis.port = int(parts[1])
        else:
            config.redis.host = host
    if password := os.getenv("REDIS_PASSWORD"):
        config.redis.password = password
    
    # AIC
    if enable_aic := os.getenv("ENABLE_AIC"):
        config.aic.enabled = enable_aic.lower() == "true"
    
    # Monitoring
    if log_level := os.getenv("LOG_LEVEL"):
        config.monitoring.log_level = log_level
