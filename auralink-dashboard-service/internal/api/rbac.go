// AuraLink Dashboard Service - RBAC with Casbin
// Package api provides role-based access control endpoints
package api

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/auralink/dashboard-service/internal/database"
	"github.com/auralink/dashboard-service/internal/services"
	"github.com/gorilla/mux"
	"github.com/google/uuid"
)

// RBACRole represents a role in the RBAC system
type RBACRole struct {
	RoleID         string                   `json:"role_id"`
	OrganizationID *string                  `json:"organization_id,omitempty"`
	RoleName       string                   `json:"role_name"`
	RoleKey        string                   `json:"role_key"`
	Description    string                   `json:"description"`
	IsSystemRole   bool                     `json:"is_system_role"`
	IsDefault      bool                     `json:"is_default"`
	Permissions    []map[string]interface{} `json:"permissions"`
	CreatedAt      time.Time                `json:"created_at"`
	UpdatedAt      time.Time                `json:"updated_at"`
}

// UserRoleAssignment represents a user's role assignment
type UserRoleAssignment struct {
	AssignmentID   string     `json:"assignment_id"`
	UserID         string     `json:"user_id"`
	RoleID         string     `json:"role_id"`
	OrganizationID *string    `json:"organization_id,omitempty"`
	AssignedBy     *string    `json:"assigned_by,omitempty"`
	ExpiresAt      *time.Time `json:"expires_at,omitempty"`
	IsActive       bool       `json:"is_active"`
	AssignedAt     time.Time  `json:"assigned_at"`
}

