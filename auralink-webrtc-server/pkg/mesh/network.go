package mesh

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/pion/webrtc/v4"
)

// NodeType represents the type of mesh node
type NodeType string

const (
	NodeTypePeer      NodeType = "peer"
	NodeTypeRelay     NodeType = "relay"
	NodeTypeEdge      NodeType = "edge"
	NodeTypeSuperNode NodeType = "super_node"
)

// TrustLevel represents the trust level of a node
type TrustLevel string

const (
	TrustLevelNew        TrustLevel = "new"
	TrustLevelTrusted    TrustLevel = "trusted"
	TrustLevelVerified   TrustLevel = "verified"
	TrustLevelSuspicious TrustLevel = "suspicious"
	TrustLevelBanned     TrustLevel = "banned"
)

// MeshNode represents a node in the mesh network
type MeshNode struct {
	NodeID                   string     `json:"node_id"`
	AuraID                   string     `json:"aura_id"`
	NodeAddress              string     `json:"node_address"`
	NodeType                 NodeType   `json:"node_type"`
	MaxConnections           int        `json:"max_connections"`
	CurrentConnections       int        `json:"current_connections"`
	BandwidthCapacityMbps    int        `json:"bandwidth_capacity_mbps"`
	CurrentBandwidthUsageMbps int       `json:"current_bandwidth_usage_mbps"`
	Region                   string     `json:"region"`
	CountryCode              string     `json:"country_code"`
	Latitude                 float64    `json:"latitude"`
	Longitude                float64    `json:"longitude"`
	AvgLatencyMs             float64    `json:"avg_latency_ms"`
	PacketLossRate           float64    `json:"packet_loss_rate"`
	UptimePercentage         float64    `json:"uptime_percentage"`
	ReputationScore          float64    `json:"reputation_score"`
	TrustLevel               TrustLevel `json:"trust_level"`
	IsOnline                 bool       `json:"is_online"`
	IsAcceptingConnections   bool       `json:"is_accepting_connections"`
	SupportsAICProtocol      bool       `json:"supports_aic_protocol"`
	LastHeartbeatAt          time.Time  `json:"last_heartbeat_at"`
	CreatedAt                time.Time  `json:"created_at"`
	UpdatedAt                time.Time  `json:"updated_at"`
}

// MeshRoute represents a route through the mesh network
type MeshRoute struct {
	RouteID                 string    `json:"route_id"`
	SourceNodeID            string    `json:"source_node_id"`
	DestinationNodeID       string    `json:"destination_node_id"`
	PathNodes               []string  `json:"path_nodes"`
	PathLength              int       `json:"path_length"`
	AIScore                 float64   `json:"ai_score"`
	PredictedLatencyMs      int       `json:"predicted_latency_ms"`
	PredictedBandwidthMbps  int       `json:"predicted_bandwidth_mbps"`
	ActualLatencyMs         *int      `json:"actual_latency_ms,omitempty"`
	ActualBandwidthMbps     *int      `json:"actual_bandwidth_mbps,omitempty"`
	PacketLossRate          *float64  `json:"packet_loss_rate,omitempty"`
	IsActive                bool      `json:"is_active"`
	IsOptimal               bool      `json:"is_optimal"`
	UsageCount              int       `json:"usage_count"`
	SuccessRate             float64   `json:"success_rate"`
	CreatedAt               time.Time `json:"created_at"`
	ExpiresAt               time.Time `json:"expires_at"`
}

// P2PConnection represents a peer-to-peer connection
type P2PConnection struct {
	ConnectionID   string               `json:"connection_id"`
	SourceNodeID   string               `json:"source_node_id"`
	TargetNodeID   string               `json:"target_node_id"`
	RouteID        string               `json:"route_id"`
	Status         string               `json:"status"`
	EstablishedAt  time.Time            `json:"established_at"`
	TerminatedAt   *time.Time           `json:"terminated_at,omitempty"`
	PeerConnection *webrtc.PeerConnection `json:"-"`
	DataChannel    *webrtc.DataChannel    `json:"-"`
}

// MeshNetwork manages the mesh networking layer
type MeshNetwork struct {
	db                *sql.DB
	localNode         *MeshNode
	activeConnections map[string]*P2PConnection
	mu                sync.RWMutex
	ctx               context.Context
	cancel            context.CancelFunc
	aiCoreURL         string
	iceServers        []webrtc.ICEServer
}

