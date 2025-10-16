// Package services provides enterprise service implementations
package services

import (
	"context"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"time"

	"github.com/casbin/casbin/v2"
	"github.com/crewjam/saml"
	"github.com/crewjam/saml/samlsp"
	"github.com/google/uuid"
	"github.com/stripe/stripe-go/v76"
	"github.com/stripe/stripe-go/v76/customer"
	"github.com/stripe/stripe-go/v76/subscription"
	"golang.org/x/crypto/bcrypt"
	"golang.org/x/oauth2"
)

// EnterpriseService handles all enterprise features
type EnterpriseService struct {
	db           *sql.DB
	enforcer     *casbin.Enforcer
	samlSPs      map[string]*samlsp.Middleware
	oauthConfigs map[string]*oauth2.Config
	stripeKey    string
}

// NewEnterpriseService creates a new enterprise service
func NewEnterpriseService(db *sql.DB, enforcer *casbin.Enforcer, stripeKey string) *EnterpriseService {
	stripe.Key = stripeKey
	
	return &EnterpriseService{
		db:           db,
		enforcer:     enforcer,
		samlSPs:      make(map[string]*samlsp.Middleware),
		oauthConfigs: make(map[string]*oauth2.Config),
		stripeKey:    stripeKey,
	}
}

// SSO Management

// CreateSAMLServiceProvider creates a SAML service provider for an organization
func (s *EnterpriseService) CreateSAMLServiceProvider(configID, entityID, ssoURL, cert, acsURL string) (*samlsp.Middleware, error) {
	keyPair, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		return nil, fmt.Errorf("failed to generate key pair: %w", err)
	}

	rootURL, err := url.Parse(acsURL)
	if err != nil {
		return nil, fmt.Errorf("invalid ACS URL: %w", err)
	}

	// Parse IdP certificate
	block, _ := pem.Decode([]byte(cert))
	if block == nil {
		return nil, fmt.Errorf("failed to parse certificate PEM")
	}

	idpCert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("failed to parse certificate: %w", err)
	}

	idpMetadataURL, _ := url.Parse(entityID)
	
	samlSP, err := samlsp.New(samlsp.Options{
		URL:            *rootURL,
		Key:            keyPair,
		Certificate:    nil, // Will be auto-generated
		IDPMetadata: &saml.EntityDescriptor{
			EntityID: entityID,
			IDPSSODescriptors: []saml.IDPSSODescriptor{
				{
					SSODescriptor: saml.SSODescriptor{
						ProtocolSupportEnumeration: "urn:oasis:names:tc:SAML:2.0:protocol",
					},
					SingleSignOnServices: []saml.Endpoint{
						{
							Binding:  "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
							Location: ssoURL,
						},
					},
				},
			},
		},
		IDPMetadataURL: idpMetadataURL,
	})

	if err != nil {
		return nil, fmt.Errorf("failed to create SAML SP: %w", err)
	}

	s.samlSPs[configID] = samlSP
	return samlSP, nil
}

// GetSAMLServiceProvider retrieves a SAML service provider
func (s *EnterpriseService) GetSAMLServiceProvider(configID string) (*samlsp.Middleware, error) {
	sp, exists := s.samlSPs[configID]
	if !exists {
		return nil, fmt.Errorf("SAML SP not found for config %s", configID)
	}
	return sp, nil
}

// CreateOAuthConfig creates an OAuth2 configuration
func (s *EnterpriseService) CreateOAuthConfig(configID, clientID, clientSecret, authURL, tokenURL, redirectURL string, scopes []string) *oauth2.Config {
	config := &oauth2.Config{
		ClientID:     clientID,
		ClientSecret: clientSecret,
		Endpoint: oauth2.Endpoint{
			AuthURL:  authURL,
			TokenURL: tokenURL,
		},
		RedirectURL: redirectURL,
		Scopes:      scopes,
	}

	s.oauthConfigs[configID] = config
	return config
}

// GetOAuthConfig retrieves an OAuth2 configuration
func (s *EnterpriseService) GetOAuthConfig(configID string) (*oauth2.Config, error) {
	config, exists := s.oauthConfigs[configID]
	if !exists {
		return nil, fmt.Errorf("OAuth config not found for %s", configID)
	}
	return config, nil
}

// RBAC Management

// CheckPermission checks if a user has permission to perform an action
func (s *EnterpriseService) CheckPermission(userID, resource, action string) (bool, error) {
	if s.enforcer == nil {
		return false, fmt.Errorf("RBAC enforcer not initialized")
	}

	allowed, err := s.enforcer.Enforce(userID, resource, action)
	if err != nil {
		return false, fmt.Errorf("permission check failed: %w", err)
	}

	return allowed, nil
}

