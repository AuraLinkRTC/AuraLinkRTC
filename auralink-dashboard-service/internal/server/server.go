// Package server provides the main server struct with dependency injection
package server

import (
	"database/sql"
	"log"

	"github.com/auralink/dashboard-service/internal/config"
	"github.com/auralink/shared/livekit"
	"github.com/auralink/shared/storage"
	"github.com/redis/go-redis/v9"
)

// Server represents the main application server with all dependencies
type Server struct {
	Config   *config.Config
	DB       *sql.DB
	Redis    *redis.Client
	Logger   *log.Logger
	LiveKit  livekit.Client
	Storage  storage.Client
}

// NewServer creates a new server instance with dependency injection
func NewServer(cfg *config.Config) (*Server, error) {
	// Create logger
	logger := log.New(log.Writer(), "[dashboard-service] ", log.LstdFlags|log.Lshortfile)

	server := &Server{
		Config: cfg,
		Logger: logger,
	}

	return server, nil
}

// SetDB sets the database connection
func (s *Server) SetDB(db *sql.DB) {
	s.DB = db
}

// SetRedis sets the Redis client
func (s *Server) SetRedis(client *redis.Client) {
	s.Redis = client
}

// SetLiveKit sets the LiveKit client
func (s *Server) SetLiveKit(client livekit.Client) {
	s.LiveKit = client
}

// SetStorage sets the Storage client
func (s *Server) SetStorage(client storage.Client) {
	s.Storage = client
}

// HasDB checks if database is configured
func (s *Server) HasDB() bool {
	return s.DB != nil
}

// HasRedis checks if Redis is configured
func (s *Server) HasRedis() bool {
	return s.Redis != nil
}

// HasLiveKit checks if LiveKit is configured
func (s *Server) HasLiveKit() bool {
	return s.LiveKit != nil
}

// HasStorage checks if Storage is configured
func (s *Server) HasStorage() bool {
	return s.Storage != nil
}