// NewMeshNetwork creates a new mesh network manager
func NewMeshNetwork(db *sql.DB, auraID string, nodeType NodeType, aiCoreURL string) (*MeshNetwork, error) {
	ctx, cancel := context.WithCancel(context.Background())

	// Configure ICE servers (STUN/TURN)
	iceServers := []webrtc.ICEServer{
		{
			URLs: []string{
				"stun:stun.l.google.com:19302",
				"stun:stun1.l.google.com:19302",
			},
		},
		{
			URLs:       []string{"turn:turn.auralink.io:3478"},
			Username:   "auralink",
			Credential: "auralink-turn-secret",
		},
	}

	mn := &MeshNetwork{
		db:                db,
		activeConnections: make(map[string]*P2PConnection),
		ctx:               ctx,
		cancel:            cancel,
		aiCoreURL:         aiCoreURL,
		iceServers:        iceServers,
	}

	// Register or retrieve local node
	node, err := mn.registerNode(auraID, nodeType)
	if err != nil {
		cancel()
		return nil, fmt.Errorf("failed to register node: %w", err)
	}

	mn.localNode = node

	// Start heartbeat
	go mn.heartbeatLoop()

	// Start connection monitor
	go mn.monitorConnections()

	log.Printf("Mesh network initialized for node %s (AuraID: %s)", node.NodeID, node.AuraID)

	return mn, nil
}

// registerNode registers this instance as a mesh node
func (mn *MeshNetwork) registerNode(auraID string, nodeType NodeType) (*MeshNode, error) {
	nodeID := uuid.New().String()

	// Get geo location (placeholder - in production, use IP geolocation service)
	region := "us-west-1"
	countryCode := "US"
	latitude := 37.7749
	longitude := -122.4194

	node := &MeshNode{
		NodeID:                   nodeID,
		AuraID:                   auraID,
		NodeAddress:              "",  // Will be set based on actual network address
		NodeType:                 nodeType,
		MaxConnections:           100,
		CurrentConnections:       0,
		BandwidthCapacityMbps:    1000,
		CurrentBandwidthUsageMbps: 0,
		Region:                   region,
		CountryCode:              countryCode,
		Latitude:                 latitude,
		Longitude:                longitude,
		AvgLatencyMs:             10.0,
		PacketLossRate:           0.001,
		UptimePercentage:         100.0,
		ReputationScore:          50.0,
		TrustLevel:               TrustLevelNew,
		IsOnline:                 true,
		IsAcceptingConnections:   true,
		SupportsAICProtocol:      true,
		LastHeartbeatAt:          time.Now(),
	}

	// Insert into database
	_, err := mn.db.Exec(`
		INSERT INTO mesh_nodes (
			node_id, aura_id, node_address, node_type, max_connections, current_connections,
			bandwidth_capacity_mbps, current_bandwidth_usage_mbps, region, country_code,
			latitude, longitude, avg_latency_ms, packet_loss_rate, uptime_percentage,
			reputation_score, trust_level, is_online, is_accepting_connections,
			supports_aic_protocol, last_heartbeat_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
	`,
		node.NodeID, node.AuraID, node.NodeAddress, node.NodeType, node.MaxConnections,
		node.CurrentConnections, node.BandwidthCapacityMbps, node.CurrentBandwidthUsageMbps,
		node.Region, node.CountryCode, node.Latitude, node.Longitude,
		node.AvgLatencyMs, node.PacketLossRate, node.UptimePercentage,
		node.ReputationScore, node.TrustLevel, node.IsOnline, node.IsAcceptingConnections,
		node.SupportsAICProtocol, node.LastHeartbeatAt,
	)

	if err != nil {
		return nil, err
	}

	return node, nil
}

// heartbeatLoop sends periodic heartbeats to maintain node status
func (mn *MeshNetwork) heartbeatLoop() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-mn.ctx.Done():
			return
		case <-ticker.C:
			mn.sendHeartbeat()
		}
	}
}