// AddRoleForUser adds a role to a user
func (s *EnterpriseService) AddRoleForUser(userID, roleID string) error {
	if s.enforcer == nil {
		return fmt.Errorf("RBAC enforcer not initialized")
	}

	_, err := s.enforcer.AddRoleForUser(userID, roleID)
	if err != nil {
		return fmt.Errorf("failed to add role: %w", err)
	}

	return s.enforcer.SavePolicy()
}

// RemoveRoleForUser removes a role from a user
func (s *EnterpriseService) RemoveRoleForUser(userID, roleID string) error {
	if s.enforcer == nil {
		return fmt.Errorf("RBAC enforcer not initialized")
	}

	_, err := s.enforcer.DeleteRoleForUser(userID, roleID)
	if err != nil {
		return fmt.Errorf("failed to remove role: %w", err)
	}

	return s.enforcer.SavePolicy()
}

// GetRolesForUser retrieves all roles for a user
func (s *EnterpriseService) GetRolesForUser(userID string) ([]string, error) {
	if s.enforcer == nil {
		return nil, fmt.Errorf("RBAC enforcer not initialized")
	}

	roles, err := s.enforcer.GetRolesForUser(userID)
	if err != nil {
		return nil, fmt.Errorf("failed to get roles: %w", err)
	}

	return roles, nil
}

// AddPolicy adds a policy rule
func (s *EnterpriseService) AddPolicy(role, resource, action string) error {
	if s.enforcer == nil {
		return fmt.Errorf("RBAC enforcer not initialized")
	}

	_, err := s.enforcer.AddPolicy(role, resource, action)
	if err != nil {
		return fmt.Errorf("failed to add policy: %w", err)
	}

	return s.enforcer.SavePolicy()
}

// Audit Logging

// CreateAuditLog creates a new audit log entry
func (s *EnterpriseService) CreateAuditLog(ctx context.Context, log AuditLog) error {
	query := `
		INSERT INTO audit_logs (
			organization_id, user_id, action, resource_type, resource_id,
			description, severity, ip_address, user_agent, request_method,
			request_path, request_body, response_status, old_values, new_values, metadata
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
	`

	requestBodyJSON, _ := json.Marshal(log.RequestBody)
	oldValuesJSON, _ := json.Marshal(log.OldValues)
	newValuesJSON, _ := json.Marshal(log.NewValues)
	metadataJSON, _ := json.Marshal(log.Metadata)

	_, err := s.db.ExecContext(ctx, query,
		log.OrganizationID, log.UserID, log.Action, log.ResourceType, log.ResourceID,
		log.Description, log.Severity, log.IPAddress, log.UserAgent, log.RequestMethod,
		log.RequestPath, requestBodyJSON, log.ResponseStatus, oldValuesJSON, newValuesJSON, metadataJSON,
	)

	return err
}

// Billing & Subscriptions

// CreateStripeCustomer creates a new Stripe customer
func (s *EnterpriseService) CreateStripeCustomer(email, name, orgID string) (*stripe.Customer, error) {
	params := &stripe.CustomerParams{
		Email: stripe.String(email),
		Name:  stripe.String(name),
		Metadata: map[string]string{
			"organization_id": orgID,
		},
	}

	return customer.New(params)
}

// CreateStripeSubscription creates a new Stripe subscription
func (s *EnterpriseService) CreateStripeSubscription(customerID, priceID string) (*stripe.Subscription, error) {
	params := &stripe.SubscriptionParams{
		Customer: stripe.String(customerID),
		Items: []*stripe.SubscriptionItemsParams{
			{Price: stripe.String(priceID)},
		},
	}

	return subscription.New(params)
}

// CancelStripeSubscription cancels a Stripe subscription
func (s *EnterpriseService) CancelStripeSubscription(subscriptionID string, cancelAtPeriodEnd bool) (*stripe.Subscription, error) {
	params := &stripe.SubscriptionParams{
		CancelAtPeriodEnd: stripe.Bool(cancelAtPeriodEnd),
	}

	return subscription.Update(subscriptionID, params)
}

// Encryption utilities

// EncryptSecret encrypts a secret using bcrypt
func EncryptSecret(secret string) (string, error) {
	hash, err := bcrypt.GenerateFromPassword([]byte(secret), bcrypt.DefaultCost)
	if err != nil {
		return "", err
	}
	return string(hash), nil
}

// GenerateSecureToken generates a cryptographically secure random token
func GenerateSecureToken() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return base64.URLEncoding.EncodeToString(b), nil
}

// Data types

type AuditLog struct {
	OrganizationID *string
	UserID         *string
	Action         string
	ResourceType   *string
	ResourceID     *string
	Description    string
	Severity       string
	IPAddress      *string
	UserAgent      *string
	RequestMethod  *string
	RequestPath    *string
	RequestBody    map[string]interface{}
	ResponseStatus *int
	OldValues      map[string]interface{}
	NewValues      map[string]interface{}
	Metadata       map[string]interface{}
}
