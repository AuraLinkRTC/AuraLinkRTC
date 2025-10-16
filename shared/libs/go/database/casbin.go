// Package database - Casbin RBAC enforcer integration
package database

import (
	"fmt"
	"log"
	"sync"

	"github.com/casbin/casbin/v2"
	gormadapter "github.com/casbin/gorm-adapter/v3"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

var (
	gormDB   *gorm.DB
	enforcer *casbin.Enforcer
	gormMutex sync.RWMutex
)

// InitCasbin initializes the Casbin enforcer with GORM adapter
func InitCasbin(databaseURL, modelPath string) error {
	gormMutex.Lock()
	defer gormMutex.Unlock()

	// Initialize GORM if not already done
	if gormDB == nil {
		var err error
		gormDB, err = gorm.Open(postgres.Open(databaseURL), &gorm.Config{
			Logger: logger.Default.LogMode(logger.Silent),
		})
		if err != nil {
			return fmt.Errorf("failed to initialize GORM: %w", err)
		}
	}

	// Create Casbin adapter
	adapter, err := gormadapter.NewAdapterByDB(gormDB)
	if err != nil {
		return fmt.Errorf("failed to create Casbin adapter: %w", err)
	}

	// Use inline model if no path provided
	var e *casbin.Enforcer
	if modelPath == "" {
		modelText := `
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act
`
		e, err = casbin.NewEnforcer(casbin.NewModel(modelText), adapter)
	} else {
		e, err = casbin.NewEnforcer(modelPath, adapter)
	}

	if err != nil {
		return fmt.Errorf("failed to create Casbin enforcer: %w", err)
	}

	// Load policies from database
	if err := e.LoadPolicy(); err != nil {
		return fmt.Errorf("failed to load policies: %w", err)
	}

	enforcer = e
	log.Println("✓ Casbin enforcer initialized")
	return nil
}

// GetEnforcer returns the Casbin enforcer instance
func GetEnforcer() *casbin.Enforcer {
	gormMutex.RLock()
	defer gormMutex.RUnlock()
	return enforcer
}

// GetGormDB returns the GORM database instance
func GetGormDB() *gorm.DB {
	gormMutex.RLock()
	defer gormMutex.RUnlock()
	return gormDB
}
