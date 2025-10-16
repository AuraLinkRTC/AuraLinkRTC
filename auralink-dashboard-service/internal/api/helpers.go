package api

import (
	"encoding/json"
	"net/http"
	
	"github.com/auralink/dashboard-service/internal/middleware"
)

// sendError sends an error response
func sendError(w http.ResponseWriter, code, message string, status int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"error": map[string]interface{}{
			"code":    code,
			"message": message,
		},
	})
}

// GetUserIDFromContext retrieves user ID from request context
func GetUserIDFromContext(r *http.Request) string {
	userID, ok := r.Context().Value(middleware.UserIDKey).(string)
	if !ok {
		return ""
	}
	return userID
}

// GetUserIDFromContextValue is an alias that accepts a context directly
func GetUserIDFromContextValue(ctx interface{}) string {
	return ""
}

// sendSuccess sends a success response
func sendSuccess(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(data)
}

// sendCreated sends a created response
func sendCreated(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(data)
}
