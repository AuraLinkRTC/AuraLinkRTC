// Package api provides HTTP handlers with server context
package api

import (
	"database/sql"
	"log"
	"sync"

	"github.com/auralink/dashboard-service/internal/config"
	"github.com/auralink/dashboard-service/internal/services"
	"github.com/auralink/shared/database"
	"github.com/auralink/shared/livekit"
	"github.com/auralink/shared/storage"
)

// ServerContext holds global server dependencies accessible to all handlers
type ServerContext struct {
	Config             *config.Config
	Logger             *log.Logger
	DB                 *sql.DB
	LiveKitClient      livekit.Client
	StorageClient      storage.Client
	EnterpriseService  *services.EnterpriseService
}

var (
	serverContext *ServerContext
	contextMutex  sync.RWMutex
)

// InitServerContext initializes the global server context
func InitServerContext(cfg *config.Config, logger *log.Logger) {
	contextMutex.Lock()
	defer contextMutex.Unlock()

	serverContext = &ServerContext{
		Config: cfg,
		Logger: logger,
	}
}

// GetServerContext returns the global server context
func GetServerContext() *ServerContext {
	contextMutex.RLock()
	defer contextMutex.RUnlock()
	return serverContext
}

// SetDatabase sets the database connection
func SetDatabase(db *sql.DB) {
	contextMutex.Lock()
	defer contextMutex.Unlock()
	if serverContext != nil {
		serverContext.DB = db
	}
}

// SetLiveKitClient sets the LiveKit client
func SetLiveKitClient(client livekit.Client) {
	contextMutex.Lock()
	defer contextMutex.Unlock()
	if serverContext != nil {
		serverContext.LiveKitClient = client
	}
}

// SetStorageClient sets the storage client
func SetStorageClient(client storage.Client) {
	contextMutex.Lock()
	defer contextMutex.Unlock()
	if serverContext != nil {
		serverContext.StorageClient = client
	}
}

// InitEnterpriseService initializes the enterprise service
func InitEnterpriseService(service *services.EnterpriseService) {
	contextMutex.Lock()
	defer contextMutex.Unlock()
	if serverContext != nil {
		serverContext.EnterpriseService = service
	}
}

// GetDB returns the database connection (backward compatible helper)
func GetDB() *sql.DB {
	ctx := GetServerContext()
	if ctx != nil {
		return ctx.DB
	}
	// Fallback to legacy global database
	return database.GetDB()
}

// GetLiveKitClient returns the LiveKit client (backward compatible helper)
func GetLiveKitClient() livekit.Client {
	ctx := GetServerContext()
	if ctx != nil && ctx.LiveKitClient != nil {
		return ctx.LiveKitClient
	}
	// Fallback to legacy global client
	return livekit.GetClient()
}

// GetStorageClient returns the storage client (backward compatible helper)
func GetStorageClient() storage.Client {
	ctx := GetServerContext()
	if ctx != nil && ctx.StorageClient != nil {
		return ctx.StorageClient
	}
	// Fallback to legacy global client
	return storage.GetClient()
}

// GetEnterpriseService returns the enterprise service
func GetEnterpriseService() *services.EnterpriseService {
	ctx := GetServerContext()
	if ctx != nil {
		return ctx.EnterpriseService
	}
	return nil
}

// GetConfig returns the configuration
func GetConfig() *config.Config {
	ctx := GetServerContext()
	if ctx != nil {
		return ctx.Config
	}
	return nil
}

// GetLogger returns the logger
func GetLogger() *log.Logger {
	ctx := GetServerContext()
	if ctx != nil && ctx.Logger != nil {
		return ctx.Logger
	}
	// Fallback to standard logger
	return log.Default()
}
