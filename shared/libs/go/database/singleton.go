package database

import (
	"database/sql"
	"log"
	"sync"
)

var (
	globalDB *sql.DB
	dbMutex  sync.RWMutex
)

// InitDB initializes the global database instance
func InitDB(db *sql.DB) {
	dbMutex.Lock()
	defer dbMutex.Unlock()
	globalDB = db
	log.Println("✓ Global database instance initialized")
}

// GetDB returns the global database instance
func GetDB() *sql.DB {
	dbMutex.RLock()
	defer dbMutex.RUnlock()
	return globalDB
}

// CloseDB closes the global database connection
func CloseDB() error {
	dbMutex.Lock()
	defer dbMutex.Unlock()
	if globalDB != nil {
		return globalDB.Close()
	}
	return nil
}
