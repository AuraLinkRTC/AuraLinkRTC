// AuraLink Dashboard Service
// Main API gateway for platform management
package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gorilla/mux"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/rs/cors"
	_ "github.com/lib/pq"

	"github.com/auralink/dashboard-service/internal/api"
	"github.com/auralink/dashboard-service/internal/config"
	"github.com/auralink/dashboard-service/internal/middleware"
	"github.com/auralink/dashboard-service/internal/services"
	"github.com/auralink/shared/database"
	"github.com/auralink/shared/livekit"
	"github.com/auralink/shared/storage"
)

func main() {
	// Load configuration
	cfg, err := config.Load("")
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	log.Printf("Starting AuraLink Dashboard Service")
	log.Printf("Environment: %s", cfg.Environment)
	log.Printf("Port: %d", cfg.Service.Port)

	// Initialize database
	if cfg.Database.URL != "" {
		db, err := sql.Open("postgres", cfg.Database.URL)
		if err != nil {
			log.Fatalf("Failed to connect to database: %v", err)
		}
		db.SetMaxOpenConns(cfg.Database.MaxConnections)
		db.SetMaxIdleConns(10)
		db.SetConnMaxLifetime(5 * time.Minute)
		
		if err := db.Ping(); err != nil {
			log.Fatalf("Failed to ping database: %v", err)
		}
		
		database.InitDB(db)
		log.Println("✓ Database initialized")
		
		// Initialize Casbin for RBAC
		if cfg.Enterprise.EnableRBAC {
			if err := database.InitCasbin(cfg.Database.URL, cfg.Enterprise.CasbinModelPath); err != nil {
				log.Printf("⚠ Failed to initialize Casbin: %v", err)
			} else {
				log.Println("✓ Casbin RBAC enforcer initialized")
			}
		}
		
		// Initialize Enterprise Service
		if cfg.Enterprise.EnableSSO || cfg.Enterprise.EnableRBAC || cfg.Enterprise.EnableBilling {
			enterpriseService := services.NewEnterpriseService(
				database.GetDB(),
				database.GetEnforcer(),
				cfg.Enterprise.StripeSecretKey,
			)
			api.InitEnterpriseService(enterpriseService)
			log.Println("✓ Enterprise services initialized")
			
			if cfg.Enterprise.EnableSSO {
				log.Println("  → SSO (SAML/OAuth) enabled")
			}
			if cfg.Enterprise.EnableRBAC {
				log.Println("  → RBAC with Casbin enabled")
			}
			if cfg.Enterprise.EnableBilling {
				log.Println("  → Stripe billing enabled")
			}
		}
		
		defer func() {
			if err := database.CloseDB(); err != nil {
				log.Printf("Error closing database: %v", err)
			}
		}()
	} else {
		log.Println("⚠ DATABASE_URL not set, database features disabled")
	}

	// Initialize LiveKit client
	if cfg.LiveKit.URL != "" && cfg.LiveKit.APIKey != "" && cfg.LiveKit.APISecret != "" {
		lkClient, err := livekit.NewClient(livekit.Config{
			URL:       cfg.LiveKit.URL,
			APIKey:    cfg.LiveKit.APIKey,
			APISecret: cfg.LiveKit.APISecret,
		})
		if err != nil {
			log.Printf("⚠ Failed to initialize LiveKit: %v", err)
		} else {
			livekit.InitClient(lkClient)
			log.Println("✓ LiveKit client initialized")
		}
	} else {
		log.Println("⚠ LiveKit config not set, WebRTC features disabled")
	}

	// Initialize storage client
	if cfg.Storage.URL != "" && cfg.Storage.ServiceRoleKey != "" {
		storageClient, err := storage.NewClient(storage.Config{
			URL:           cfg.Storage.URL,
			ServiceRoleKey: cfg.Storage.ServiceRoleKey,
			BucketName:    cfg.Storage.BucketName,
		})
		if err != nil {
			log.Printf("⚠ Failed to initialize storage: %v", err)
		} else {
			storage.InitClient(storageClient)
			log.Println("✓ Storage client initialized")
		}
	} else {
		log.Println("⚠ Storage config not set, file sharing features disabled")
	}

	// Create router
	router := mux.NewRouter()

	// Prometheus metrics endpoint
	router.Handle("/metrics", promhttp.Handler()).Methods("GET")

	// Health check endpoints
	router.HandleFunc("/health", api.HealthCheck).Methods("GET")
	router.HandleFunc("/readiness", api.ReadinessCheck).Methods("GET")
	router.HandleFunc("/liveness", api.LivenessCheck).Methods("GET")

	// API v1 routes
	v1 := router.PathPrefix("/api/v1").Subrouter()
	
	// Authentication routes (public)
	authRouter := v1.PathPrefix("/auth").Subrouter()
	authRouter.HandleFunc("/signup", api.SignUp).Methods("POST")
	authRouter.HandleFunc("/login", api.Login).Methods("POST")
	authRouter.HandleFunc("/refresh", api.RefreshToken).Methods("POST")
	authRouter.HandleFunc("/logout", api.Logout).Methods("POST")

	// Protected routes
	protectedRouter := v1.PathPrefix("").Subrouter()
	protectedRouter.Use(middleware.AuthMiddleware(cfg))
	
	// User routes
	protectedRouter.HandleFunc("/users/me", api.GetCurrentUser).Methods("GET")
	protectedRouter.HandleFunc("/users/me", api.UpdateCurrentUser).Methods("PUT")
	
	// Room management routes
	protectedRouter.HandleFunc("/rooms", api.CreateRoom).Methods("POST")
	protectedRouter.HandleFunc("/rooms", api.ListRooms).Methods("GET")
	protectedRouter.HandleFunc("/rooms/{room_id}", api.GetRoom).Methods("GET")
	protectedRouter.HandleFunc("/rooms/{room_id}", api.DeleteRoom).Methods("DELETE")
	protectedRouter.HandleFunc("/rooms/{room_id}/token", api.GenerateRoomToken).Methods("POST")
	
	// Call management routes
	protectedRouter.HandleFunc("/calls", api.ListCalls).Methods("GET")
	protectedRouter.HandleFunc("/calls/{call_id}", api.GetCall).Methods("GET")
	protectedRouter.HandleFunc("/calls/{call_id}/participants", api.GetCallParticipants).Methods("GET")
	
	// Contact routes
	protectedRouter.HandleFunc("/contacts", api.CreateContact).Methods("POST")
	protectedRouter.HandleFunc("/contacts", api.ListContacts).Methods("GET")
	protectedRouter.HandleFunc("/contacts/{contact_id}", api.UpdateContact).Methods("PUT")
	protectedRouter.HandleFunc("/contacts/{contact_id}", api.DeleteContact).Methods("DELETE")
	
	// File sharing routes (Phase 2)
	protectedRouter.HandleFunc("/files", api.UploadFile).Methods("POST")
	protectedRouter.HandleFunc("/files", api.ListFiles).Methods("GET")
	protectedRouter.HandleFunc("/files/{file_id}", api.GetFile).Methods("GET")
	protectedRouter.HandleFunc("/files/{file_id}", api.DeleteFile).Methods("DELETE")
	protectedRouter.HandleFunc("/files/{file_id}/download", api.DownloadFile).Methods("GET")
	
	// Organization routes (admin only)
	protectedRouter.HandleFunc("/organizations", api.CreateOrganization).Methods("POST")
	protectedRouter.HandleFunc("/organizations/{org_id}", api.GetOrganization).Methods("GET")
	protectedRouter.HandleFunc("/organizations/{org_id}", api.UpdateOrganization).Methods("PUT")
	
	// ========================================================================
	// PHASE 7: ENTERPRISE FEATURES
	// ========================================================================
	
	// SSO Configuration routes (admin only)
	ssoRouter := protectedRouter.PathPrefix("/sso").Subrouter()
	ssoRouter.HandleFunc("/configs", api.CreateSSOConfig).Methods("POST")
	ssoRouter.HandleFunc("/configs", api.GetSSOConfigs).Methods("GET")
	ssoRouter.HandleFunc("/configs/{config_id}", api.GetSSOConfig).Methods("GET")
	ssoRouter.HandleFunc("/configs/{config_id}", api.UpdateSSOConfig).Methods("PUT")
	ssoRouter.HandleFunc("/configs/{config_id}", api.DeleteSSOConfig).Methods("DELETE")
	
	// SSO Login flows (public)
	authRouter.HandleFunc("/sso/saml/login", api.InitiateSAMLLogin).Methods("GET")
	authRouter.HandleFunc("/sso/saml/callback", api.HandleSAMLCallback).Methods("POST")
	authRouter.HandleFunc("/sso/oauth/login", api.InitiateOAuthLogin).Methods("GET")
	authRouter.HandleFunc("/sso/oauth/callback", api.HandleOAuthCallback).Methods("GET")
	
	// RBAC routes (admin only)
	rbacRouter := protectedRouter.PathPrefix("/rbac").Subrouter()
	rbacRouter.HandleFunc("/roles", api.CreateRole).Methods("POST")
	rbacRouter.HandleFunc("/roles", api.ListRoles).Methods("GET")
	rbacRouter.HandleFunc("/roles/{role_id}", api.GetRole).Methods("GET")
	rbacRouter.HandleFunc("/roles/{role_id}", api.UpdateRole).Methods("PUT")
	rbacRouter.HandleFunc("/roles/{role_id}", api.DeleteRole).Methods("DELETE")
	rbacRouter.HandleFunc("/assignments", api.AssignRoleToUser).Methods("POST")
	rbacRouter.HandleFunc("/assignments/{assignment_id}", api.RevokeUserRole).Methods("DELETE")
	rbacRouter.HandleFunc("/users/{user_id}/roles", api.GetUserRoles).Methods("GET")
	rbacRouter.HandleFunc("/users/{user_id}/permissions", api.GetUserPermissions).Methods("GET")
	rbacRouter.HandleFunc("/permissions/check", api.CheckPermission).Methods("POST")
	
	// Audit Logging routes (admin only)
	auditRouter := protectedRouter.PathPrefix("/audit").Subrouter()
	auditRouter.HandleFunc("/logs", api.CreateAuditLog).Methods("POST")
	auditRouter.HandleFunc("/logs", api.GetAuditLogs).Methods("GET")
	auditRouter.HandleFunc("/logs/{log_id}", api.GetAuditLog).Methods("GET")
	auditRouter.HandleFunc("/logs/export", api.ExportAuditLogs).Methods("GET")
	auditRouter.HandleFunc("/logs/stats", api.GetAuditStats).Methods("GET")
	
	// Billing & Subscriptions routes
	billingRouter := protectedRouter.PathPrefix("/billing").Subrouter()
	billingRouter.HandleFunc("/subscriptions", api.CreateSubscription).Methods("POST")
	billingRouter.HandleFunc("/subscriptions/{subscription_id}", api.GetSubscription).Methods("GET")
	billingRouter.HandleFunc("/subscriptions/{subscription_id}", api.UpdateSubscription).Methods("PUT")
	billingRouter.HandleFunc("/subscriptions/{subscription_id}/cancel", api.CancelSubscription).Methods("POST")
	billingRouter.HandleFunc("/invoices", api.GetInvoices).Methods("GET")
	billingRouter.HandleFunc("/invoices/{invoice_id}", api.GetInvoice).Methods("GET")
	billingRouter.HandleFunc("/usage", api.RecordUsage).Methods("POST")
	billingRouter.HandleFunc("/usage/records", api.GetUsageRecords).Methods("GET")
	billingRouter.HandleFunc("/usage/summary", api.GetUsageSummary).Methods("GET")
	
	// Compliance routes (GDPR/HIPAA)
	complianceRouter := protectedRouter.PathPrefix("/compliance").Subrouter()
	complianceRouter.HandleFunc("/data-export", api.RequestDataExport).Methods("POST")
	complianceRouter.HandleFunc("/data-deletion", api.RequestDataDeletion).Methods("POST")
	complianceRouter.HandleFunc("/requests", api.GetComplianceRequests).Methods("GET")
	complianceRouter.HandleFunc("/requests/{request_id}", api.GetComplianceRequest).Methods("GET")
	complianceRouter.HandleFunc("/requests/{request_id}/cancel", api.CancelComplianceRequest).Methods("POST")
	complianceRouter.HandleFunc("/retention-policies", api.CreateRetentionPolicy).Methods("POST")
	complianceRouter.HandleFunc("/retention-policies", api.GetRetentionPolicies).Methods("GET")
	complianceRouter.HandleFunc("/retention-policies/{policy_id}", api.UpdateRetentionPolicy).Methods("PUT")
	complianceRouter.HandleFunc("/retention-policies/{policy_id}", api.DeleteRetentionPolicy).Methods("DELETE")
	complianceRouter.HandleFunc("/report", api.GetComplianceReport).Methods("GET")
	
	// Analytics routes
	analyticsRouter := protectedRouter.PathPrefix("/analytics").Subrouter()
	analyticsRouter.HandleFunc("/organizations/{org_id}", api.GetOrganizationAnalytics).Methods("GET")
	analyticsRouter.HandleFunc("/call-quality", api.GetCallQualityAnalytics).Methods("GET")
	analyticsRouter.HandleFunc("/ai-usage", api.GetAIUsageAnalytics).Methods("GET")
	analyticsRouter.HandleFunc("/cost-insights", api.GetCostOptimizationInsights).Methods("GET")
	analyticsRouter.HandleFunc("/cost-insights/{insight_id}/acknowledge", api.AcknowledgeCostInsight).Methods("POST")
	analyticsRouter.HandleFunc("/reports", api.CreateCustomReport).Methods("POST")
	analyticsRouter.HandleFunc("/reports", api.GetCustomReports).Methods("GET")
	analyticsRouter.HandleFunc("/reports/{report_id}/run", api.RunCustomReport).Methods("POST")
	analyticsRouter.HandleFunc("/realtime", api.GetRealtimeMetrics).Methods("GET")
	
	// ========================================================================
	// PHASE 6: AURAID & MESH NETWORK
	// ========================================================================
	
	// AuraID routes
	auraIDRouter := protectedRouter.PathPrefix("/auraid").Subrouter()
	auraIDRouter.HandleFunc("", api.CreateAuraID).Methods("POST")
	auraIDRouter.HandleFunc("/me", api.GetMyAuraID).Methods("GET")
	auraIDRouter.HandleFunc("/me", api.UpdateAuraID).Methods("PUT")
	auraIDRouter.HandleFunc("/verify", api.VerifyAuraID).Methods("POST")
	auraIDRouter.HandleFunc("/search", api.SearchAuraID).Methods("GET")
	auraIDRouter.HandleFunc("/{aura_id}/resolve", api.ResolveAuraID).Methods("GET")
	
	// Public AuraID routes
	v1.HandleFunc("/auraid/check", api.CheckAuraIDAvailability).Methods("GET")
	
	// Mesh network routes
	meshRouter := protectedRouter.PathPrefix("/mesh").Subrouter()
	meshRouter.HandleFunc("/nodes", api.GetMyMeshNodes).Methods("GET")
	meshRouter.HandleFunc("/nodes/{node_id}", api.GetMeshNodeByID).Methods("GET")
	meshRouter.HandleFunc("/nodes/{node_id}/reputation", api.GetNodeReputationHistory).Methods("GET")
	meshRouter.HandleFunc("/routes", api.GetMeshRoutes).Methods("GET")
	meshRouter.HandleFunc("/reports/abuse", api.SubmitAbuseReport).Methods("POST")
	meshRouter.HandleFunc("/stats", api.GetMeshStatistics).Methods("GET")
	meshRouter.HandleFunc("/health", api.GetMeshHealth).Methods("GET")
	
	log.Println("✓ Phase 6 mesh network and AuraID routes configured:")
	log.Println("  - AuraID Creation & Verification")
	log.Println("  - Mesh Node Management")
	log.Println("  - AI-Powered Routing")
	log.Println("  - Trust & Reputation System")
	log.Println("  - Abuse Reporting")
	log.Println("  - Federation Support")
	
	log.Println("✓ Phase 7 enterprise routes configured:")
	log.Println("  - SSO Integration (SAML/OAuth)")
	log.Println("  - RBAC with Casbin")
	log.Println("  - Audit Logging")
	log.Println("  - Billing & Subscriptions")
	log.Println("  - GDPR/HIPAA Compliance")
	log.Println("  - Advanced Analytics")

	// Apply middleware
	router.Use(middleware.LoggingMiddleware)
	router.Use(middleware.RecoveryMiddleware)
	router.Use(middleware.MetricsMiddleware)

	// CORS configuration
	c := cors.New(cors.Options{
		AllowedOrigins:   []string{"http://localhost:3000", "http://localhost:8080"},
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Authorization", "Content-Type", "X-Request-ID"},
		AllowCredentials: true,
		MaxAge:           86400,
	})

	handler := c.Handler(router)

	// Create HTTP server
	srv := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Service.Port),
		Handler:      handler,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start server in a goroutine
	go func() {
		log.Printf("Dashboard Service listening on port %d", cfg.Service.Port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	// Wait for interrupt signal to gracefully shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")

	// Graceful shutdown with 30 second timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}

	log.Println("Server exited")
}