// sendHeartbeat updates node status in database
func (mn *MeshNetwork) sendHeartbeat() {
	mn.mu.RLock()
	currentConnections := len(mn.activeConnections)
	mn.mu.RUnlock()

	_, err := mn.db.Exec(`
		UPDATE mesh_nodes
		SET 
			current_connections = $2,
			is_online = TRUE,
			last_heartbeat_at = NOW(),
			updated_at = NOW()
		WHERE node_id = $1
	`, mn.localNode.NodeID, currentConnections)

	if err != nil {
		log.Printf("Failed to send heartbeat: %v", err)
	}
}

// monitorConnections monitors and cleans up stale connections
func (mn *MeshNetwork) monitorConnections() {
	ticker := time.NewTicker(60 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-mn.ctx.Done():
			return
		case <-ticker.C:
			mn.cleanupStaleConnections()
		}
	}
}

// cleanupStaleConnections removes inactive connections
func (mn *MeshNetwork) cleanupStaleConnections() {
	mn.mu.Lock()
	defer mn.mu.Unlock()

	now := time.Now()
	for connID, conn := range mn.activeConnections {
		// Remove connections older than 5 minutes without activity
		if now.Sub(conn.EstablishedAt) > 5*time.Minute && conn.Status != "active" {
			delete(mn.activeConnections, connID)
			log.Printf("Cleaned up stale connection: %s", connID)
		}
	}
}

// EstablishP2PConnection establishes a P2P connection to another node
func (mn *MeshNetwork) EstablishP2PConnection(targetAuraID string, requireAIC bool) (*P2PConnection, error) {
	// Request optimal route from AI Core
	route, err := mn.requestOptimalRoute(mn.localNode.AuraID, targetAuraID, requireAIC)
	if err != nil {
		return nil, fmt.Errorf("failed to get optimal route: %w", err)
	}

	if route == nil {
		return nil, fmt.Errorf("no route available to target")
	}

	// Create connection
	connectionID := uuid.New().String()
	conn := &P2PConnection{
		ConnectionID:  connectionID,
		SourceNodeID:  mn.localNode.NodeID,
		TargetNodeID:  route.DestinationNodeID,
		RouteID:       route.RouteID,
		Status:        "establishing",
		EstablishedAt: time.Now(),
	}

	// Store in active connections
	mn.mu.Lock()
	mn.activeConnections[connectionID] = conn
	mn.mu.Unlock()

	// Establish actual P2P WebRTC connection with ICE/STUN/TURN
	if err := mn.establishWebRTCConnection(conn, route); err != nil {
		mn.mu.Lock()
		delete(mn.activeConnections, connectionID)
		mn.mu.Unlock()
		return nil, fmt.Errorf("failed to establish WebRTC connection: %w", err)
	}

	conn.Status = "active"

	log.Printf("Established P2P connection %s via route %s", connectionID, route.RouteID)

	return conn, nil
}

