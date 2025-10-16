// ================================================================
// AuraLink Mesh Network - Dashboard APIs
// ================================================================
// Purpose: REST APIs for mesh network management and monitoring
// Phase 6: Enterprise-grade mesh networking
// ================================================================

package api

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/gorilla/mux"
)

// ================================================================
// Request/Response Types
// ================================================================

// MeshNodeResponse represents a mesh node
type MeshNodeResponse struct {
	NodeID                  string    `json:"node_id"`
	AuraID                  string    `json:"aura_id"`
	NodeAddress             string    `json:"node_address"`
	NodeType                string    `json:"node_type"`
	Region                  string    `json:"region"`
	CountryCode             string    `json:"country_code"`
	IsOnline                bool      `json:"is_online"`
	ReputationScore         float64   `json:"reputation_score"`
	TrustLevel              string    `json:"trust_level"`
	CurrentConnections      int       `json:"current_connections"`
	MaxConnections          int       `json:"max_connections"`
	BandwidthCapacityMbps   int       `json:"bandwidth_capacity_mbps"`
	AvgLatencyMs            float64   `json:"avg_latency_ms"`
	UptimePercentage        float64   `json:"uptime_percentage"`
	SupportsAICProtocol     bool      `json:"supports_aic_protocol"`
	LastHeartbeatAt         time.Time `json:"last_heartbeat_at"`
	CreatedAt               time.Time `json:"created_at"`
}

// MeshRouteResponse represents a mesh route
type MeshRouteResponse struct {
	RouteID               string    `json:"route_id"`
	SourceNodeID          string    `json:"source_node_id"`
	DestinationNodeID     string    `json:"destination_node_id"`
	PathLength            int       `json:"path_length"`
	AIScore               float64   `json:"ai_score"`
	PredictedLatencyMs    int       `json:"predicted_latency_ms"`
	ActualLatencyMs       *int      `json:"actual_latency_ms,omitempty"`
	PredictedBandwidthMbps int      `json:"predicted_bandwidth_mbps"`
	IsOptimal             bool      `json:"is_optimal"`
	IsActive              bool      `json:"is_active"`
	SuccessRate           float64   `json:"success_rate"`
	UsageCount            int       `json:"usage_count"`
	CreatedAt             time.Time `json:"created_at"`
}

// ReputationHistoryResponse represents reputation events
type ReputationHistoryResponse struct {
	EventID          string    `json:"event_id"`
	EventType        string    `json:"event_type"`
	EventSeverity    string    `json:"event_severity"`
	ReputationChange float64   `json:"reputation_change"`
	PreviousScore    float64   `json:"previous_score"`
	NewScore         float64   `json:"new_score"`
	Description      string    `json:"description"`
	CreatedAt        time.Time `json:"created_at"`
}

// AbuseReportRequest represents an abuse report submission
type AbuseReportRequest struct {
	ReportedAuraID string                 `json:"reported_aura_id"`
	ReportedNodeID string                 `json:"reported_node_id"`
	ReportType     string                 `json:"report_type"`
	Severity       string                 `json:"severity"`
	Description    string                 `json:"description"`
	Evidence       map[string]interface{} `json:"evidence"`
}

// MeshStatsResponse represents mesh network statistics
type MeshStatsResponse struct {
	TotalNodes        int                `json:"total_nodes"`
	OnlineNodes       int                `json:"online_nodes"`
	TotalRoutes       int                `json:"total_routes"`
	ActiveRoutes      int                `json:"active_routes"`
	AvgAIScore        float64            `json:"avg_ai_score"`
	AvgLatency        float64            `json:"avg_latency"`
	TrustDistribution map[string]int     `json:"trust_distribution"`
	RegionDistribution map[string]int    `json:"region_distribution"`
}

// ================================================================
// Mesh Node Endpoints
// ================================================================

