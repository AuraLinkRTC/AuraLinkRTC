"""
MCP Configuration Loader
Loads and validates MCP server configuration from YAML
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class MCPConfig:
    """MCP Configuration Manager"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize MCP configuration
        
        Args:
            config_path: Path to mcp-config.yaml file
        """
        if config_path is None:
            # Default path
            config_path = os.path.join(
                os.path.dirname(__file__),
                '../../../shared/configs/mcp-config.yaml'
            )
        
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            config_file = Path(self.config_path)
            
            if not config_file.exists():
                logger.warning(f"MCP config file not found: {self.config_path}")
                return self._get_default_config()
            
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Replace environment variables
            config = self._replace_env_vars(config)
            
            logger.info("MCP configuration loaded successfully")
            return config
            
        except Exception as e:
            logger.error(f"Failed to load MCP config: {e}")
            return self._get_default_config()
    
    def _replace_env_vars(self, config: Any) -> Any:
        """Replace ${VAR} with environment variable values"""
        if isinstance(config, dict):
            return {k: self._replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith('${') and config.endswith('}'):
            var_name = config[2:-1]
            return os.getenv(var_name, config)
        else:
            return config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if file not found"""
        return {
            'mcp_servers': {
                'deepwiki': {
                    'enabled': False,
                    'endpoint': 'http://localhost:8080',
                    'timeout': 30,
                    'fallback_enabled': True
                },
                'memory': {
                    'enabled': False,
                    'endpoint': 'http://localhost:8081',
                    'timeout': 30,
                    'fallback_enabled': True
                },
                'sequential_thinking': {
                    'enabled': False,
                    'endpoint': 'http://localhost:8082',
                    'timeout': 60,
                    'fallback_enabled': True
                },
                'supabase': {
                    'enabled': False,
                    'endpoint': 'http://localhost:8083',
                    'timeout': 30,
                    'fallback_enabled': True
                }
            },
            'mcp_global': {
                'max_connections': 50,
                'connection_timeout': 10,
                'rate_limit_enabled': True,
                'cache_enabled': True,
                'fallback_on_error': True
            },
            'environment': {
                'mode': 'development'
            }
        }
    
    def get_server_config(self, server_type: str) -> Dict[str, Any]:
        """Get configuration for a specific MCP server"""
        servers = self.config.get('mcp_servers', {})
        return servers.get(server_type, {})
    
    def is_server_enabled(self, server_type: str) -> bool:
        """Check if an MCP server is enabled"""
        server_config = self.get_server_config(server_type)
        return server_config.get('enabled', False)
    
    def get_server_endpoint(self, server_type: str) -> Optional[str]:
        """Get endpoint URL for an MCP server"""
        server_config = self.get_server_config(server_type)
        return server_config.get('endpoint')
    
    def get_server_timeout(self, server_type: str) -> int:
        """Get timeout for an MCP server"""
        server_config = self.get_server_config(server_type)
        return server_config.get('timeout', 30)
    
    def is_fallback_enabled(self, server_type: str) -> bool:
        """Check if fallback is enabled for an MCP server"""
        server_config = self.get_server_config(server_type)
        return server_config.get('fallback_enabled', True)
    
    def get_global_config(self) -> Dict[str, Any]:
        """Get global MCP configuration"""
        return self.config.get('mcp_global', {})
    
    def is_production(self) -> bool:
        """Check if running in production mode"""
        env = self.config.get('environment', {})
        return env.get('mode', 'development') == 'production'
    
    def get_auth_type(self, server_type: str) -> str:
        """Get authentication type for MCP server"""
        server_config = self.get_server_config(server_type)
        return server_config.get('auth_type', 'bearer')
    
    def get_api_key_env_var(self, server_type: str) -> str:
        """Get environment variable name for API key"""
        return f"{server_type.upper().replace('-', '_')}_MCP_API_KEY"
    
    def get_api_key(self, server_type: str) -> Optional[str]:
        """Get API key for MCP server from environment"""
        env_var = self.get_api_key_env_var(server_type)
        return os.getenv(env_var)
    
    def validate_config(self) -> bool:
        """Validate MCP configuration"""
        try:
            # Check required sections
            if 'mcp_servers' not in self.config:
                logger.error("Missing 'mcp_servers' section in config")
                return False
            
            # Validate each server
            for server_type, server_config in self.config.get('mcp_servers', {}).items():
                if server_config.get('enabled', False):
                    if not server_config.get('endpoint'):
                        logger.warning(f"MCP server '{server_type}' enabled but no endpoint configured")
                    
                    # Check API key if in production
                    if self.is_production():
                        api_key = self.get_api_key(server_type)
                        if not api_key:
                            logger.warning(f"No API key found for '{server_type}' (env var: {self.get_api_key_env_var(server_type)})")
            
            logger.info("MCP configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"MCP configuration validation failed: {e}")
            return False
    
    def get_circuit_breaker_config(self) -> Dict[str, Any]:
        """Get circuit breaker configuration"""
        return self.config.get('circuit_breaker', {
            'failure_threshold': 5,
            'success_threshold': 2,
            'timeout': 30
        })
    
    def reload_config(self):
        """Reload configuration from file"""
        self.config = self._load_config()
        logger.info("MCP configuration reloaded")


# Global instance
_mcp_config: Optional[MCPConfig] = None


def get_mcp_config() -> MCPConfig:
    """Get global MCP configuration instance"""
    global _mcp_config
    
    if _mcp_config is None:
        _mcp_config = MCPConfig()
    
    return _mcp_config


def reload_mcp_config():
    """Reload MCP configuration"""
    global _mcp_config
    _mcp_config = None
    return get_mcp_config()
