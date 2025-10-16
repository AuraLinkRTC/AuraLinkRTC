package api

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
)

// AuraID represents a universal identity
type AuraID struct {
	RegistryID         string                 `json:"registry_id"`
	UserID             string                 `json:"user_id"`
	AuraID             string                 `json:"aura_id"`
	IsVerified         bool                   `json:"is_verified"`
	VerificationMethod string                 `json:"verification_method,omitempty"`
	VerifiedAt         *time.Time             `json:"verified_at,omitempty"`
	PrivacyLevel       string                 `json:"privacy_level"`
	AllowDiscovery     bool                   `json:"allow_discovery"`
	AllowCrossAppCalls bool                   `json:"allow_cross_app_calls"`
	BlockUnknownCallers bool                  `json:"block_unknown_callers"`
	FederatedDomains   []string               `json:"federated_domains"`
	FederationEnabled  bool                   `json:"federation_enabled"`
	IsActive           bool                   `json:"is_active"`
	Suspended          bool                   `json:"suspended"`
	PublicMetadata     map[string]interface{} `json:"public_metadata"`
	CreatedAt          time.Time              `json:"created_at"`
	UpdatedAt          time.Time              `json:"updated_at"`
	LastUsedAt         *time.Time             `json:"last_used_at,omitempty"`
}

// CreateAuraIDRequest represents the request to create a new AuraID
type CreateAuraIDRequest struct {
	Username      string `json:"username"`
	PrivacyLevel  string `json:"privacy_level,omitempty"`
	FederationEnabled bool `json:"federation_enabled,omitempty"`
}

// UpdateAuraIDRequest represents the request to update AuraID settings
type UpdateAuraIDRequest struct {
	PrivacyLevel        *string  `json:"privacy_level,omitempty"`
	AllowDiscovery      *bool    `json:"allow_discovery,omitempty"`
	AllowCrossAppCalls  *bool    `json:"allow_cross_app_calls,omitempty"`
	BlockUnknownCallers *bool    `json:"block_unknown_callers,omitempty"`
	FederatedDomains    []string `json:"federated_domains,omitempty"`
	FederationEnabled   *bool    `json:"federation_enabled,omitempty"`
}

// VerifyAuraIDRequest represents verification request
type VerifyAuraIDRequest struct {
	VerificationMethod string `json:"verification_method"`
	VerificationCode   string `json:"verification_code"`
	PhoneNumber        string `json:"phone_number,omitempty"`
}

// AuraIDSearchResult represents search results
type AuraIDSearchResult struct {
	AuraID       string    `json:"aura_id"`
	DisplayName  string    `json:"display_name"`
	AvatarURL    string    `json:"avatar_url,omitempty"`
	IsVerified   bool      `json:"is_verified"`
	IsOnline     bool      `json:"is_online"`
	PrivacyLevel string    `json:"privacy_level"`
	LastUsedAt   *time.Time `json:"last_used_at,omitempty"`
}

var (
	// AuraID format: @username.aura
	auraIDRegex = regexp.MustCompile(`^@[a-zA-Z0-9_-]+\.aura$`)
	usernameRegex = regexp.MustCompile(`^[a-zA-Z0-9_-]{3,30}$`)
)

