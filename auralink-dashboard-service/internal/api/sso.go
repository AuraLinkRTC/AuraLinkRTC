// AuraLink Dashboard Service - SSO Integration
// Package api provides SSO (SAML/OAuth) authentication endpoints
package api

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/auralink/dashboard-service/internal/database"
	"github.com/auralink/dashboard-service/internal/services"
	"github.com/gorilla/mux"
	"github.com/google/uuid"
	"golang.org/x/oauth2"
)

// SSOConfig represents SSO configuration
type SSOConfig struct {
	ConfigID              string                 `json:"config_id"`
	OrganizationID        string                 `json:"organization_id"`
	ProviderType          string                 `json:"provider_type"`
	ProviderName          string                 `json:"provider_name"`
	ConfigData            map[string]interface{} `json:"config_data"`
	SAMLEntityID          *string                `json:"saml_entity_id,omitempty"`
	SAMLSsoURL            *string                `json:"saml_sso_url,omitempty"`
	SAMLCertificate       *string                `json:"saml_certificate,omitempty"`
	ClientID              *string                `json:"client_id,omitempty"`
	ClientSecretEncrypted *string                `json:"client_secret_encrypted,omitempty"`
	AuthorizationEndpoint *string                `json:"authorization_endpoint,omitempty"`
	TokenEndpoint         *string                `json:"token_endpoint,omitempty"`
	UserinfoEndpoint      *string                `json:"userinfo_endpoint,omitempty"`
	IsActive              bool                   `json:"is_active"`
	AutoProvisionUsers    bool                   `json:"auto_provision_users"`
	DefaultRole           string                 `json:"default_role"`
	AttributeMapping      map[string]string      `json:"attribute_mapping"`
	CreatedAt             time.Time              `json:"created_at"`
	UpdatedAt             time.Time              `json:"updated_at"`
}

var enterpriseService *services.EnterpriseService

// InitEnterpriseService initializes the enterprise service
func InitEnterpriseService(svc *services.EnterpriseService) {
	enterpriseService = svc
}

