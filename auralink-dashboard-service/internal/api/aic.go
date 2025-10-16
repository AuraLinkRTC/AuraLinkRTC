// ================================================================
// AuraLink AIC Protocol - Dashboard APIs
// ================================================================
// Purpose: REST APIs for AIC Protocol control and monitoring
// Dependencies: Database, AI Core HTTP APIs
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

// AICConfigRequest represents request to update AIC configuration
type AICConfigRequest struct {
	Enabled                      bool    `json:"enabled"`
	Mode                         string  `json:"mode"` // conservative, adaptive, aggressive, off
	TargetCompressionRatio       float64 `json:"target_compression_ratio"`
	MaxLatencyMs                 int     `json:"max_latency_ms"`
	ModelType                    string  `json:"model_type"` // encodec, lyra, maxine, hybrid
	MinQualityScore              float64 `json:"min_quality_score"`
	EnablePredictiveCompression  bool    `json:"enable_predictive_compression"`
	EnablePerceptualOptimization bool    `json:"enable_perceptual_optimization"`
	OptOut                       bool    `json:"opt_out"`
}

// AICConfigResponse represents AIC configuration
type AICConfigResponse struct {
	ConfigID               string    `json:"config_id"`
	UserID                 string    `json:"user_id"`
	Enabled                bool      `json:"enabled"`
	Mode                   string    `json:"mode"`
	TargetCompressionRatio float64   `json:"target_compression_ratio"`
	MaxLatencyMs           int       `json:"max_latency_ms"`
	ModelType              string    `json:"model_type"`
	ModelVersion           string    `json:"model_version"`
	MinQualityScore        float64   `json:"min_quality_score"`
	CreatedAt              time.Time `json:"created_at"`
	UpdatedAt              time.Time `json:"updated_at"`
}

// CompressionMetric represents a single compression metric
type CompressionMetric struct {
	MetricID                string    `json:"metric_id"`
	CallID                  string    `json:"call_id"`
	ParticipantID           string    `json:"participant_id"`
	OriginalBandwidthKbps   int       `json:"original_bandwidth_kbps"`
	CompressedBandwidthKbps int       `json:"compressed_bandwidth_kbps"`
	CompressionRatio        float64   `json:"compression_ratio"`
	BandwidthSavingsPercent float64   `json:"bandwidth_savings_percent"`
	InferenceLatencyMs      float64   `json:"inference_latency_ms"`
	QualityScore            float64   `json:"quality_score"`
	PSNRDb                  *float64  `json:"psnr_db,omitempty"`
	ModelUsed               string    `json:"model_used"`
	FallbackTriggered       bool      `json:"fallback_triggered"`
	Timestamp               time.Time `json:"timestamp"`
}

// PerformanceSummary represents aggregated performance metrics
type PerformanceSummary struct {
	TotalFrames          int     `json:"total_frames"`
	AvgCompressionRatio  float64 `json:"avg_compression_ratio"`
	AvgBandwidthSavings  float64 `json:"avg_bandwidth_savings"`
	AvgInferenceLatency  float64 `json:"avg_inference_latency"`
	AvgQualityScore      float64 `json:"avg_quality_score"`
	FallbackCount        int     `json:"fallback_count"`
	FallbackRatePercent  float64 `json:"fallback_rate_percent"`
}

// BandwidthSavingsResponse represents bandwidth savings calculation
type BandwidthSavingsResponse struct {
	TotalSavedMB              float64 `json:"total_saved_mb"`
	TotalSavedGB              float64 `json:"total_saved_gb"`
	AvgSavingsPercent         float64 `json:"avg_savings_percent"`
	TotalFrames               int     `json:"total_frames"`
	EstimatedCostSavingsUSD   float64 `json:"estimated_cost_savings_usd"`
	PeriodDays                int     `json:"period_days"`
}

// ================================================================
// AIC Configuration Endpoints
// ================================================================

