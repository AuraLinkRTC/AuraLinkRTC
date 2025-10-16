"""
Error handling utilities for AuraLink Python services
"""

from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
import traceback


class ErrorCode(str, Enum):
    """Standardized error codes"""
    # Authentication & Authorization
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_TOKEN = "INVALID_TOKEN"
    EXPIRED_TOKEN = "EXPIRED_TOKEN"
    
    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_FIELD = "MISSING_FIELD"
    
    # Resources
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    CONFLICT = "CONFLICT"
    
    # Operations
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    
    # Database
    DATABASE_ERROR = "DATABASE_ERROR"
    DUPLICATE_KEY = "DUPLICATE_KEY"
    
    # External Services
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    SUPABASE_ERROR = "SUPABASE_ERROR"
    REDIS_ERROR = "REDIS_ERROR"


class AuraError(Exception):
    """Standardized error class for AuraLink services"""
    
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
        trace_id: Optional[str] = None,
        service: Optional[str] = None,
        include_stack: bool = False
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code or self._get_status_code(code)
        self.timestamp = datetime.utcnow()
        self.trace_id = trace_id
        self.service = service
        self.stack = traceback.format_exc() if include_stack else None
    
    @staticmethod
    def _get_status_code(code: ErrorCode) -> int:
        """Map error codes to HTTP status codes"""
        mapping = {
            ErrorCode.UNAUTHORIZED: 401,
            ErrorCode.FORBIDDEN: 403,
            ErrorCode.INVALID_TOKEN: 401,
            ErrorCode.EXPIRED_TOKEN: 401,
            ErrorCode.NOT_FOUND: 404,
            ErrorCode.VALIDATION_ERROR: 400,
            ErrorCode.INVALID_INPUT: 400,
            ErrorCode.MISSING_FIELD: 400,
            ErrorCode.ALREADY_EXISTS: 409,
            ErrorCode.CONFLICT: 409,
            ErrorCode.DUPLICATE_KEY: 409,
            ErrorCode.SERVICE_UNAVAILABLE: 503,
            ErrorCode.TIMEOUT: 504,
            ErrorCode.RATE_LIMITED: 429,
        }
        return mapping.get(code, 500)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary"""
        result = {
            "code": self.code.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }
        
        if self.details:
            result["details"] = self.details
        if self.trace_id:
            result["trace_id"] = self.trace_id
        if self.service:
            result["service"] = self.service
        if self.stack:
            result["stack"] = self.stack
            
        return result
    
    def with_details(self, key: str, value: Any) -> "AuraError":
        """Add additional details to the error"""
        self.details[key] = value
        return self
    
    def with_trace_id(self, trace_id: str) -> "AuraError":
        """Add trace ID for distributed tracing"""
        self.trace_id = trace_id
        return self
    
    def with_service(self, service: str) -> "AuraError":
        """Add service name"""
        self.service = service
        return self


# Convenience functions for common errors
def unauthorized(message: str = "Unauthorized") -> AuraError:
    """Create an unauthorized error"""
    return AuraError(ErrorCode.UNAUTHORIZED, message)


def forbidden(message: str = "Forbidden") -> AuraError:
    """Create a forbidden error"""
    return AuraError(ErrorCode.FORBIDDEN, message)


def not_found(resource: str) -> AuraError:
    """Create a not found error"""
    return AuraError(ErrorCode.NOT_FOUND, f"{resource} not found")


def validation_error(message: str) -> AuraError:
    """Create a validation error"""
    return AuraError(ErrorCode.VALIDATION_ERROR, message)


def internal_error(message: str = "Internal server error") -> AuraError:
    """Create an internal error"""
    return AuraError(ErrorCode.INTERNAL_ERROR, message, include_stack=True)


def service_unavailable(service: str) -> AuraError:
    """Create a service unavailable error"""
    return AuraError(
        ErrorCode.SERVICE_UNAVAILABLE,
        f"{service} is currently unavailable"
    )