// CreateRole creates a new RBAC role
func CreateRole(w http.ResponseWriter, r *http.Request) {
	var req struct {
		OrganizationID *string                  `json:"organization_id,omitempty"`
		RoleName       string                   `json:"role_name"`
		RoleKey        string                   `json:"role_key"`
		Description    string                   `json:"description"`
		Permissions    []map[string]interface{} `json:"permissions"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	roleID := uuid.New().String()

	// Marshal permissions JSON
	permissionsJSON, _ := json.Marshal(req.Permissions)

	// Insert into database
	query := `
		INSERT INTO rbac_roles (
			role_id, organization_id, role_name, role_key, description,
			is_system_role, is_default, permissions
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		RETURNING created_at, updated_at
	`

	var createdAt, updatedAt time.Time
	err := db.QueryRowContext(r.Context(), query,
		roleID, req.OrganizationID, req.RoleName, req.RoleKey, req.Description,
		false, false, permissionsJSON,
	).Scan(&createdAt, &updatedAt)

	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to create role: %v", err), http.StatusInternalServerError)
		return
	}

	// Add policies to Casbin
	if enterpriseService != nil {
		for _, perm := range req.Permissions {
			if resource, ok := perm["resource"].(string); ok {
				if action, ok := perm["action"].(string); ok {
					enterpriseService.AddPolicy(roleID, resource, action)
				}
			}
		}
	}

	role := RBACRole{
		RoleID:         roleID,
		OrganizationID: req.OrganizationID,
		RoleName:       req.RoleName,
		RoleKey:        req.RoleKey,
		Description:    req.Description,
		IsSystemRole:   false,
		IsDefault:      false,
		Permissions:    req.Permissions,
		CreatedAt:      createdAt,
		UpdatedAt:      updatedAt,
	}

	// Log audit event
	if enterpriseService != nil {
		orgID := ""
		if req.OrganizationID != nil {
			orgID = *req.OrganizationID
		}
		auditLog := services.AuditLog{
			OrganizationID: &orgID,
			Action:         "rbac.role_create",
			ResourceType:   strPtr("role"),
			ResourceID:     &roleID,
			Description:    fmt.Sprintf("RBAC role created: %s", req.RoleName),
			Severity:       "info",
		}
		enterpriseService.CreateAuditLog(r.Context(), auditLog)
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(role)
}

// ListRoles lists all roles for an organization
func ListRoles(w http.ResponseWriter, r *http.Request) {
	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	orgID := r.URL.Query().Get("organization_id")
	includeSystem := r.URL.Query().Get("include_system") == "true"

	query := `
		SELECT role_id, organization_id, role_name, role_key, description,
		       is_system_role, is_default, permissions, created_at, updated_at
		FROM rbac_roles
		WHERE ($1 = '' OR organization_id = $1::uuid OR organization_id IS NULL)
		  AND ($2 = true OR is_system_role = false)
		ORDER BY is_system_role DESC, created_at DESC
	`

	rows, err := db.QueryContext(r.Context(), query, orgID, includeSystem)
	if err != nil {
		http.Error(w, "Failed to query roles", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	roles := []RBACRole{}
	for rows.Next() {
		var role RBACRole
		var permissionsJSON []byte
		var orgIDPtr *string
		err := rows.Scan(
			&role.RoleID, &orgIDPtr, &role.RoleName, &role.RoleKey, &role.Description,
			&role.IsSystemRole, &role.IsDefault, &permissionsJSON, &role.CreatedAt, &role.UpdatedAt,
		)
		if err != nil {
			continue
		}
		if orgIDPtr != nil {
			role.OrganizationID = orgIDPtr
		}
		json.Unmarshal(permissionsJSON, &role.Permissions)
		roles = append(roles, role)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"roles":          roles,
		"total":          len(roles),
		"include_system": includeSystem,
	})
}

// GetRole retrieves a specific role
func GetRole(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	roleID := vars["role_id"]

	// TODO: Query database
	role := RBACRole{
		RoleID:    roleID,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(role)
}

// UpdateRole updates a role's configuration
func UpdateRole(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	roleID := vars["role_id"]

	var req struct {
		RoleName    *string                  `json:"role_name,omitempty"`
		Description *string                  `json:"description,omitempty"`
		Permissions []map[string]interface{} `json:"permissions,omitempty"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	// Build update query dynamically
	setClauses := []string{}
	args := []interface{}{roleID}
	argCount := 2

	if req.RoleName != nil {
		setClauses = append(setClauses, fmt.Sprintf("role_name = $%d", argCount))
		args = append(args, *req.RoleName)
		argCount++
	}
	if req.Description != nil {
		setClauses = append(setClauses, fmt.Sprintf("description = $%d", argCount))
		args = append(args, *req.Description)
		argCount++
	}
	if req.Permissions != nil {
		permissionsJSON, _ := json.Marshal(req.Permissions)
		setClauses = append(setClauses, fmt.Sprintf("permissions = $%d", argCount))
		args = append(args, permissionsJSON)
		argCount++
	}

	if len(setClauses) == 0 {
		http.Error(w, "No fields to update", http.StatusBadRequest)
		return
	}

	query := fmt.Sprintf(
		"UPDATE rbac_roles SET %s, updated_at = NOW() WHERE role_id = $1",
		"role_name = COALESCE($2, role_name), description = COALESCE($3, description)",
	)

	_, err := db.ExecContext(r.Context(), query, args...)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to update role: %v", err), http.StatusInternalServerError)
		return
	}

	// Log audit event
	if enterpriseService != nil {
		auditLog := services.AuditLog{
			Action:       "rbac.role_update",
			ResourceType: strPtr("role"),
			ResourceID:   &roleID,
			Description:  "RBAC role updated",
			Severity:     "info",
		}
		enterpriseService.CreateAuditLog(r.Context(), auditLog)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"role_id":   roleID,
		"updated":   true,
		"timestamp": time.Now(),
	})
}

// DeleteRole deletes a role
func DeleteRole(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	roleID := vars["role_id"]

	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	// Delete role
	_, err := db.ExecContext(r.Context(), "DELETE FROM rbac_roles WHERE role_id = $1 AND is_system_role = false", roleID)
	if err != nil {
		http.Error(w, "Failed to delete role", http.StatusInternalServerError)
		return
	}

	// Log audit event
	if enterpriseService != nil {
		auditLog := services.AuditLog{
			Action:       "rbac.role_delete",
			ResourceType: strPtr("role"),
			ResourceID:   &roleID,
			Description:  "RBAC role deleted",
			Severity:     "info",
		}
		enterpriseService.CreateAuditLog(r.Context(), auditLog)
	}

	w.WriteHeader(http.StatusNoContent)
}