// UpdateAICConfig updates AIC configuration for user
func UpdateAICConfig(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := GetUserIDFromContext(r)

	var req AICConfigRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		RespondError(w, http.StatusBadRequest, "INVALID_REQUEST", "Invalid request body", nil)
		return
	}

	// Validate input
	if req.Mode != "conservative" && req.Mode != "adaptive" && req.Mode != "aggressive" && req.Mode != "off" {
		RespondError(w, http.StatusBadRequest, "INVALID_MODE", "Mode must be conservative, adaptive, aggressive, or off", nil)
		return
	}

	if req.TargetCompressionRatio < 0.1 || req.TargetCompressionRatio > 0.95 {
		RespondError(w, http.StatusBadRequest, "INVALID_RATIO", "Compression ratio must be between 0.1 and 0.95", nil)
		return
	}

	// Check if config exists
	var existingConfigID string
	err := s.db.QueryRowContext(ctx,
		"SELECT config_id FROM aic_configs WHERE user_id = $1",
		userID,
	).Scan(&existingConfigID)

	var config AICConfigResponse

	if err == sql.ErrNoRows {
		// Create new config
		err = s.db.QueryRowContext(ctx, `
			INSERT INTO aic_configs (
				user_id, enabled, mode, target_compression_ratio,
				max_latency_ms, model_type, min_quality_score,
				enable_predictive_compression, enable_perceptual_optimization, opt_out
			)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
			RETURNING config_id, user_id, enabled, mode, target_compression_ratio,
			         max_latency_ms, model_type, model_version, min_quality_score,
			         created_at, updated_at
		`,
			userID, req.Enabled, req.Mode, req.TargetCompressionRatio,
			req.MaxLatencyMs, req.ModelType, req.MinQualityScore,
			req.EnablePredictiveCompression, req.EnablePerceptualOptimization, req.OptOut,
		).Scan(
			&config.ConfigID, &config.UserID, &config.Enabled, &config.Mode,
			&config.TargetCompressionRatio, &config.MaxLatencyMs, &config.ModelType,
			&config.ModelVersion, &config.MinQualityScore, &config.CreatedAt, &config.UpdatedAt,
		)
	} else if err == nil {
		// Update existing config
		err = s.db.QueryRowContext(ctx, `
			UPDATE aic_configs SET
				enabled = $1,
				mode = $2,
				target_compression_ratio = $3,
				max_latency_ms = $4,
				model_type = $5,
				min_quality_score = $6,
				enable_predictive_compression = $7,
				enable_perceptual_optimization = $8,
				opt_out = $9,
				updated_at = NOW()
			WHERE user_id = $10
			RETURNING config_id, user_id, enabled, mode, target_compression_ratio,
			         max_latency_ms, model_type, model_version, min_quality_score,
			         created_at, updated_at
		`,
			req.Enabled, req.Mode, req.TargetCompressionRatio,
			req.MaxLatencyMs, req.ModelType, req.MinQualityScore,
			req.EnablePredictiveCompression, req.EnablePerceptualOptimization,
			req.OptOut, userID,
		).Scan(
			&config.ConfigID, &config.UserID, &config.Enabled, &config.Mode,
			&config.TargetCompressionRatio, &config.MaxLatencyMs, &config.ModelType,
			&config.ModelVersion, &config.MinQualityScore, &config.CreatedAt, &config.UpdatedAt,
		)
	}

	if err != nil {
		s.logger.Printf("Error updating AIC config: %v", err)
		RespondError(w, http.StatusInternalServerError, "DATABASE_ERROR", "Failed to update configuration", nil)
		return
	}

	s.logger.Printf("AIC config updated for user %s: enabled=%v, mode=%s", userID, req.Enabled, req.Mode)
	RespondJSON(w, http.StatusOK, config)
}

