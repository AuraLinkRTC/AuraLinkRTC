package livekit

import (
	"log"
	"sync"
)

var (
	globalClient *Client
	clientMutex  sync.RWMutex
)

// InitClient initializes the global LiveKit client instance
func InitClient(client *Client) {
	clientMutex.Lock()
	defer clientMutex.Unlock()
	globalClient = client
	log.Println("✓ Global LiveKit client initialized")
}

// GetClient returns the global LiveKit client instance
func GetClient() *Client {
	clientMutex.RLock()
	defer clientMutex.RUnlock()
	return globalClient
}

// CloseClient closes the global LiveKit client
func CloseClient() error {
	clientMutex.Lock()
	defer clientMutex.Unlock()
	if globalClient != nil {
		return globalClient.Close()
	}
	return nil
}