// AssignRoleToUser assigns a role to a user
func AssignRoleToUser(w http.ResponseWriter, r *http.Request) {
	var req struct {
		UserID         string     `json:"user_id"`
		RoleID         string     `json:"role_id"`
		OrganizationID *string    `json:"organization_id,omitempty"`
		ExpiresAt      *time.Time `json:"expires_at,omitempty"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	assignmentID := uuid.New().String()

	// Insert into database
	query := `
		INSERT INTO user_role_assignments (
			assignment_id, user_id, role_id, organization_id, expires_at, is_active
		) VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING assigned_at
	`

	var assignedAt time.Time
	err := db.QueryRowContext(r.Context(), query,
		assignmentID, req.UserID, req.RoleID, req.OrganizationID, req.ExpiresAt, true,
	).Scan(&assignedAt)

	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to assign role: %v", err), http.StatusInternalServerError)
		return
	}

	// Add role to user in Casbin
	if enterpriseService != nil {
		enterpriseService.AddRoleForUser(req.UserID, req.RoleID)
	}

	assignment := UserRoleAssignment{
		AssignmentID:   assignmentID,
		UserID:         req.UserID,
		RoleID:         req.RoleID,
		OrganizationID: req.OrganizationID,
		ExpiresAt:      req.ExpiresAt,
		IsActive:       true,
		AssignedAt:     assignedAt,
	}

	// Log audit event
	if enterpriseService != nil {
		orgID := ""
		if req.OrganizationID != nil {
			orgID = *req.OrganizationID
		}
		auditLog := services.AuditLog{
			OrganizationID: &orgID,
			Action:         "rbac.role_assign",
			ResourceType:   strPtr("user_role"),
			ResourceID:     &assignmentID,
			Description:    fmt.Sprintf("Role assigned to user %s", req.UserID),
			Severity:       "info",
		}
		enterpriseService.CreateAuditLog(r.Context(), auditLog)
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(assignment)
}

// GetUserRoles retrieves all roles assigned to a user
func GetUserRoles(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	userID := vars["user_id"]

	// TODO: Query database
	assignments := []UserRoleAssignment{}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"user_id":     userID,
		"assignments": assignments,
		"total":       len(assignments),
	})
}

// RevokeUserRole revokes a role assignment
func RevokeUserRole(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	assignmentID := vars["assignment_id"]

	// TODO: Delete from database and update Casbin policies
	// Log audit event
	logAuditEvent(r, "", "rbac.role_revoke", "user_role", assignmentID, "Role assignment revoked")

	w.WriteHeader(http.StatusNoContent)
}

// CheckPermission checks if a user has a specific permission
func CheckPermission(w http.ResponseWriter, r *http.Request) {
	var req struct {
		UserID         string  `json:"user_id"`
		Resource       string  `json:"resource"`
		Action         string  `json:"action"`
		OrganizationID *string `json:"organization_id,omitempty"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Check permission using Casbin
	allowed := false
	if enterpriseService != nil {
		allowedResult, err := enterpriseService.CheckPermission(req.UserID, req.Resource, req.Action)
		if err == nil {
			allowed = allowedResult
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"user_id":  req.UserID,
		"resource": req.Resource,
		"action":   req.Action,
		"allowed":  allowed,
	})
}

// GetUserPermissions retrieves all permissions for a user
func GetUserPermissions(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	userID := vars["user_id"]
	orgID := r.URL.Query().Get("organization_id")

	// TODO: Query database and Casbin policies
	permissions := []map[string]interface{}{}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"user_id":         userID,
		"organization_id": orgID,
		"permissions":     permissions,
		"total":           len(permissions),
	})
}