// GetAICConfig retrieves AIC configuration for user
func GetAICConfig(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := GetUserIDFromContext(r)

	var config AICConfigResponse
	err := s.db.QueryRowContext(ctx, `
		SELECT config_id, user_id, enabled, mode, target_compression_ratio,
		       max_latency_ms, model_type, model_version, min_quality_score,
		       created_at, updated_at
		FROM aic_configs
		WHERE user_id = $1
	`, userID).Scan(
		&config.ConfigID, &config.UserID, &config.Enabled, &config.Mode,
		&config.TargetCompressionRatio, &config.MaxLatencyMs, &config.ModelType,
		&config.ModelVersion, &config.MinQualityScore, &config.CreatedAt, &config.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		// Return default config
		config = AICConfigResponse{
			ConfigID:               "default",
			UserID:                 userID,
			Enabled:                false,
			Mode:                   "adaptive",
			TargetCompressionRatio: 0.80,
			MaxLatencyMs:           20,
			ModelType:              "encodec",
			ModelVersion:           "v1.0",
			MinQualityScore:        0.85,
			CreatedAt:              time.Now(),
			UpdatedAt:              time.Now(),
		}
		RespondJSON(w, http.StatusOK, config)
		return
	}

	if err != nil {
		s.logger.Printf("Error fetching AIC config: %v", err)
		RespondError(w, http.StatusInternalServerError, "DATABASE_ERROR", "Failed to fetch configuration", nil)
		return
	}

	RespondJSON(w, http.StatusOK, config)
}

// ================================================================
// Metrics Endpoints
// ================================================================

// GetCompressionMetrics retrieves compression metrics
func GetCompressionMetrics(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := GetUserIDFromContext(r)

	// Parse query parameters
	callID := r.URL.Query().Get("call_id")
	limitStr := r.URL.Query().Get("limit")
	
	limit := 100
	if limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil && l > 0 && l <= 1000 {
			limit = l
		}
	}

	// Build query
	query := `
		SELECT m.metric_id, m.call_id, m.participant_id,
		       m.original_bandwidth_kbps, m.compressed_bandwidth_kbps,
		       m.compression_ratio, m.bandwidth_savings_percent,
		       m.inference_latency_ms, m.quality_score, m.psnr_db,
		       m.model_used, m.fallback_triggered, m.timestamp
		FROM aic_metrics m
		JOIN call_participants cp ON m.participant_id = cp.participant_id
		WHERE cp.identity = $1
	`
	args := []interface{}{userID}

	if callID != "" {
		query += " AND m.call_id = $2"
		args = append(args, callID)
	}

	query += fmt.Sprintf(" ORDER BY m.timestamp DESC LIMIT $%d", len(args)+1)
	args = append(args, limit)

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		s.logger.Printf("Error fetching metrics: %v", err)
		RespondError(w, http.StatusInternalServerError, "DATABASE_ERROR", "Failed to fetch metrics", nil)
		return
	}
	defer rows.Close()

	metrics := []CompressionMetric{}
	for rows.Next() {
		var m CompressionMetric
		err := rows.Scan(
			&m.MetricID, &m.CallID, &m.ParticipantID,
			&m.OriginalBandwidthKbps, &m.CompressedBandwidthKbps,
			&m.CompressionRatio, &m.BandwidthSavingsPercent,
			&m.InferenceLatencyMs, &m.QualityScore, &m.PSNRDb,
			&m.ModelUsed, &m.FallbackTriggered, &m.Timestamp,
		)
		if err != nil {
			s.logger.Printf("Error scanning metric: %v", err)
			continue
		}
		metrics = append(metrics, m)
	}

	RespondJSON(w, http.StatusOK, metrics)
}