// GetMyMeshNodes retrieves mesh nodes for the current user
func (h *Handler) GetMyMeshNodes(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value("user_id").(string)

	// Get user's AuraID
	var auraID string
	err := h.DB.QueryRow(`
		SELECT aura_id FROM users WHERE user_id = $1
	`, userID).Scan(&auraID)

	if err != nil {
		http.Error(w, "User AuraID not found", http.StatusNotFound)
		return
	}

	rows, err := h.DB.Query(`
		SELECT 
			node_id, aura_id, node_address, node_type, region, country_code,
			is_online, reputation_score, trust_level, current_connections,
			max_connections, bandwidth_capacity_mbps, avg_latency_ms,
			uptime_percentage, supports_aic_protocol, last_heartbeat_at, created_at
		FROM mesh_nodes
		WHERE aura_id = $1
		ORDER BY created_at DESC
	`, auraID)

	if err != nil {
		http.Error(w, "Failed to fetch mesh nodes", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	nodes := []MeshNodeResponse{}
	for rows.Next() {
		var node MeshNodeResponse
		err := rows.Scan(
			&node.NodeID, &node.AuraID, &node.NodeAddress, &node.NodeType,
			&node.Region, &node.CountryCode, &node.IsOnline, &node.ReputationScore,
			&node.TrustLevel, &node.CurrentConnections, &node.MaxConnections,
			&node.BandwidthCapacityMbps, &node.AvgLatencyMs, &node.UptimePercentage,
			&node.SupportsAICProtocol, &node.LastHeartbeatAt, &node.CreatedAt,
		)
		if err != nil {
			continue
		}
		nodes = append(nodes, node)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"nodes": nodes,
		"count": len(nodes),
	})
}

// GetMeshNodeByID retrieves a specific mesh node
func (h *Handler) GetMeshNodeByID(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	nodeID := vars["node_id"]

	var node MeshNodeResponse
	err := h.DB.QueryRow(`
		SELECT 
			node_id, aura_id, node_address, node_type, region, country_code,
			is_online, reputation_score, trust_level, current_connections,
			max_connections, bandwidth_capacity_mbps, avg_latency_ms,
			uptime_percentage, supports_aic_protocol, last_heartbeat_at, created_at
		FROM mesh_nodes
		WHERE node_id = $1
	`, nodeID).Scan(
		&node.NodeID, &node.AuraID, &node.NodeAddress, &node.NodeType,
		&node.Region, &node.CountryCode, &node.IsOnline, &node.ReputationScore,
		&node.TrustLevel, &node.CurrentConnections, &node.MaxConnections,
		&node.BandwidthCapacityMbps, &node.AvgLatencyMs, &node.UptimePercentage,
		&node.SupportsAICProtocol, &node.LastHeartbeatAt, &node.CreatedAt,
	)

	if err == sql.ErrNoRows {
		http.Error(w, "Node not found", http.StatusNotFound)
		return
	}

	if err != nil {
		http.Error(w, "Failed to fetch node", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(node)
}

// ================================================================
// Route Endpoints
// ================================================================

// GetMeshRoutes retrieves mesh routes
func (h *Handler) GetMeshRoutes(w http.ResponseWriter, r *http.Request) {
	limitStr := r.URL.Query().Get("limit")
	limit := 50
	if limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil && l > 0 && l <= 200 {
			limit = l
		}
	}

	activeOnly := r.URL.Query().Get("active_only") == "true"

	query := `
		SELECT 
			route_id, source_node_id, destination_node_id, path_length,
			ai_score, predicted_latency_ms, actual_latency_ms,
			predicted_bandwidth_mbps, is_optimal, is_active,
			success_rate, usage_count, created_at
		FROM mesh_routes
		WHERE 1=1
	`

	if activeOnly {
		query += " AND is_active = TRUE AND expires_at > NOW()"
	}

	query += " ORDER BY created_at DESC LIMIT $1"

	rows, err := h.DB.Query(query, limit)
	if err != nil {
		http.Error(w, "Failed to fetch routes", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	routes := []MeshRouteResponse{}
	for rows.Next() {
		var route MeshRouteResponse
		err := rows.Scan(
			&route.RouteID, &route.SourceNodeID, &route.DestinationNodeID,
			&route.PathLength, &route.AIScore, &route.PredictedLatencyMs,
			&route.ActualLatencyMs, &route.PredictedBandwidthMbps,
			&route.IsOptimal, &route.IsActive, &route.SuccessRate,
			&route.UsageCount, &route.CreatedAt,
		)
		if err != nil {
			continue
		}
		routes = append(routes, route)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"routes": routes,
		"count":  len(routes),
	})
}

// ================================================================
// Reputation Endpoints
// ================================================================

// GetNodeReputationHistory retrieves reputation history for a node
func (h *Handler) GetNodeReputationHistory(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	nodeID := vars["node_id"]

	limitStr := r.URL.Query().Get("limit")
	limit := 50
	if limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil && l > 0 && l <= 200 {
			limit = l
		}
	}

	rows, err := h.DB.Query(`
		SELECT 
			event_id, event_type, event_severity, reputation_change,
			previous_score, new_score, description, created_at
		FROM node_reputation_events
		WHERE node_id = $1
		ORDER BY created_at DESC
		LIMIT $2
	`, nodeID, limit)

	if err != nil {
		http.Error(w, "Failed to fetch reputation history", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	events := []ReputationHistoryResponse{}
	for rows.Next() {
		var event ReputationHistoryResponse
		err := rows.Scan(
			&event.EventID, &event.EventType, &event.EventSeverity,
			&event.ReputationChange, &event.PreviousScore, &event.NewScore,
			&event.Description, &event.CreatedAt,
		)
		if err != nil {
			continue
		}
		events = append(events, event)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"events": events,
		"count":  len(events),
	})
}

// SubmitAbuseReport submits an abuse report
func (h *Handler) SubmitAbuseReport(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value("user_id").(string)

	// Get reporter's AuraID
	var reporterAuraID string
	err := h.DB.QueryRow(`
		SELECT aura_id FROM users WHERE user_id = $1
	`, userID).Scan(&reporterAuraID)

	if err != nil {
		http.Error(w, "User AuraID not found", http.StatusNotFound)
		return
	}

	var req AbuseReportRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate fields
	if req.ReportType == "" || req.Description == "" {
		http.Error(w, "report_type and description are required", http.StatusBadRequest)
		return
	}

	evidenceJSON, _ := json.Marshal(req.Evidence)

	// Create report
	var reportID string
	err = h.DB.QueryRow(`
		INSERT INTO abuse_reports (
			reporter_aura_id, reported_aura_id, reported_node_id,
			report_type, severity, description, evidence, status
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		RETURNING report_id
	`, reporterAuraID, req.ReportedAuraID, req.ReportedNodeID,
		req.ReportType, req.Severity, req.Description, evidenceJSON, "pending").Scan(&reportID)

	if err != nil {
		http.Error(w, "Failed to create abuse report", http.StatusInternalServerError)
		return
	}

	// Log audit event
	h.logFederationAudit("abuse_report_submitted", "security", reporterAuraID,
		req.ReportedAuraID, "", "", 
		fmt.Sprintf("Abuse report filed: %s", req.ReportType),
		map[string]interface{}{"report_id": reportID, "report_type": req.ReportType},
		"success", "")

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"report_id": reportID,
		"status":    "pending",
		"message":   "Abuse report submitted successfully",
	})
}

// ================================================================
// Statistics Endpoints
// ================================================================

// GetMeshStatistics retrieves mesh network statistics
func (h *Handler) GetMeshStatistics(w http.ResponseWriter, r *http.Request) {
	var stats MeshStatsResponse

	// Get node counts
	h.DB.QueryRow(`
		SELECT 
			COUNT(*) as total,
			COUNT(*) FILTER (WHERE is_online = TRUE) as online
		FROM mesh_nodes
	`).Scan(&stats.TotalNodes, &stats.OnlineNodes)

	// Get route counts
	h.DB.QueryRow(`
		SELECT 
			COUNT(*) as total,
			COUNT(*) FILTER (WHERE is_active = TRUE AND expires_at > NOW()) as active,
			AVG(ai_score) as avg_score,
			AVG(predicted_latency_ms) as avg_latency
		FROM mesh_routes
	`).Scan(&stats.TotalRoutes, &stats.ActiveRoutes, &stats.AvgAIScore, &stats.AvgLatency)

	// Get trust distribution
	trustRows, err := h.DB.Query(`
		SELECT trust_level, COUNT(*) as count
		FROM mesh_nodes
		WHERE is_online = TRUE
		GROUP BY trust_level
	`)
	if err == nil {
		defer trustRows.Close()
		stats.TrustDistribution = make(map[string]int)
		for trustRows.Next() {
			var level string
			var count int
			trustRows.Scan(&level, &count)
			stats.TrustDistribution[level] = count
		}
	}

	// Get region distribution
	regionRows, err := h.DB.Query(`
		SELECT region, COUNT(*) as count
		FROM mesh_nodes
		WHERE is_online = TRUE AND region IS NOT NULL
		GROUP BY region
		ORDER BY count DESC
		LIMIT 10
	`)
	if err == nil {
		defer regionRows.Close()
		stats.RegionDistribution = make(map[string]int)
		for regionRows.Next() {
			var region string
			var count int
			regionRows.Scan(&region, &count)
			stats.RegionDistribution[region] = count
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(stats)
}

// GetMeshHealth checks mesh network health
func (h *Handler) GetMeshHealth(w http.ResponseWriter, r *http.Request) {
	var onlineNodes, totalNodes, activeRoutes int
	var avgReputation float64

	h.DB.QueryRow(`
		SELECT 
			COUNT(*) FILTER (WHERE is_online = TRUE),
			COUNT(*),
			AVG(reputation_score) FILTER (WHERE is_online = TRUE)
		FROM mesh_nodes
	`).Scan(&onlineNodes, &totalNodes, &avgReputation)

	h.DB.QueryRow(`
		SELECT COUNT(*)
		FROM mesh_routes
		WHERE is_active = TRUE AND expires_at > NOW()
	`).Scan(&activeRoutes)

	health := "healthy"
	if onlineNodes < totalNodes/2 {
		health = "degraded"
	}
	if onlineNodes < totalNodes/4 {
		health = "unhealthy"
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":           health,
		"online_nodes":     onlineNodes,
		"total_nodes":      totalNodes,
		"active_routes":    activeRoutes,
		"avg_reputation":   avgReputation,
		"timestamp":        time.Now(),
	})
}
