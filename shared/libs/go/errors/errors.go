// Package errors provides standardized error handling for AuraLink services
package errors

import (
	"encoding/json"
	"fmt"
	"net/http"
	"runtime"
	"time"
)

// ErrorCode represents standardized error codes across services
type ErrorCode string

const (
	// Authentication & Authorization
	ErrUnauthorized       ErrorCode = "UNAUTHORIZED"
	ErrForbidden          ErrorCode = "FORBIDDEN"
	ErrInvalidToken       ErrorCode = "INVALID_TOKEN"
	ErrExpiredToken       ErrorCode = "EXPIRED_TOKEN"
	
	// Validation
	ErrValidation         ErrorCode = "VALIDATION_ERROR"
	ErrInvalidInput       ErrorCode = "INVALID_INPUT"
	ErrMissingField       ErrorCode = "MISSING_FIELD"
	
	// Resources
	ErrNotFound           ErrorCode = "NOT_FOUND"
	ErrAlreadyExists      ErrorCode = "ALREADY_EXISTS"
	ErrConflict           ErrorCode = "CONFLICT"
	
	// Operations
	ErrInternal           ErrorCode = "INTERNAL_ERROR"
	ErrServiceUnavailable ErrorCode = "SERVICE_UNAVAILABLE"
	ErrTimeout            ErrorCode = "TIMEOUT"
	ErrRateLimited        ErrorCode = "RATE_LIMITED"
	
	// Database
	ErrDatabase           ErrorCode = "DATABASE_ERROR"
	ErrDuplicateKey       ErrorCode = "DUPLICATE_KEY"
	
	// External Services
	ErrExternalService    ErrorCode = "EXTERNAL_SERVICE_ERROR"
	ErrSupabaseError      ErrorCode = "SUPABASE_ERROR"
	ErrRedisError         ErrorCode = "REDIS_ERROR"
)

// AuraError represents a standardized error structure
type AuraError struct {
	Code       ErrorCode              `json:"code"`
	Message    string                 `json:"message"`
	Details    map[string]interface{} `json:"details,omitempty"`
	StatusCode int                    `json:"-"`
	Timestamp  time.Time              `json:"timestamp"`
	TraceID    string                 `json:"trace_id,omitempty"`
	Service    string                 `json:"service,omitempty"`
	Stack      string                 `json:"stack,omitempty"`
	err        error                  // Original error
}

// Error implements the error interface
func (e *AuraError) Error() string {
	if e.err != nil {
		return fmt.Sprintf("[%s] %s: %v", e.Code, e.Message, e.err)
	}
	return fmt.Sprintf("[%s] %s", e.Code, e.Message)
}

// Unwrap returns the original error
func (e *AuraError) Unwrap() error {
	return e.err
}

// WithDetails adds additional context to the error
func (e *AuraError) WithDetails(key string, value interface{}) *AuraError {
	if e.Details == nil {
		e.Details = make(map[string]interface{})
	}
	e.Details[key] = value
	return e
}

// WithTraceID adds a trace ID for distributed tracing
func (e *AuraError) WithTraceID(traceID string) *AuraError {
	e.TraceID = traceID
	return e
}

// WithService adds the service name
func (e *AuraError) WithService(service string) *AuraError {
	e.Service = service
	return e
}

// New creates a new AuraError
func New(code ErrorCode, message string) *AuraError {
	return &AuraError{
		Code:       code,
		Message:    message,
		StatusCode: getStatusCode(code),
		Timestamp:  time.Now(),
	}
}

// Wrap wraps an existing error with AuraError context
func Wrap(err error, code ErrorCode, message string) *AuraError {
	if err == nil {
		return nil
	}
	
	// If already an AuraError, just return it
	if auraErr, ok := err.(*AuraError); ok {
		return auraErr
	}
	
	return &AuraError{
		Code:       code,
		Message:    message,
		StatusCode: getStatusCode(code),
		Timestamp:  time.Now(),
		err:        err,
	}
}

// WrapWithStack wraps an error and captures the stack trace
func WrapWithStack(err error, code ErrorCode, message string) *AuraError {
	auraErr := Wrap(err, code, message)
	if auraErr != nil {
		auraErr.Stack = captureStack(3)
	}
	return auraErr
}

// getStatusCode maps error codes to HTTP status codes
func getStatusCode(code ErrorCode) int {
	switch code {
	case ErrUnauthorized, ErrInvalidToken, ErrExpiredToken:
		return http.StatusUnauthorized
	case ErrForbidden:
		return http.StatusForbidden
	case ErrNotFound:
		return http.StatusNotFound
	case ErrValidation, ErrInvalidInput, ErrMissingField:
		return http.StatusBadRequest
	case ErrAlreadyExists, ErrConflict, ErrDuplicateKey:
		return http.StatusConflict
	case ErrServiceUnavailable:
		return http.StatusServiceUnavailable
	case ErrTimeout:
		return http.StatusGatewayTimeout
	case ErrRateLimited:
		return http.StatusTooManyRequests
	default:
		return http.StatusInternalServerError
	}
}

// captureStack captures the current stack trace
func captureStack(skip int) string {
	buf := make([]byte, 1024)
	for {
		n := runtime.Stack(buf, false)
		if n < len(buf) {
			return string(buf[:n])
		}
		buf = make([]byte, 2*len(buf))
	}
}

// ToJSON converts the error to JSON
func (e *AuraError) ToJSON() []byte {
	data, _ := json.Marshal(e)
	return data
}

// HTTPResponse writes the error as an HTTP response
func (e *AuraError) HTTPResponse(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(e.StatusCode)
	w.Write(e.ToJSON())
}

// Common error constructors
func Unauthorized(message string) *AuraError {
	return New(ErrUnauthorized, message)
}

func Forbidden(message string) *AuraError {
	return New(ErrForbidden, message)
}

func NotFound(resource string) *AuraError {
	return New(ErrNotFound, fmt.Sprintf("%s not found", resource))
}

func ValidationError(message string) *AuraError {
	return New(ErrValidation, message)
}

func Internal(message string) *AuraError {
	return New(ErrInternal, message)
}

func ServiceUnavailable(service string) *AuraError {
	return New(ErrServiceUnavailable, fmt.Sprintf("%s is currently unavailable", service))
}
