// Package cache provides Redis caching with health checks
package cache

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

// RedisClient wraps Redis client with helper methods
type RedisClient struct {
	client *redis.Client
	config Config
}

// Config holds Redis configuration
type Config struct {
	Host     string
	Port     int
	Password string
	DB       int
}

// New creates a new Redis client
func New(cfg Config) (*RedisClient, error) {
	if cfg.Host == "" {
		cfg.Host = "localhost"
	}
	if cfg.Port == 0 {
		cfg.Port = 6379
	}

	client := redis.NewClient(&redis.Options{
		Addr:         fmt.Sprintf("%s:%d", cfg.Host, cfg.Port),
		Password:     cfg.Password,
		DB:           cfg.DB,
		DialTimeout:  5 * time.Second,
		ReadTimeout:  3 * time.Second,
		WriteTimeout: 3 * time.Second,
		PoolSize:     50,
		MinIdleConns: 10,
	})

	rc := &RedisClient{
		client: client,
		config: cfg,
	}

	// Verify connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := rc.Ping(ctx); err != nil {
		log.Printf("⚠ Redis connection failed: %v (service will continue without caching)", err)
		return rc, nil // Return client but log warning
	}

	info, err := client.Info(ctx, "server").Result()
	if err == nil {
		log.Printf("✓ Redis connected: %s", info[:50])
	}

	return rc, nil
}

// Close closes the Redis connection
func (rc *RedisClient) Close() error {
	if rc.client != nil {
		log.Println("✓ Closing Redis connection")
		return rc.client.Close()
	}
	return nil
}

// Ping checks if Redis is reachable
func (rc *RedisClient) Ping(ctx context.Context) error {
	if rc.client == nil {
		return fmt.Errorf("redis client not initialized")
	}
	return rc.client.Ping(ctx).Err()
}

// HealthCheck performs a Redis health check
func (rc *RedisClient) HealthCheck(ctx context.Context) (map[string]interface{}, error) {
	if rc.client == nil {
		return map[string]interface{}{
			"status": "unavailable",
			"error":  "client not initialized",
		}, fmt.Errorf("redis client not initialized")
	}

	start := time.Now()
	if err := rc.client.Ping(ctx).Err(); err != nil {
		return map[string]interface{}{
			"status": "unhealthy",
			"error":  err.Error(),
		}, err
	}
	latency := time.Since(start).Milliseconds()

	// Get stats
	stats := rc.client.PoolStats()

	return map[string]interface{}{
		"status":      "healthy",
		"latency_ms":  latency,
		"hits":        stats.Hits,
		"misses":      stats.Misses,
		"timeouts":    stats.Timeouts,
		"total_conns": stats.TotalConns,
		"idle_conns":  stats.IdleConns,
	}, nil
}

// Get retrieves a value from Redis
func (rc *RedisClient) Get(ctx context.Context, key string) (string, error) {
	if rc.client == nil {
		return "", fmt.Errorf("redis not available")
	}
	return rc.client.Get(ctx, key).Result()
}

// Set stores a value in Redis with optional expiration
func (rc *RedisClient) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	if rc.client == nil {
		return fmt.Errorf("redis not available")
	}
	return rc.client.Set(ctx, key, value, expiration).Err()
}

// SetJSON stores a JSON-encoded value in Redis
func (rc *RedisClient) SetJSON(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	if rc.client == nil {
		return fmt.Errorf("redis not available")
	}

	data, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("failed to marshal JSON: %w", err)
	}

	return rc.client.Set(ctx, key, data, expiration).Err()
}

// GetJSON retrieves and decodes a JSON value from Redis
func (rc *RedisClient) GetJSON(ctx context.Context, key string, dest interface{}) error {
	if rc.client == nil {
		return fmt.Errorf("redis not available")
	}

	data, err := rc.client.Get(ctx, key).Result()
	if err != nil {
		return err
	}

	return json.Unmarshal([]byte(data), dest)
}

// Delete removes a key from Redis
func (rc *RedisClient) Delete(ctx context.Context, keys ...string) error {
	if rc.client == nil {
		return fmt.Errorf("redis not available")
	}
	return rc.client.Del(ctx, keys...).Err()
}

// Exists checks if a key exists in Redis
func (rc *RedisClient) Exists(ctx context.Context, key string) (bool, error) {
	if rc.client == nil {
		return false, fmt.Errorf("redis not available")
	}
	result, err := rc.client.Exists(ctx, key).Result()
	return result > 0, err
}

// Expire sets expiration on a key
func (rc *RedisClient) Expire(ctx context.Context, key string, expiration time.Duration) error {
	if rc.client == nil {
		return fmt.Errorf("redis not available")
	}
	return rc.client.Expire(ctx, key, expiration).Err()
}

// Publish publishes a message to a channel
func (rc *RedisClient) Publish(ctx context.Context, channel string, message interface{}) error {
	if rc.client == nil {
		return fmt.Errorf("redis not available")
	}

	var payload interface{}
	if str, ok := message.(string); ok {
		payload = str
	} else {
		data, err := json.Marshal(message)
		if err != nil {
			return fmt.Errorf("failed to marshal message: %w", err)
		}
		payload = string(data)
	}

	return rc.client.Publish(ctx, channel, payload).Err()
}

// Subscribe subscribes to channels
func (rc *RedisClient) Subscribe(ctx context.Context, channels ...string) *redis.PubSub {
	if rc.client == nil {
		return nil
	}
	return rc.client.Subscribe(ctx, channels...)
}

// GetClient returns the underlying Redis client
func (rc *RedisClient) GetClient() *redis.Client {
	return rc.client
}
