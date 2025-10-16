// Package config provides configuration management for AuraLink services
package config

import (
	"fmt"
	"os"
	"strconv"
	"time"

	"gopkg.in/yaml.v3"
)

// Config represents the application configuration
type Config struct {
	Environment string           `yaml:"environment"`
	Service     ServiceConfig    `yaml:"service"`
	Database    DatabaseConfig   `yaml:"database"`
	Redis       RedisConfig      `yaml:"redis"`
	Auth        AuthConfig       `yaml:"auth"`
	Monitoring  MonitoringConfig `yaml:"monitoring"`
	AIC         AICConfig        `yaml:"aic"`
	RateLimit   RateLimitConfig  `yaml:"rate_limit"`
}

// ServiceConfig contains service-specific configuration
type ServiceConfig struct {
	Name        string        `yaml:"name"`
	Port        int           `yaml:"port"`
	HealthCheck string        `yaml:"health_check"`
	Timeout     time.Duration `yaml:"timeout"`
}

// DatabaseConfig contains database connection settings
type DatabaseConfig struct {
	Provider          string        `yaml:"provider"`
	Host              string        `yaml:"host"`
	Port              int           `yaml:"port"`
	Database          string        `yaml:"database"`
	MaxConnections    int           `yaml:"max_connections"`
	ConnectionTimeout time.Duration `yaml:"connection_timeout"`
}

// RedisConfig contains Redis connection settings
type RedisConfig struct {
	Host       string `yaml:"host"`
	Port       int    `yaml:"port"`
	DB         int    `yaml:"db"`
	MaxRetries int    `yaml:"max_retries"`
	PoolSize   int    `yaml:"pool_size"`
}

// AuthConfig contains authentication settings
type AuthConfig struct {
	Provider               string        `yaml:"provider"`
	JWTExpiration          time.Duration `yaml:"jwt_expiration"`
	RefreshTokenExpiration time.Duration `yaml:"refresh_token_expiration"`
}

// MonitoringConfig contains monitoring settings
type MonitoringConfig struct {
	Prometheus PrometheusConfig `yaml:"prometheus"`
	Jaeger     JaegerConfig     `yaml:"jaeger"`
	Logging    LoggingConfig    `yaml:"logging"`
}

// PrometheusConfig contains Prometheus settings
type PrometheusConfig struct {
	Enabled        bool          `yaml:"enabled"`
	Port           int           `yaml:"port"`
	ScrapeInterval time.Duration `yaml:"scrape_interval"`
}

// JaegerConfig contains Jaeger tracing settings
type JaegerConfig struct {
	Enabled      bool    `yaml:"enabled"`
	Endpoint     string  `yaml:"endpoint"`
	SamplingRate float64 `yaml:"sampling_rate"`
}

// LoggingConfig contains logging settings
type LoggingConfig struct {
	Level  string `yaml:"level"`
	Format string `yaml:"format"`
	Output string `yaml:"output"`
}

// AICConfig contains AIC Protocol settings
type AICConfig struct {
	Enabled          bool    `yaml:"enabled"`
	CompressionRatio float64 `yaml:"compression_ratio"`
	FallbackEnabled  bool    `yaml:"fallback_enabled"`
	MinBandwidth     int     `yaml:"min_bandwidth"`
}

// RateLimitConfig contains rate limiting settings
type RateLimitConfig struct {
	Enabled            bool `yaml:"enabled"`
	RequestsPerMinute  int  `yaml:"requests_per_minute"`
	Burst              int  `yaml:"burst"`
}

// LoadConfig loads configuration from file and environment variables
func LoadConfig(configPath string) (*Config, error) {
	config := &Config{}

	// Load from YAML file if provided
	if configPath != "" {
		data, err := os.ReadFile(configPath)
		if err != nil {
			return nil, fmt.Errorf("failed to read config file: %w", err)
		}

		if err := yaml.Unmarshal(data, config); err != nil {
			return nil, fmt.Errorf("failed to parse config file: %w", err)
		}
	}

	// Override with environment variables
	config.applyEnvOverrides()

	return config, nil
}

// applyEnvOverrides applies environment variable overrides
func (c *Config) applyEnvOverrides() {
	if env := os.Getenv("ENVIRONMENT"); env != "" {
		c.Environment = env
	}

	// Supabase
	if url := os.Getenv("SUPABASE_URL"); url != "" {
		c.Database.Host = url
	}

	// Redis
	if host := os.Getenv("REDIS_HOST"); host != "" {
		c.Redis.Host = host
	}
	if port := os.Getenv("REDIS_PORT"); port != "" {
		if p, err := strconv.Atoi(port); err == nil {
			c.Redis.Port = p
		}
	}

	// Service port
	if port := os.Getenv("SERVICE_PORT"); port != "" {
		if p, err := strconv.Atoi(port); err == nil {
			c.Service.Port = p
		}
	}

	// AIC
	if enableAIC := os.Getenv("ENABLE_AIC"); enableAIC == "true" {
		c.AIC.Enabled = true
	}

	// Log level
	if level := os.Getenv("LOG_LEVEL"); level != "" {
		c.Monitoring.Logging.Level = level
	}
}

// GetDatabaseURL returns the database connection URL
func (c *Config) GetDatabaseURL() string {
	url := os.Getenv("DATABASE_URL")
	if url != "" {
		return url
	}
	return fmt.Sprintf("postgresql://postgres@%s:%d/%s", c.Database.Host, c.Database.Port, c.Database.Database)
}

// GetRedisAddr returns the Redis address
func (c *Config) GetRedisAddr() string {
	return fmt.Sprintf("%s:%d", c.Redis.Host, c.Redis.Port)
}

// IsDevelopment checks if running in development mode
func (c *Config) IsDevelopment() bool {
	return c.Environment == "development" || c.Environment == "dev"
}

// IsProduction checks if running in production mode
func (c *Config) IsProduction() bool {
	return c.Environment == "production" || c.Environment == "prod"
}