// establishWebRTCConnection establishes real WebRTC P2P connection with ICE/STUN/TURN
func (mn *MeshNetwork) establishWebRTCConnection(conn *P2PConnection, route *MeshRoute) error {
	// Create WebRTC peer connection configuration
	config := webrtc.Configuration{
		ICEServers: mn.iceServers,
	}

	// Create peer connection
	peerConnection, err := webrtc.NewPeerConnection(config)
	if err != nil {
		return fmt.Errorf("failed to create peer connection: %w", err)
	}

	// Store peer connection
	conn.PeerConnection = peerConnection

	// Handle ICE connection state changes
	peerConnection.OnICEConnectionStateChange(func(state webrtc.ICEConnectionState) {
		log.Printf("ICE Connection State for %s: %s", conn.ConnectionID, state.String())
		
		switch state {
		case webrtc.ICEConnectionStateConnected:
			conn.Status = "active"
			log.Printf("P2P connection %s established", conn.ConnectionID)
		case webrtc.ICEConnectionStateFailed:
			conn.Status = "failed"
			log.Printf("P2P connection %s failed", conn.ConnectionID)
			mn.TerminateConnection(conn.ConnectionID)
		case webrtc.ICEConnectionStateDisconnected:
			conn.Status = "disconnected"
			log.Printf("P2P connection %s disconnected", conn.ConnectionID)
		case webrtc.ICEConnectionStateClosed:
			conn.Status = "closed"
		}
	})

	// Handle ICE candidates
	peerConnection.OnICECandidate(func(candidate *webrtc.ICECandidate) {
		if candidate == nil {
			return
		}
		log.Printf("New ICE candidate: %s", candidate.String())
		// In production, send candidate to signaling server
		// For mesh network, we'd use the route path to relay candidates
	})

	// Create data channel for mesh signaling
	dataChannelOptions := &webrtc.DataChannelInit{
		Ordered: func() *bool { b := true; return &b }(),
	}
	
	dataChannel, err := peerConnection.CreateDataChannel("mesh", dataChannelOptions)
	if err != nil {
		peerConnection.Close()
		return fmt.Errorf("failed to create data channel: %w", err)
	}

	conn.DataChannel = dataChannel

	// Handle data channel events
	dataChannel.OnOpen(func() {
		log.Printf("Data channel opened for connection %s", conn.ConnectionID)
		
		// Send initial handshake
		handshake := map[string]interface{}{
			"type":          "handshake",
			"node_id":       mn.localNode.NodeID,
			"aura_id":       mn.localNode.AuraID,
			"connection_id": conn.ConnectionID,
			"route_id":      conn.RouteID,
		}
		
		if data, err := json.Marshal(handshake); err == nil {
			dataChannel.SendText(string(data))
		}
	})

	dataChannel.OnMessage(func(msg webrtc.DataChannelMessage) {
		log.Printf("Received mesh message on connection %s: %s", conn.ConnectionID, string(msg.Data))
		// Handle mesh protocol messages
	})

	dataChannel.OnClose(func() {
		log.Printf("Data channel closed for connection %s", conn.ConnectionID)
	})

	// Create offer
	offer, err := peerConnection.CreateOffer(nil)
	if err != nil {
		peerConnection.Close()
		return fmt.Errorf("failed to create offer: %w", err)
	}

	// Set local description
	if err := peerConnection.SetLocalDescription(offer); err != nil {
		peerConnection.Close()
		return fmt.Errorf("failed to set local description: %w", err)
	}

	// In production, send offer through signaling server or relay nodes
	// For mesh network, use the route path to relay SDP offers
	log.Printf("WebRTC offer created for connection %s, awaiting answer...", conn.ConnectionID)

	// TODO: Implement signaling through mesh relay nodes
	// This would involve:
	// 1. Send SDP offer through route path
	// 2. Wait for SDP answer
	// 3. Exchange ICE candidates
	// 4. Wait for connection establishment

	return nil
}

// requestOptimalRoute requests an optimal route from the AI Core
func (mn *MeshNetwork) requestOptimalRoute(sourceAuraID, destAuraID string, requireAIC bool) (*MeshRoute, error) {
	// Call AI Core mesh routing API
	type RouteRequest struct {
		SourceAuraID      string `json:"source_aura_id"`
		DestinationAuraID string `json:"destination_aura_id"`
		MediaType         string `json:"media_type"`
		RequireAIC        bool   `json:"require_aic"`
	}

	reqBody := RouteRequest{
		SourceAuraID:      sourceAuraID,
		DestinationAuraID: destAuraID,
		MediaType:         "audio_video",
		RequireAIC:        requireAIC,
	}

	jsonData, err := json.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Call AI Core HTTP API
	client := &http.Client{Timeout: 5 * time.Second}
	req, err := http.NewRequest("POST", fmt.Sprintf("%s/api/v1/mesh/find-route", mn.aiCoreURL), bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		log.Printf("Failed to call AI Core routing service: %v, falling back to database", err)
		return mn.requestOptimalRouteFallback(sourceAuraID, destAuraID)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Printf("AI Core routing returned status %d, falling back to database", resp.StatusCode)
		return mn.requestOptimalRouteFallback(sourceAuraID, destAuraID)
	}

	var route MeshRoute
	if err := json.NewDecoder(resp.Body).Decode(&route); err != nil {
		return nil, fmt.Errorf("failed to decode route response: %w", err)
	}

	return &route, nil
}