// CreateSSOConfig creates a new SSO configuration for an organization
func CreateSSOConfig(w http.ResponseWriter, r *http.Request) {
	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}
	// Parse request
	var req struct {
		OrganizationID        string                 `json:"organization_id"`
		ProviderType          string                 `json:"provider_type"`
		ProviderName          string                 `json:"provider_name"`
		ConfigData            map[string]interface{} `json:"config_data"`
		SAMLEntityID          *string                `json:"saml_entity_id,omitempty"`
		SAMLSsoURL            *string                `json:"saml_sso_url,omitempty"`
		SAMLCertificate       *string                `json:"saml_certificate,omitempty"`
		ClientID              *string                `json:"client_id,omitempty"`
		ClientSecret          *string                `json:"client_secret,omitempty"`
		AuthorizationEndpoint *string                `json:"authorization_endpoint,omitempty"`
		TokenEndpoint         *string                `json:"token_endpoint,omitempty"`
		UserinfoEndpoint      *string                `json:"userinfo_endpoint,omitempty"`
		AutoProvisionUsers    *bool                  `json:"auto_provision_users,omitempty"`
		DefaultRole           string                 `json:"default_role"`
		AttributeMapping      map[string]string      `json:"attribute_mapping"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate provider type
	if req.ProviderType != "saml" && req.ProviderType != "oauth" && req.ProviderType != "oidc" {
		http.Error(w, "Invalid provider type. Must be 'saml', 'oauth', or 'oidc'", http.StatusBadRequest)
		return
	}

	// Encrypt client secret if provided
	var encryptedSecret *string
	if req.ClientSecret != nil {
		encrypted, err := services.EncryptSecret(*req.ClientSecret)
		if err != nil {
			http.Error(w, "Failed to encrypt client secret", http.StatusInternalServerError)
			return
		}
		encryptedSecret = &encrypted
	}

	configID := uuid.New().String()
	autoProvision := true
	if req.AutoProvisionUsers != nil {
		autoProvision = *req.AutoProvisionUsers
	}

	// Marshal JSON fields
	configDataJSON, _ := json.Marshal(req.ConfigData)
	attributeMappingJSON, _ := json.Marshal(req.AttributeMapping)

	// Insert into database
	query := `
		INSERT INTO sso_configs (
			config_id, organization_id, provider_type, provider_name, config_data,
			saml_entity_id, saml_sso_url, saml_certificate,
			client_id, client_secret_encrypted, authorization_endpoint, token_endpoint, userinfo_endpoint,
			is_active, auto_provision_users, default_role, attribute_mapping
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
		RETURNING created_at, updated_at
	`

	var createdAt, updatedAt time.Time
	err := db.QueryRowContext(r.Context(), query,
		configID, req.OrganizationID, req.ProviderType, req.ProviderName, configDataJSON,
		req.SAMLEntityID, req.SAMLSsoURL, req.SAMLCertificate,
		req.ClientID, encryptedSecret, req.AuthorizationEndpoint, req.TokenEndpoint, req.UserinfoEndpoint,
		true, autoProvision, req.DefaultRole, attributeMappingJSON,
	).Scan(&createdAt, &updatedAt)

	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to create SSO config: %v", err), http.StatusInternalServerError)
		return
	}

	// Initialize SAML SP if SAML provider
	if req.ProviderType == "saml" && req.SAMLEntityID != nil && req.SAMLSsoURL != nil && req.SAMLCertificate != nil {
		if enterpriseService != nil {
			_, err := enterpriseService.CreateSAMLServiceProvider(
				configID, *req.SAMLEntityID, *req.SAMLSsoURL, *req.SAMLCertificate,
				fmt.Sprintf("https://api.auralink.com/api/v1/auth/sso/saml/callback?config_id=%s", configID),
			)
			if err != nil {
				// Log but don't fail - can be initialized later
				fmt.Printf("Warning: Failed to initialize SAML SP: %v\n", err)
			}
		}
	}

	// Initialize OAuth config if OAuth/OIDC provider
	if (req.ProviderType == "oauth" || req.ProviderType == "oidc") && req.ClientID != nil && req.AuthorizationEndpoint != nil && req.TokenEndpoint != nil {
		if enterpriseService != nil && req.ClientSecret != nil {
			scopes := []string{"openid", "profile", "email"}
			if req.ProviderType == "oidc" {
				scopes = append(scopes, "openid")
			}
			enterpriseService.CreateOAuthConfig(
				configID, *req.ClientID, *req.ClientSecret,
				*req.AuthorizationEndpoint, *req.TokenEndpoint,
				fmt.Sprintf("https://api.auralink.com/api/v1/auth/sso/oauth/callback?config_id=%s", configID),
				scopes,
			)
		}
	}

	config := SSOConfig{
		ConfigID:              configID,
		OrganizationID:        req.OrganizationID,
		ProviderType:          req.ProviderType,
		ProviderName:          req.ProviderName,
		ConfigData:            req.ConfigData,
		SAMLEntityID:          req.SAMLEntityID,
		SAMLSsoURL:            req.SAMLSsoURL,
		SAMLCertificate:       req.SAMLCertificate,
		ClientID:              req.ClientID,
		ClientSecretEncrypted: encryptedSecret,
		AuthorizationEndpoint: req.AuthorizationEndpoint,
		TokenEndpoint:         req.TokenEndpoint,
		UserinfoEndpoint:      req.UserinfoEndpoint,
		IsActive:              true,
		AutoProvisionUsers:    autoProvision,
		DefaultRole:           req.DefaultRole,
		AttributeMapping:      req.AttributeMapping,
		CreatedAt:             createdAt,
		UpdatedAt:             updatedAt,
	}

	// Log audit event
	if enterpriseService != nil {
		auditLog := services.AuditLog{
			OrganizationID: &req.OrganizationID,
			Action:         "sso.config_create",
			ResourceType:   strPtr("sso_config"),
			ResourceID:     &configID,
			Description:    fmt.Sprintf("SSO configuration created for %s", req.ProviderType),
			Severity:       "info",
		}
		enterpriseService.CreateAuditLog(r.Context(), auditLog)
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(config)
}

// GetSSOConfigs retrieves all SSO configurations for an organization
func GetSSOConfigs(w http.ResponseWriter, r *http.Request) {
	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	orgID := r.URL.Query().Get("organization_id")
	if orgID == "" {
		http.Error(w, "organization_id is required", http.StatusBadRequest)
		return
	}

	query := `
		SELECT config_id, organization_id, provider_type, provider_name,
		       saml_entity_id, saml_sso_url, client_id, authorization_endpoint,
		       token_endpoint, userinfo_endpoint, is_active, auto_provision_users,
		       default_role, created_at, updated_at
		FROM sso_configs
		WHERE organization_id = $1 AND is_active = true
		ORDER BY created_at DESC
	`

	rows, err := db.QueryContext(r.Context(), query, orgID)
	if err != nil {
		http.Error(w, "Failed to query SSO configs", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	configs := []SSOConfig{}
	for rows.Next() {
		var config SSOConfig
		err := rows.Scan(
			&config.ConfigID, &config.OrganizationID, &config.ProviderType, &config.ProviderName,
			&config.SAMLEntityID, &config.SAMLSsoURL, &config.ClientID, &config.AuthorizationEndpoint,
			&config.TokenEndpoint, &config.UserinfoEndpoint, &config.IsActive, &config.AutoProvisionUsers,
			&config.DefaultRole, &config.CreatedAt, &config.UpdatedAt,
		)
		if err != nil {
			continue
		}
		configs = append(configs, config)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"configs": configs,
		"total":   len(configs),
	})
}

// GetSSOConfig retrieves a specific SSO configuration
func GetSSOConfig(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	configID := vars["config_id"]

	// TODO: Query database
	// Mock response
	config := SSOConfig{
		ConfigID:   configID,
		IsActive:   true,
		CreatedAt:  time.Now(),
		UpdatedAt:  time.Now(),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(config)
}

// UpdateSSOConfig updates an existing SSO configuration
func UpdateSSOConfig(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	configID := vars["config_id"]

	var req map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// TODO: Update database
	// Log audit event
	logAuditEvent(r, "", "sso.update", "sso_config", configID, "SSO configuration updated")

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"config_id": configID,
		"updated":   true,
		"timestamp": time.Now(),
	})
}

// DeleteSSOConfig deletes an SSO configuration
func DeleteSSOConfig(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	configID := vars["config_id"]

	// TODO: Delete from database
	// Log audit event
	logAuditEvent(r, "", "sso.delete", "sso_config", configID, "SSO configuration deleted")

	w.WriteHeader(http.StatusNoContent)
}

// InitiateSAMLLogin initiates SAML SSO login flow
func InitiateSAMLLogin(w http.ResponseWriter, r *http.Request) {
	configID := r.URL.Query().Get("config_id")
	if configID == "" {
		http.Error(w, "config_id is required", http.StatusBadRequest)
		return
	}

	if enterpriseService == nil {
		http.Error(w, "Enterprise service not initialized", http.StatusInternalServerError)
		return
	}

	// Get SAML service provider
	samlSP, err := enterpriseService.GetSAMLServiceProvider(configID)
	if err != nil {
		// Try to fetch from DB and initialize
		db := database.GetDB()
		if db != nil {
			var entityID, ssoURL, cert sql.NullString
			err := db.QueryRowContext(r.Context(),
				"SELECT saml_entity_id, saml_sso_url, saml_certificate FROM sso_configs WHERE config_id = $1",
				configID,
			).Scan(&entityID, &ssoURL, &cert)
			
			if err == nil && entityID.Valid && ssoURL.Valid && cert.Valid {
				samlSP, err = enterpriseService.CreateSAMLServiceProvider(
					configID, entityID.String, ssoURL.String, cert.String,
					fmt.Sprintf("https://api.auralink.com/api/v1/auth/sso/saml/callback?config_id=%s", configID),
				)
			}
		}
		
		if err != nil {
			http.Error(w, "SAML SP not found", http.StatusNotFound)
			return
		}
	}

	// Generate auth request URL
	authReqURL, err := samlSP.ServiceProvider.MakeAuthenticationRequest("")
	if err != nil {
		http.Error(w, "Failed to create SAML request", http.StatusInternalServerError)
		return
	}

	redirectURL := authReqURL.String()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"redirect_url": redirectURL,
		"config_id":    configID,
	})
}

// HandleSAMLCallback handles SAML SSO callback
func HandleSAMLCallback(w http.ResponseWriter, r *http.Request) {
	samlResponse := r.FormValue("SAMLResponse")
	relayState := r.FormValue("RelayState")

	if samlResponse == "" {
		http.Error(w, "SAMLResponse is required", http.StatusBadRequest)
		return
	}

	// TODO: Validate SAML response and create user session
	// Log audit event
	logAuditEvent(r, "", "sso.saml_callback", "session", "", "SAML SSO login completed")

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success":      true,
		"relay_state":  relayState,
		"access_token": generateMockToken(),
	})
}

// InitiateOAuthLogin initiates OAuth/OIDC login flow
func InitiateOAuthLogin(w http.ResponseWriter, r *http.Request) {
	configID := r.URL.Query().Get("config_id")
	if configID == "" {
		http.Error(w, "config_id is required", http.StatusBadRequest)
		return
	}

	if enterpriseService == nil {
		http.Error(w, "Enterprise service not initialized", http.StatusInternalServerError)
		return
	}

	// Get OAuth config
	oauthConfig, err := enterpriseService.GetOAuthConfig(configID)
	if err != nil {
		// Try to fetch from DB and initialize
		db := database.GetDB()
		if db != nil {
			var clientID, clientSecret, authEndpoint, tokenEndpoint sql.NullString
			err := db.QueryRowContext(r.Context(),
				`SELECT client_id, client_secret_encrypted, authorization_endpoint, token_endpoint 
				 FROM sso_configs WHERE config_id = $1`,
				configID,
			).Scan(&clientID, &clientSecret, &authEndpoint, &tokenEndpoint)
			
			if err == nil && clientID.Valid && authEndpoint.Valid && tokenEndpoint.Valid {
				secret := ""
				if clientSecret.Valid {
					secret = clientSecret.String
				}
				oauthConfig = enterpriseService.CreateOAuthConfig(
					configID, clientID.String, secret,
					authEndpoint.String, tokenEndpoint.String,
					fmt.Sprintf("https://api.auralink.com/api/v1/auth/sso/oauth/callback?config_id=%s", configID),
					[]string{"openid", "profile", "email"},
				)
			}
		}
		
		if err != nil {
			http.Error(w, "OAuth config not found", http.StatusNotFound)
			return
		}
	}

	// Generate state for CSRF protection
	state, err := services.GenerateSecureToken()
	if err != nil {
		http.Error(w, "Failed to generate state", http.StatusInternalServerError)
		return
	}

	// TODO: Store state in Redis/session for verification

	redirectURL := oauthConfig.AuthCodeURL(state, oauth2.AccessTypeOffline)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"redirect_url": redirectURL,
		"state":        state,
		"config_id":    configID,
	})
}

// HandleOAuthCallback handles OAuth/OIDC callback
func HandleOAuthCallback(w http.ResponseWriter, r *http.Request) {
	code := r.URL.Query().Get("code")
	state := r.URL.Query().Get("state")

	if code == "" || state == "" {
		http.Error(w, "code and state are required", http.StatusBadRequest)
		return
	}

	// TODO: Exchange code for token and create user session
	// Log audit event
	logAuditEvent(r, "", "sso.oauth_callback", "session", "", "OAuth SSO login completed")

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success":      true,
		"access_token": generateMockToken(),
	})
}

// Helper functions

func encryptSecret(secret string) (string, error) {
	// TODO: Implement proper encryption using AES-256-GCM
	// For now, just base64 encode (NOT SECURE - implement proper encryption)
	return base64.StdEncoding.EncodeToString([]byte(secret)), nil
}

func generateSecureToken() (string, error) {
	return services.GenerateSecureToken()
}

func generateMockToken() string {
	return "mock_jwt_token_" + uuid.New().String()
}

func strPtr(s string) *string {
	return &s
}
