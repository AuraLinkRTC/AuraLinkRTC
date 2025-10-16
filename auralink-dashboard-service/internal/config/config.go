// Package config provides configuration management
package config

import (
	"fmt"
	"os"
	"strconv"
)

// Config represents the application configuration
type Config struct {
	Environment string
	Service     ServiceConfig
	Database    DatabaseConfig
	Redis       RedisConfig
	Auth        AuthConfig
	Supabase    SupabaseConfig
	LiveKit     LiveKitConfig
	Storage     StorageConfig
	Enterprise  EnterpriseConfig
}

// EnterpriseConfig contains enterprise feature settings
type EnterpriseConfig struct {
	StripeSecretKey      string
	StripeWebhookSecret  string
	CasbinModelPath      string
	EnableSSO            bool
	EnableRBAC           bool
	EnableAuditLogging   bool
	EnableBilling        bool
}

// ServiceConfig contains service-specific settings
type ServiceConfig struct {
	Name string
	Port int
}

// DatabaseConfig contains database settings
type DatabaseConfig struct {
	URL            string
	MaxConnections int
}

// RedisConfig contains Redis settings
type RedisConfig struct {
	Host     string
	Password string
}

// AuthConfig contains authentication settings
type AuthConfig struct {
	JWTSecret      string
	TokenDuration  int // hours
}

// SupabaseConfig contains Supabase settings
type SupabaseConfig struct {
	URL            string
	AnonKey        string
	ServiceRoleKey string
	JWTSecret      string
}

// LiveKitConfig contains LiveKit settings
type LiveKitConfig struct {
	URL       string
	APIKey    string
	APISecret string
}

// StorageConfig contains storage settings
type StorageConfig struct {
	URL            string
	ServiceRoleKey string
	BucketName     string
}

// Load loads configuration from environment variables
func Load(configPath string) (*Config, error) {
	cfg := &Config{
		Environment: getEnv("ENVIRONMENT", "development"),
		Service: ServiceConfig{
			Name: getEnv("SERVICE_NAME", "auralink-dashboard-service"),
			Port: getEnvInt("DASHBOARD_SERVICE_PORT", 8080),
		},
		Database: DatabaseConfig{
			URL:            getEnv("DATABASE_URL", ""),
			MaxConnections: getEnvInt("DB_MAX_CONNECTIONS", 100),
		},
		Redis: RedisConfig{
			Host:     getEnv("REDIS_HOST", "localhost:6379"),
			Password: getEnv("REDIS_PASSWORD", ""),
		},
		Auth: AuthConfig{
			JWTSecret:     getEnv("SUPABASE_JWT_SECRET", ""),
			TokenDuration: getEnvInt("JWT_EXPIRATION_HOURS", 24),
		},
		Supabase: SupabaseConfig{
			URL:            getEnv("SUPABASE_URL", ""),
			AnonKey:        getEnv("SUPABASE_ANON_KEY", ""),
			ServiceRoleKey: getEnv("SUPABASE_SERVICE_ROLE_KEY", ""),
			JWTSecret:      getEnv("SUPABASE_JWT_SECRET", ""),
		},
		LiveKit: LiveKitConfig{
			URL:       getEnv("LIVEKIT_URL", "ws://localhost:7880"),
			APIKey:    getEnv("LIVEKIT_API_KEY", ""),
			APISecret: getEnv("LIVEKIT_API_SECRET", ""),
		},
		Storage: StorageConfig{
			URL:            getEnv("STORAGE_URL", getEnv("SUPABASE_URL", "")+"/storage/v1"),
			ServiceRoleKey: getEnv("STORAGE_SERVICE_ROLE_KEY", getEnv("SUPABASE_SERVICE_ROLE_KEY", "")),
			BucketName:     getEnv("STORAGE_BUCKET", "auralink-files"),
		},
		Enterprise: EnterpriseConfig{
			StripeSecretKey:     getEnv("STRIPE_SECRET_KEY", ""),
			StripeWebhookSecret: getEnv("STRIPE_WEBHOOK_SECRET", ""),
			CasbinModelPath:     getEnv("CASBIN_MODEL_PATH", ""),
			EnableSSO:           getEnv("ENABLE_SSO", "true") == "true",
			EnableRBAC:          getEnv("ENABLE_RBAC", "true") == "true",
			EnableAuditLogging:  getEnv("ENABLE_AUDIT_LOGGING", "true") == "true",
			EnableBilling:       getEnv("ENABLE_BILLING", "false") == "true",
		},
	}

	// Validate required fields
	if cfg.Supabase.URL == "" {
		return nil, fmt.Errorf("SUPABASE_URL is required")
	}
	if cfg.Supabase.JWTSecret == "" {
		return nil, fmt.Errorf("SUPABASE_JWT_SECRET is required")
	}

	return cfg, nil
}

// IsDevelopment checks if running in development mode
func (c *Config) IsDevelopment() bool {
	return c.Environment == "development" || c.Environment == "dev"
}

// IsProduction checks if running in production mode
func (c *Config) IsProduction() bool {
	return c.Environment == "production" || c.Environment == "prod"
}

// Helper functions
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intVal, err := strconv.Atoi(value); err == nil {
			return intVal
		}
	}
	return defaultValue
}