// GetPerformanceSummary retrieves performance summary
func GetPerformanceSummary(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := GetUserIDFromContext(r)

	hoursStr := r.URL.Query().Get("hours")
	hours := 24
	if hoursStr != "" {
		if h, err := strconv.Atoi(hoursStr); err == nil && h > 0 && h <= 168 {
			hours = h
		}
	}

	since := time.Now().Add(-time.Duration(hours) * time.Hour)

	var summary PerformanceSummary
	err := s.db.QueryRowContext(ctx, `
		SELECT
			COALESCE(COUNT(*), 0) as total_frames,
			COALESCE(AVG(compression_ratio), 0) as avg_compression_ratio,
			COALESCE(AVG(bandwidth_savings_percent), 0) as avg_bandwidth_savings,
			COALESCE(AVG(inference_latency_ms), 0) as avg_inference_latency,
			COALESCE(AVG(quality_score), 0) as avg_quality_score,
			COALESCE(SUM(CASE WHEN fallback_triggered THEN 1 ELSE 0 END), 0) as fallback_count,
			COALESCE(SUM(CASE WHEN fallback_triggered THEN 1 ELSE 0 END)::DECIMAL / 
				NULLIF(COUNT(*), 0) * 100, 0) as fallback_rate_percent
		FROM aic_metrics m
		JOIN call_participants cp ON m.participant_id = cp.participant_id
		WHERE cp.identity = $1 AND m.timestamp >= $2
	`, userID, since).Scan(
		&summary.TotalFrames, &summary.AvgCompressionRatio,
		&summary.AvgBandwidthSavings, &summary.AvgInferenceLatency,
		&summary.AvgQualityScore, &summary.FallbackCount,
		&summary.FallbackRatePercent,
	)

	if err != nil {
		s.logger.Printf("Error fetching performance summary: %v", err)
		RespondError(w, http.StatusInternalServerError, "DATABASE_ERROR", "Failed to fetch summary", nil)
		return
	}

	RespondJSON(w, http.StatusOK, summary)
}

// GetBandwidthSavings calculates total bandwidth savings
func GetBandwidthSavings(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := GetUserIDFromContext(r)

	daysStr := r.URL.Query().Get("days")
	days := 7
	if daysStr != "" {
		if d, err := strconv.Atoi(daysStr); err == nil && d > 0 && d <= 90 {
			days = d
		}
	}

	since := time.Now().Add(-time.Duration(days) * 24 * time.Hour)

	var totalMB float64
	var avgPercent float64
	var totalFrames int

	err := s.db.QueryRowContext(ctx, `
		SELECT
			COALESCE(SUM((original_bandwidth_kbps - compressed_bandwidth_kbps) * 1.0 / 8192), 0) as total_saved_mb,
			COALESCE(AVG(bandwidth_savings_percent), 0) as avg_savings_percent,
			COALESCE(COUNT(*), 0) as total_frames
		FROM aic_metrics m
		JOIN call_participants cp ON m.participant_id = cp.participant_id
		WHERE cp.identity = $1 AND m.timestamp >= $2
	`, userID, since).Scan(&totalMB, &avgPercent, &totalFrames)

	if err != nil {
		s.logger.Printf("Error calculating bandwidth savings: %v", err)
		RespondError(w, http.StatusInternalServerError, "DATABASE_ERROR", "Failed to calculate savings", nil)
		return
	}

	totalGB := totalMB / 1024
	estimatedSavings := totalGB * 0.10 // $0.10 per GB

	response := BandwidthSavingsResponse{
		TotalSavedMB:            totalMB,
		TotalSavedGB:            totalGB,
		AvgSavingsPercent:       avgPercent,
		TotalFrames:             totalFrames,
		EstimatedCostSavingsUSD: estimatedSavings,
		PeriodDays:              days,
	}

	RespondJSON(w, http.StatusOK, response)
}

// ================================================================
// Register Routes
// ================================================================

// RegisterAICRoutes registers AIC-related routes
func RegisterAICRoutes(router *mux.Router, server *Server) {
	// Configuration endpoints
	router.HandleFunc("/api/v1/aic/config", server.AuthMiddleware(server.GetAICConfig)).Methods("GET")
	router.HandleFunc("/api/v1/aic/config", server.AuthMiddleware(server.UpdateAICConfig)).Methods("POST")

	// Metrics endpoints
	router.HandleFunc("/api/v1/aic/metrics", server.AuthMiddleware(server.GetCompressionMetrics)).Methods("GET")
	router.HandleFunc("/api/v1/aic/performance/summary", server.AuthMiddleware(server.GetPerformanceSummary)).Methods("GET")
	router.HandleFunc("/api/v1/aic/stats/bandwidth-savings", server.AuthMiddleware(server.GetBandwidthSavings)).Methods("GET")
}