// CreateAuraID creates a new universal AuraID for the user
func (h *Handler) CreateAuraID(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value("user_id").(string)

	var req CreateAuraIDRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate username format
	if !usernameRegex.MatchString(req.Username) {
		http.Error(w, "Invalid username format. Use 3-30 alphanumeric characters, underscores, or hyphens", http.StatusBadRequest)
		return
	}

	// Construct AuraID
	auraID := fmt.Sprintf("@%s.aura", strings.ToLower(req.Username))

	// Check if user already has an AuraID
	var existingID string
	err := h.DB.QueryRow(`
		SELECT aura_id FROM aura_id_registry WHERE user_id = $1
	`, userID).Scan(&existingID)

	if err != sql.ErrNoRows {
		if err == nil {
			http.Error(w, fmt.Sprintf("User already has AuraID: %s", existingID), http.StatusConflict)
			return
		}
		http.Error(w, "Database error", http.StatusInternalServerError)
		return
	}

	// Check if AuraID is available
	var available bool
	err = h.DB.QueryRow(`SELECT is_aura_id_available($1)`, auraID).Scan(&available)
	if err != nil {
		http.Error(w, "Database error checking availability", http.StatusInternalServerError)
		return
	}

	if !available {
		http.Error(w, "AuraID already taken", http.StatusConflict)
		return
	}

	// Set defaults
	privacyLevel := "public"
	if req.PrivacyLevel != "" {
		privacyLevel = req.PrivacyLevel
	}

	federationEnabled := true
	if !req.FederationEnabled {
		federationEnabled = false
	}

	// Create AuraID
	registryID := uuid.New().String()
	_, err = h.DB.Exec(`
		INSERT INTO aura_id_registry (
			registry_id, user_id, aura_id, privacy_level, federation_enabled,
			allow_discovery, allow_cross_app_calls, block_unknown_callers
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
	`, registryID, userID, auraID, privacyLevel, federationEnabled, true, true, false)

	if err != nil {
		http.Error(w, "Failed to create AuraID", http.StatusInternalServerError)
		return
	}

	// Also update the users table with the AuraID
	_, err = h.DB.Exec(`
		UPDATE users SET aura_id = $1, updated_at = NOW() WHERE user_id = $2
	`, auraID, userID)

	if err != nil {
		// Rollback AuraID creation
		h.DB.Exec(`DELETE FROM aura_id_registry WHERE registry_id = $1`, registryID)
		http.Error(w, "Failed to link AuraID to user", http.StatusInternalServerError)
		return
	}

	// Create default notification preferences
	_, err = h.DB.Exec(`
		INSERT INTO notification_preferences (
			aura_id, enable_smart_routing, ring_timeout_seconds
		) VALUES ($1, $2, $3)
	`, auraID, true, 30)

	// Log audit event
	h.logFederationAudit("auraid_created", "identity", userID, "", auraID, "", 
		fmt.Sprintf("Created AuraID: %s", auraID), map[string]interface{}{
			"username": req.Username,
			"privacy_level": privacyLevel,
		}, "success", "")

	// Fetch and return created AuraID
	auraIDData, err := h.getAuraIDByID(auraID)
	if err != nil {
		http.Error(w, "Failed to fetch created AuraID", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(auraIDData)
}

// GetMyAuraID retrieves the current user's AuraID
func (h *Handler) GetMyAuraID(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value("user_id").(string)

	var auraID string
	err := h.DB.QueryRow(`
		SELECT aura_id FROM aura_id_registry WHERE user_id = $1
	`, userID).Scan(&auraID)

	if err == sql.ErrNoRows {
		http.Error(w, "AuraID not found", http.StatusNotFound)
		return
	}

	if err != nil {
		http.Error(w, "Database error", http.StatusInternalServerError)
		return
	}

	auraIDData, err := h.getAuraIDByID(auraID)
	if err != nil {
		http.Error(w, "Failed to fetch AuraID details", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(auraIDData)
}

// UpdateAuraID updates AuraID settings
func (h *Handler) UpdateAuraID(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value("user_id").(string)

	var req UpdateAuraIDRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Build dynamic update query
	updates := []string{}
	args := []interface{}{userID}
	argCount := 2

	if req.PrivacyLevel != nil {
		updates = append(updates, fmt.Sprintf("privacy_level = $%d", argCount))
		args = append(args, *req.PrivacyLevel)
		argCount++
	}

	if req.AllowDiscovery != nil {
		updates = append(updates, fmt.Sprintf("allow_discovery = $%d", argCount))
		args = append(args, *req.AllowDiscovery)
		argCount++
	}

	if req.AllowCrossAppCalls != nil {
		updates = append(updates, fmt.Sprintf("allow_cross_app_calls = $%d", argCount))
		args = append(args, *req.AllowCrossAppCalls)
		argCount++
	}

	if req.BlockUnknownCallers != nil {
		updates = append(updates, fmt.Sprintf("block_unknown_callers = $%d", argCount))
		args = append(args, *req.BlockUnknownCallers)
		argCount++
	}

	if req.FederatedDomains != nil {
		updates = append(updates, fmt.Sprintf("federated_domains = $%d", argCount))
		args = append(args, req.FederatedDomains)
		argCount++
	}

	if req.FederationEnabled != nil {
		updates = append(updates, fmt.Sprintf("federation_enabled = $%d", argCount))
		args = append(args, *req.FederationEnabled)
		argCount++
	}

	if len(updates) == 0 {
		http.Error(w, "No fields to update", http.StatusBadRequest)
		return
	}

	query := fmt.Sprintf(`
		UPDATE aura_id_registry 
		SET %s, updated_at = NOW()
		WHERE user_id = $1
	`, strings.Join(updates, ", "))

	_, err := h.DB.Exec(query, args...)
	if err != nil {
		http.Error(w, "Failed to update AuraID", http.StatusInternalServerError)
		return
	}

	// Fetch and return updated AuraID
	var auraID string
	h.DB.QueryRow(`SELECT aura_id FROM aura_id_registry WHERE user_id = $1`, userID).Scan(&auraID)

	auraIDData, _ := h.getAuraIDByID(auraID)
	
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(auraIDData)
}

// VerifyAuraID initiates or completes AuraID verification
func (h *Handler) VerifyAuraID(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value("user_id").(string)

	var req VerifyAuraIDRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// In production, implement actual verification logic
	// For now, mark as verified if code matches (placeholder)
	if req.VerificationCode == "" {
		http.Error(w, "Verification code required", http.StatusBadRequest)
		return
	}

	// TODO: Implement actual verification logic with SMS/Email providers
	// For demo purposes, accept any non-empty code

	_, err := h.DB.Exec(`
		UPDATE aura_id_registry 
		SET is_verified = true, 
		    verification_method = $1,
		    verified_at = NOW(),
		    updated_at = NOW()
		WHERE user_id = $2
	`, req.VerificationMethod, userID)

	if err != nil {
		http.Error(w, "Failed to verify AuraID", http.StatusInternalServerError)
		return
	}

	// Log audit event
	h.logFederationAudit("auraid_verified", "identity", userID, "", "", "", 
		fmt.Sprintf("Verified AuraID via %s", req.VerificationMethod), 
		map[string]interface{}{"method": req.VerificationMethod}, "success", "")

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"verified": true,
		"message": "AuraID verified successfully",
	})
}

// CheckAuraIDAvailability checks if an AuraID is available
func (h *Handler) CheckAuraIDAvailability(w http.ResponseWriter, r *http.Request) {
	username := r.URL.Query().Get("username")
	if username == "" {
		http.Error(w, "Username parameter required", http.StatusBadRequest)
		return
	}

	if !usernameRegex.MatchString(username) {
		http.Error(w, "Invalid username format", http.StatusBadRequest)
		return
	}

	auraID := fmt.Sprintf("@%s.aura", strings.ToLower(username))

	var available bool
	err := h.DB.QueryRow(`SELECT is_aura_id_available($1)`, auraID).Scan(&available)
	if err != nil {
		http.Error(w, "Database error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"username":  username,
		"aura_id":   auraID,
		"available": available,
	})
}

// SearchAuraID searches for AuraIDs by username or display name
func (h *Handler) SearchAuraID(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("q")
	if query == "" {
		http.Error(w, "Query parameter 'q' required", http.StatusBadRequest)
		return
	}

	limit := 20 // Default limit

	rows, err := h.DB.Query(`
		SELECT 
			air.aura_id,
			u.display_name,
			u.avatar_url,
			air.is_verified,
			air.privacy_level,
			air.last_used_at,
			EXISTS(SELECT 1 FROM mesh_nodes mn WHERE mn.aura_id = air.aura_id AND mn.is_online = TRUE) as is_online
		FROM aura_id_registry air
		JOIN users u ON air.user_id = u.user_id
		WHERE 
			air.is_active = TRUE 
			AND air.suspended = FALSE
			AND air.privacy_level = 'public'
			AND air.allow_discovery = TRUE
			AND (
				air.aura_id ILIKE $1
				OR u.username ILIKE $1
				OR u.display_name ILIKE $1
			)
		ORDER BY 
			air.is_verified DESC,
			air.last_used_at DESC NULLS LAST
		LIMIT $2
	`, "%"+query+"%", limit)

	if err != nil {
		http.Error(w, "Search failed", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	results := []AuraIDSearchResult{}
	for rows.Next() {
		var result AuraIDSearchResult
		var avatarURL sql.NullString
		err := rows.Scan(
			&result.AuraID,
			&result.DisplayName,
			&avatarURL,
			&result.IsVerified,
			&result.PrivacyLevel,
			&result.LastUsedAt,
			&result.IsOnline,
		)
		if err != nil {
			continue
		}

		if avatarURL.Valid {
			result.AvatarURL = avatarURL.String
		}

		results = append(results, result)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"query":   query,
		"results": results,
		"count":   len(results),
	})
}

// ResolveAuraID resolves an AuraID to user information
func (h *Handler) ResolveAuraID(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	auraID := vars["aura_id"]

	if !auraIDRegex.MatchString(auraID) {
		http.Error(w, "Invalid AuraID format", http.StatusBadRequest)
		return
	}

	var userID, displayName, privacyLevel string
	var isVerified, isOnline bool

	err := h.DB.QueryRow(`
		SELECT * FROM resolve_aura_id($1)
	`, auraID).Scan(&userID, &displayName, &isVerified, &privacyLevel, &isOnline)

	if err == sql.ErrNoRows {
		http.Error(w, "AuraID not found or not accessible", http.StatusNotFound)
		return
	}

	if err != nil {
		http.Error(w, "Failed to resolve AuraID", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"aura_id":       auraID,
		"user_id":       userID,
		"display_name":  displayName,
		"is_verified":   isVerified,
		"privacy_level": privacyLevel,
		"is_online":     isOnline,
	})
}

// Helper function to get AuraID details
func (h *Handler) getAuraIDByID(auraID string) (*AuraID, error) {
	var aid AuraID
	var verifiedAt, lastUsedAt sql.NullTime
	var verificationMethod sql.NullString
	var publicMetadataJSON []byte

	err := h.DB.QueryRow(`
		SELECT 
			registry_id, user_id, aura_id, is_verified, verification_method,
			verified_at, privacy_level, allow_discovery, allow_cross_app_calls,
			block_unknown_callers, federated_domains, federation_enabled,
			is_active, suspended, public_metadata, created_at, updated_at, last_used_at
		FROM aura_id_registry
		WHERE aura_id = $1
	`, auraID).Scan(
		&aid.RegistryID, &aid.UserID, &aid.AuraID, &aid.IsVerified, &verificationMethod,
		&verifiedAt, &aid.PrivacyLevel, &aid.AllowDiscovery, &aid.AllowCrossAppCalls,
		&aid.BlockUnknownCallers, &aid.FederatedDomains, &aid.FederationEnabled,
		&aid.IsActive, &aid.Suspended, &publicMetadataJSON, &aid.CreatedAt, &aid.UpdatedAt, &lastUsedAt,
	)

	if err != nil {
		return nil, err
	}

	if verificationMethod.Valid {
		aid.VerificationMethod = verificationMethod.String
	}
	if verifiedAt.Valid {
		aid.VerifiedAt = &verifiedAt.Time
	}
	if lastUsedAt.Valid {
		aid.LastUsedAt = &lastUsedAt.Time
	}

	if len(publicMetadataJSON) > 0 {
		json.Unmarshal(publicMetadataJSON, &aid.PublicMetadata)
	}

	return &aid, nil
}

// Helper function to log federation audit events
func (h *Handler) logFederationAudit(eventType, category, actorAuraID, targetAuraID, actorID, targetID, description string, eventData map[string]interface{}, result, errorMsg string) {
	eventDataJSON, _ := json.Marshal(eventData)
	
	h.DB.Exec(`
		INSERT INTO federation_audit_log (
			event_type, event_category, actor_aura_id, target_aura_id, description, event_data, result, error_message
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
	`, eventType, category, actorAuraID, targetAuraID, description, eventDataJSON, result, errorMsg)
}
