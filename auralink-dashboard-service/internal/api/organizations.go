package api

import (
	"encoding/json"
	"net/http"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"github.com/auralink/dashboard-service/internal/middleware"
)

// CreateOrganization creates a new organization
func CreateOrganization(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value(middleware.UserIDKey).(string)

	var req struct {
		Name string `json:"name"`
		Slug string `json:"slug"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, "VALIDATION_ERROR", "Invalid request body", http.StatusBadRequest)
		return
	}

	if req.Name == "" || req.Slug == "" {
		sendError(w, "VALIDATION_ERROR", "Name and slug are required", http.StatusBadRequest)
		return
	}

	// TODO: Insert into database
	
	orgID := uuid.New().String()

	response := map[string]interface{}{
		"organization_id": orgID,
		"name":            req.Name,
		"slug":            req.Slug,
		"owner_id":        userID,
		"plan_type":       "free",
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(response)
}

// GetOrganization retrieves organization details
func GetOrganization(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	orgID := vars["org_id"]

	// TODO: Query database
	
	org := map[string]interface{}{
		"organization_id": orgID,
		"name":            "Example Org",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(org)
}

// UpdateOrganization updates organization details
func UpdateOrganization(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	orgID := vars["org_id"]

	var updateData map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&updateData); err != nil {
		sendError(w, "VALIDATION_ERROR", "Invalid request body", http.StatusBadRequest)
		return
	}

	// TODO: Update in database
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"organization_id": orgID,
		"updated":         true,
	})
}