// requestOptimalRouteFallback falls back to database query if AI Core is unavailable
func (mn *MeshNetwork) requestOptimalRouteFallback(sourceAuraID, destAuraID string) (*MeshRoute, error) {
	var route MeshRoute
	err := mn.db.QueryRow(`
		SELECT * FROM find_optimal_route(
			(SELECT node_id FROM mesh_nodes WHERE aura_id = $1 AND is_online = TRUE LIMIT 1),
			(SELECT node_id FROM mesh_nodes WHERE aura_id = $2 AND is_online = TRUE LIMIT 1)
		)
	`, sourceAuraID, destAuraID).Scan(
		&route.RouteID,
		&route.PathNodes,
		&route.PredictedLatencyMs,
		&route.AIScore,
	)

	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("no route available")
	}

	if err != nil {
		return nil, err
	}

	return &route, nil
}

// TerminateConnection terminates a P2P connection
func (mn *MeshNetwork) TerminateConnection(connectionID string) error {
	mn.mu.Lock()
	defer mn.mu.Unlock()

	conn, exists := mn.activeConnections[connectionID]
	if !exists {
		return fmt.Errorf("connection not found")
	}

	now := time.Now()
	conn.TerminatedAt = &now
	conn.Status = "terminated"

	delete(mn.activeConnections, connectionID)

	log.Printf("Terminated connection: %s", connectionID)

	return nil
}

// UpdateMetrics updates node performance metrics
func (mn *MeshNetwork) UpdateMetrics(latencyMs float64, packetLossRate float64, bandwidthUsageMbps int) error {
	_, err := mn.db.Exec(`
		UPDATE mesh_nodes
		SET 
			avg_latency_ms = $2,
			packet_loss_rate = $3,
			current_bandwidth_usage_mbps = $4,
			updated_at = NOW()
		WHERE node_id = $1
	`, mn.localNode.NodeID, latencyMs, packetLossRate, bandwidthUsageMbps)

	return err
}

// GetNodeInfo returns information about the local node
func (mn *MeshNetwork) GetNodeInfo() *MeshNode {
	mn.mu.RLock()
	defer mn.mu.RUnlock()

	node := *mn.localNode
	node.CurrentConnections = len(mn.activeConnections)

	return &node
}

// GetActiveConnections returns all active P2P connections
func (mn *MeshNetwork) GetActiveConnections() []*P2PConnection {
	mn.mu.RLock()
	defer mn.mu.RUnlock()

	connections := make([]*P2PConnection, 0, len(mn.activeConnections))
	for _, conn := range mn.activeConnections {
		connections = append(connections, conn)
	}

	return connections
}

// ReportAbuseEvent reports an abuse event for reputation tracking
func (mn *MeshNetwork) ReportAbuseEvent(targetNodeID string, eventType string, description string) error {
	reportID := uuid.New().String()

	_, err := mn.db.Exec(`
		INSERT INTO abuse_reports (
			report_id, reporter_aura_id, reported_node_id, report_type, description, status
		) VALUES ($1, $2, $3, $4, $5, $6)
	`, reportID, mn.localNode.AuraID, targetNodeID, eventType, description, "pending")

	if err != nil {
		return err
	}

	// Also update reputation immediately for critical events
	if eventType == "malicious_node" || eventType == "security_threat" {
		_, err = mn.db.Exec(`
			SELECT update_node_reputation($1, $2, $3, $4)
		`, targetNodeID, eventType, -10.0, description)

		if err != nil {
			log.Printf("Failed to update reputation: %v", err)
		}
	}

	return nil
}

// Shutdown gracefully shuts down the mesh network
func (mn *MeshNetwork) Shutdown() error {
	log.Printf("Shutting down mesh network for node %s", mn.localNode.NodeID)

	// Cancel context
	mn.cancel()

	// Terminate all connections
	mn.mu.Lock()
	for connID := range mn.activeConnections {
		mn.TerminateConnection(connID)
	}
	mn.mu.Unlock()

	// Mark node as offline
	_, err := mn.db.Exec(`
		UPDATE mesh_nodes
		SET 
			is_online = FALSE,
			is_accepting_connections = FALSE,
			updated_at = NOW()
		WHERE node_id = $1
	`, mn.localNode.NodeID)

	return err
}

// MarshalJSON custom JSON marshaling for route
func (mr *MeshRoute) MarshalJSON() ([]byte, error) {
	type Alias MeshRoute
	return json.Marshal(&struct {
		*Alias
		PathNodes []string `json:"path_nodes"`
	}{
		Alias:     (*Alias)(mr),
		PathNodes: mr.PathNodes,
	})
}
