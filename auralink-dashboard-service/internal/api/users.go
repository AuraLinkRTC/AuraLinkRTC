package api

import (
	"encoding/json"
	"net/http"

	"github.com/auralink/dashboard-service/internal/middleware"
)

// GetCurrentUser retrieves the current authenticated user
func GetCurrentUser(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value(middleware.UserIDKey).(string)
	email := r.Context().Value(middleware.EmailKey).(string)
	role := r.Context().Value(middleware.RoleKey).(string)

	// TODO: Fetch full user details from database
	
	user := map[string]interface{}{
		"user_id": userID,
		"email":   email,
		"role":    role,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(user)
}

// UpdateCurrentUser updates the current user's information
func UpdateCurrentUser(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value(middleware.UserIDKey).(string)

	var updateData map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&updateData); err != nil {
		sendError(w, "VALIDATION_ERROR", "Invalid request body", http.StatusBadRequest)
		return
	}

	// TODO: Update user in database
	
	response := map[string]interface{}{
		"user_id": userID,
		"updated": true,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}
