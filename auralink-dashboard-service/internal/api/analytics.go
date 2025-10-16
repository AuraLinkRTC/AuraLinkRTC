// AuraLink Dashboard Service - Advanced Analytics
// Package api provides advanced analytics and reporting endpoints
package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/auralink/dashboard-service/internal/services"
	"github.com/auralink/shared/database"
	"github.com/gorilla/mux"
	"github.com/google/uuid"
)

// GetOrganizationAnalytics retrieves comprehensive organization analytics
func GetOrganizationAnalytics(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	orgID := vars["org_id"]
	period := r.URL.Query().Get("period") // daily, weekly, monthly, yearly

	if period == "" {
		period = "monthly"
	}

	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	// Calculate date range based on period
	var startDate time.Time
	endDate := time.Now()
	switch period {
	case "daily":
		startDate = endDate.AddDate(0, 0, -1)
	case "weekly":
		startDate = endDate.AddDate(0, 0, -7)
	case "yearly":
		startDate = endDate.AddDate(-1, 0, 0)
	default: // monthly
		startDate = endDate.AddDate(0, -1, 0)
	}

	// Query overview metrics
	query := `
		SELECT 
			COUNT(DISTINCT u.user_id) as total_users,
			COUNT(DISTINCT CASE WHEN u.last_active_at > NOW() - INTERVAL '7 days' THEN u.user_id END) as active_users,
			COUNT(c.call_id) as total_calls,
			COALESCE(SUM(EXTRACT(EPOCH FROM (c.ended_at - c.started_at))/60), 0) as total_minutes,
			COUNT(CASE WHEN c.aic_enabled = true THEN 1 END) as ai_enhanced_calls,
			COUNT(DISTINCT ag.agent_id) as total_agents,
			COALESCE(SUM(ai.cost_usd), 0) as total_cost_usd
		FROM organizations o
		LEFT JOIN users u ON u.organization_id = o.organization_id
		LEFT JOIN calls c ON c.organization_id = o.organization_id AND c.started_at >= $2
		LEFT JOIN ai_agents ag ON ag.organization_id = o.organization_id
		LEFT JOIN ai_usage_analytics ai ON ai.organization_id = o.organization_id AND ai.created_at >= $2
		WHERE o.organization_id = $1
		GROUP BY o.organization_id
	`

	var overview struct {
		TotalUsers       int
		ActiveUsers      int
		TotalCalls       int
		TotalMinutes     float64
		AIEnhancedCalls  int
		TotalAgents      int
		TotalCostUSD     float64
	}

	err := db.QueryRowContext(r.Context(), query, orgID, startDate).Scan(
		&overview.TotalUsers, &overview.ActiveUsers, &overview.TotalCalls,
		&overview.TotalMinutes, &overview.AIEnhancedCalls, &overview.TotalAgents,
		&overview.TotalCostUSD,
	)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to query analytics: %v", err), http.StatusInternalServerError)
		return
	}

	// Query call types
	callTypesQuery := `
		SELECT 
			SUM(CASE WHEN video_enabled = false AND screen_share_enabled = false THEN 1 ELSE 0 END) as audio_only,
			SUM(CASE WHEN video_enabled = true AND screen_share_enabled = false THEN 1 ELSE 0 END) as video,
			SUM(CASE WHEN screen_share_enabled = true THEN 1 ELSE 0 END) as screen_share
		FROM calls
		WHERE organization_id = $1 AND started_at >= $2
	`
	var audioOnly, video, screenShare int
	db.QueryRowContext(r.Context(), callTypesQuery, orgID, startDate).Scan(&audioOnly, &video, &screenShare)

	// Query AI feature usage
	aiUsageQuery := `
		SELECT 
			feature_type,
			COUNT(*) as usage_count,
			SUM(cost_usd) as total_cost
		FROM ai_usage_analytics
		WHERE organization_id = $1 AND created_at >= $2
		GROUP BY feature_type
	`
	aiUsageRows, _ := db.QueryContext(r.Context(), aiUsageQuery, orgID, startDate)
	aiByFeature := make(map[string]int)
	aiCostByFeature := make(map[string]float64)
	if aiUsageRows != nil {
		defer aiUsageRows.Close()
		for aiUsageRows.Next() {
			var featureType string
			var count int
			var cost float64
			if err := aiUsageRows.Scan(&featureType, &count, &cost); err == nil {
				aiByFeature[featureType] = count
				aiCostByFeature[featureType] = cost
			}
		}
	}

	// Query quality metrics from call_quality_analytics
	qualityQuery := `
		SELECT 
			AVG(audio_mos_score) as avg_mos,
			AVG(avg_latency_ms) as avg_latency,
			AVG(packet_loss_percentage) as avg_packet_loss,
			COUNT(CASE WHEN quality_issues_detected > 0 THEN 1 END) as issues_count
		FROM call_quality_analytics
		WHERE organization_id = $1 AND created_at >= $2
	`
	var avgMOS, avgLatency, avgPacketLoss float64
	var issuesCount int
	db.QueryRowContext(r.Context(), qualityQuery, orgID, startDate).Scan(
		&avgMOS, &avgLatency, &avgPacketLoss, &issuesCount,
	)

	// Query top users
	topUsersQuery := `
		SELECT u.user_id, u.email, u.display_name, COUNT(p.participant_id) as call_count
		FROM users u
		JOIN call_participants p ON p.user_id = u.user_id
		JOIN calls c ON c.call_id = p.call_id
		WHERE u.organization_id = $1 AND c.started_at >= $2
		GROUP BY u.user_id, u.email, u.display_name
		ORDER BY call_count DESC
		LIMIT 10
	`
	topUsersRows, _ := db.QueryContext(r.Context(), topUsersQuery, orgID, startDate)
	topUsers := []map[string]interface{}{}
	if topUsersRows != nil {
		defer topUsersRows.Close()
		for topUsersRows.Next() {
			var userID, email, displayName string
			var callCount int
			if err := topUsersRows.Scan(&userID, &email, &displayName, &callCount); err == nil {
				topUsers = append(topUsers, map[string]interface{}{
					"user_id":      userID,
					"email":        email,
					"display_name": displayName,
					"call_count":   callCount,
				})
			}
		}
	}

	analytics := map[string]interface{}{
		"organization_id": orgID,
		"period":          period,
		"date_range": map[string]string{
			"start": startDate.Format(time.RFC3339),
			"end":   endDate.Format(time.RFC3339),
		},
		"overview": map[string]interface{}{
			"total_users":       overview.TotalUsers,
			"active_users":      overview.ActiveUsers,
			"total_calls":       overview.TotalCalls,
			"total_minutes":     overview.TotalMinutes,
			"ai_enhanced_calls": overview.AIEnhancedCalls,
			"total_agents":      overview.TotalAgents,
			"total_cost_usd":    overview.TotalCostUSD,
		},
		"calls": map[string]interface{}{
			"by_type": map[string]int{
				"audio_only":   audioOnly,
				"video":        video,
				"screen_share": screenShare,
			},
			"average_duration_minutes": overview.TotalMinutes / float64(overview.TotalCalls),
		},
		"ai_usage": map[string]interface{}{
			"by_feature":       aiByFeature,
			"total_cost_usd":   overview.TotalCostUSD,
			"cost_by_feature": aiCostByFeature,
		},
		"quality": map[string]interface{}{
			"average_mos_score":    avgMOS,
			"average_latency_ms":   avgLatency,
			"average_packet_loss":  avgPacketLoss,
			"quality_issues_count": issuesCount,
		},
		"top_users": topUsers,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(analytics)
}

// GetCallQualityAnalytics retrieves call quality metrics
func GetCallQualityAnalytics(w http.ResponseWriter, r *http.Request) {
	orgID := r.URL.Query().Get("organization_id")
	callID := r.URL.Query().Get("call_id")
	startDate := r.URL.Query().Get("start_date")
	endDate := r.URL.Query().Get("end_date")

	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	// Build query based on filters
	whereClause := "WHERE 1=1"
	args := []interface{}{}
	argCount := 1

	if orgID != "" {
		whereClause += fmt.Sprintf(" AND organization_id = $%d", argCount)
		args = append(args, orgID)
		argCount++
	}
	if callID != "" {
		whereClause += fmt.Sprintf(" AND call_id = $%d", argCount)
		args = append(args, callID)
		argCount++
	}
	if startDate != "" {
		whereClause += fmt.Sprintf(" AND created_at >= $%d", argCount)
		args = append(args, startDate)
		argCount++
	}
	if endDate != "" {
		whereClause += fmt.Sprintf(" AND created_at <= $%d", argCount)
		args = append(args, endDate)
		argCount++
	}

	// Query call quality metrics
	query := `
		SELECT 
			AVG(avg_latency_ms) as avg_latency,
			MAX(max_latency_ms) as max_latency,
			AVG(avg_jitter_ms) as avg_jitter,
			AVG(packet_loss_percentage) as avg_packet_loss,
			AVG(avg_bitrate_kbps) as avg_bitrate,
			AVG(audio_mos_score) as avg_mos,
			AVG(CASE WHEN aic_enabled THEN 1 ELSE 0 END) * 100 as aic_percentage,
			COALESCE(SUM(aic_bandwidth_saved_mb), 0) as aic_bandwidth_saved
		FROM call_quality_analytics
		` + whereClause

	var metrics struct {
		AvgLatency         float64
		MaxLatency         float64
		AvgJitter          float64
		PacketLoss         float64
		AvgBitrate         float64
		AudioMOS           float64
		AICPercentage      float64
		AICBandwidthSaved  float64
	}

	err := db.QueryRowContext(r.Context(), query, args...).Scan(
		&metrics.AvgLatency, &metrics.MaxLatency, &metrics.AvgJitter,
		&metrics.PacketLoss, &metrics.AvgBitrate, &metrics.AudioMOS,
		&metrics.AICPercentage, &metrics.AICBandwidthSaved,
	)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to query quality analytics: %v", err), http.StatusInternalServerError)
		return
	}

	// Query by connection type
	connTypeQuery := `
		SELECT 
			connection_type,
			AVG(avg_latency_ms) as avg_latency,
			AVG(packet_loss_percentage) as avg_packet_loss,
			AVG(audio_mos_score) as avg_mos
		FROM call_quality_analytics
		` + whereClause + `
		GROUP BY connection_type
	`
	connRows, _ := db.QueryContext(r.Context(), connTypeQuery, args...)
	byConnectionType := make(map[string]interface{})
	if connRows != nil {
		defer connRows.Close()
		for connRows.Next() {
			var connType string
			var avgLat, packetLoss, mos float64
			if err := connRows.Scan(&connType, &avgLat, &packetLoss, &mos); err == nil {
				byConnectionType[connType] = map[string]interface{}{
					"avg_latency_ms":         avgLat,
					"packet_loss_percentage": packetLoss,
					"audio_mos_score":        mos,
				}
			}
		}
	}

	analytics := map[string]interface{}{
		"organization_id": orgID,
		"call_id":         callID,
		"period": map[string]string{
			"start": startDate,
			"end":   endDate,
		},
		"metrics": map[string]interface{}{
			"avg_latency_ms":         metrics.AvgLatency,
			"max_latency_ms":         metrics.MaxLatency,
			"avg_jitter_ms":          metrics.AvgJitter,
			"packet_loss_percentage": metrics.PacketLoss,
			"avg_bitrate_kbps":       metrics.AvgBitrate,
			"audio_mos_score":        metrics.AudioMOS,
			"aic_enabled_percentage": metrics.AICPercentage,
			"aic_bandwidth_saved_mb": metrics.AICBandwidthSaved,
		},
		"by_connection_type": byConnectionType,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(analytics)
}

// GetAIUsageAnalytics retrieves AI usage and cost analytics
func GetAIUsageAnalytics(w http.ResponseWriter, r *http.Request) {
	orgID := r.URL.Query().Get("organization_id")
	featureType := r.URL.Query().Get("feature_type")
	groupBy := r.URL.Query().Get("group_by") // day, week, month, feature, provider

	if groupBy == "" {
		groupBy = "day"
	}

	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	// Build where clause
	whereClause := "WHERE 1=1"
	args := []interface{}{}
	argCount := 1

	if orgID != "" {
		whereClause += fmt.Sprintf(" AND organization_id = $%d", argCount)
		args = append(args, orgID)
		argCount++
	}
	if featureType != "" {
		whereClause += fmt.Sprintf(" AND feature_type = $%d", argCount)
		args = append(args, featureType)
		argCount++
	}

	// Query summary
	summaryQuery := `
		SELECT 
			COUNT(*) as total_calls,
			COALESCE(SUM(tokens_used), 0) as total_tokens,
			COALESCE(SUM(audio_duration_seconds), 0) as total_audio_seconds,
			COALESCE(SUM(cost_usd), 0) as total_cost,
			AVG(latency_ms) as avg_latency,
			AVG(CASE WHEN status = 'success' THEN 1 ELSE 0 END) * 100 as success_rate
		FROM ai_usage_analytics
		` + whereClause

	var summary struct {
		TotalCalls        int
		TotalTokens       int
		TotalAudioSeconds int
		TotalCost         float64
		AvgLatency        float64
		SuccessRate       float64
	}

	db.QueryRowContext(r.Context(), summaryQuery, args...).Scan(
		&summary.TotalCalls, &summary.TotalTokens, &summary.TotalAudioSeconds,
		&summary.TotalCost, &summary.AvgLatency, &summary.SuccessRate,
	)

	// Query by feature
	featureQuery := `
		SELECT feature_type, COUNT(*) as calls, SUM(cost_usd) as cost
		FROM ai_usage_analytics
		` + whereClause + `
		GROUP BY feature_type
		ORDER BY cost DESC
	`
	featureRows, _ := db.QueryContext(r.Context(), featureQuery, args...)
	byFeature := []map[string]interface{}{}
	if featureRows != nil {
		defer featureRows.Close()
		for featureRows.Next() {
			var ft string
			var calls int
			var cost float64
			if err := featureRows.Scan(&ft, &calls, &cost); err == nil {
				byFeature = append(byFeature, map[string]interface{}{
					"feature_type": ft,
					"calls":        calls,
					"cost_usd":     cost,
				})
			}
		}
	}

	// Query by provider
	providerQuery := `
		SELECT provider, COUNT(*) as calls, SUM(cost_usd) as cost
		FROM ai_usage_analytics
		` + whereClause + `
		GROUP BY provider
	`
	providerRows, _ := db.QueryContext(r.Context(), providerQuery, args...)
	byProvider := make(map[string]interface{})
	if providerRows != nil {
		defer providerRows.Close()
		for providerRows.Next() {
			var provider string
			var calls int
			var cost float64
			if err := providerRows.Scan(&provider, &calls, &cost); err == nil {
				byProvider[provider] = map[string]interface{}{
					"calls":    calls,
					"cost_usd": cost,
				}
			}
		}
	}

	// Query timeline based on groupBy
	var timelineQuery string
	switch groupBy {
	case "day":
		timelineQuery = `
			SELECT DATE(created_at) as period, COUNT(*) as calls, SUM(cost_usd) as cost
			FROM ai_usage_analytics ` + whereClause + `
			GROUP BY DATE(created_at)
			ORDER BY period DESC LIMIT 30
		`
	case "week":
		timelineQuery = `
			SELECT DATE_TRUNC('week', created_at) as period, COUNT(*) as calls, SUM(cost_usd) as cost
			FROM ai_usage_analytics ` + whereClause + `
			GROUP BY DATE_TRUNC('week', created_at)
			ORDER BY period DESC LIMIT 12
		`
	default: // month
		timelineQuery = `
			SELECT DATE_TRUNC('month', created_at) as period, COUNT(*) as calls, SUM(cost_usd) as cost
			FROM ai_usage_analytics ` + whereClause + `
			GROUP BY DATE_TRUNC('month', created_at)
			ORDER BY period DESC LIMIT 12
		`
	}

	timelineRows, _ := db.QueryContext(r.Context(), timelineQuery, args...)
	timeline := []map[string]interface{}{}
	if timelineRows != nil {
		defer timelineRows.Close()
		for timelineRows.Next() {
			var period time.Time
			var calls int
			var cost float64
			if err := timelineRows.Scan(&period, &calls, &cost); err == nil {
				timeline = append(timeline, map[string]interface{}{
					"period":   period.Format("2006-01-02"),
					"calls":    calls,
					"cost_usd": cost,
				})
			}
		}
	}

	analytics := map[string]interface{}{
		"organization_id": orgID,
		"feature_type":    featureType,
		"group_by":        groupBy,
		"summary": map[string]interface{}{
			"total_api_calls":     summary.TotalCalls,
			"total_tokens_used":   summary.TotalTokens,
			"total_audio_seconds": summary.TotalAudioSeconds,
			"total_cost_usd":      summary.TotalCost,
			"average_latency_ms":  summary.AvgLatency,
			"success_rate":        summary.SuccessRate,
		},
		"by_feature":  byFeature,
		"by_provider": byProvider,
		"timeline":     timeline,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(analytics)
}

// GetCostOptimizationInsights retrieves cost optimization recommendations
func GetCostOptimizationInsights(w http.ResponseWriter, r *http.Request) {
	orgID := r.URL.Query().Get("organization_id")
	severity := r.URL.Query().Get("severity")
	status := r.URL.Query().Get("status")

	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	// Build where clause
	whereClause := "WHERE 1=1"
	args := []interface{}{}
	argCount := 1

	if orgID != "" {
		whereClause += fmt.Sprintf(" AND organization_id = $%d", argCount)
		args = append(args, orgID)
		argCount++
	}
	if severity != "" {
		whereClause += fmt.Sprintf(" AND severity = $%d", argCount)
		args = append(args, severity)
		argCount++
	}
	if status != "" {
		whereClause += fmt.Sprintf(" AND status = $%d", argCount)
		args = append(args, status)
		argCount++
	}

	query := `
		SELECT 
			insight_id, organization_id, insight_type, severity, title, description,
			recommendation, potential_savings_usd, status, detected_at
		FROM cost_optimization_insights
		` + whereClause + `
		ORDER BY potential_savings_usd DESC, detected_at DESC
	`

	rows, err := db.QueryContext(r.Context(), query, args...)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to query insights: %v", err), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	insights := []map[string]interface{}{}
	totalSavings := 0.0

	for rows.Next() {
		var insightID, orgIDStr, insightType, sev, title, desc, recommendation, stat string
		var savings float64
		var detectedAt time.Time

		if err := rows.Scan(&insightID, &orgIDStr, &insightType, &sev, &title, &desc,
			&recommendation, &savings, &stat, &detectedAt); err == nil {
			insights = append(insights, map[string]interface{}{
				"insight_id":            insightID,
				"organization_id":       orgIDStr,
				"insight_type":          insightType,
				"severity":              sev,
				"title":                 title,
				"description":           desc,
				"recommendation":        recommendation,
				"potential_savings_usd": savings,
				"status":                stat,
				"detected_at":           detectedAt,
			})
			if stat == "pending" || stat == "acknowledged" {
				totalSavings += savings
			}
		}
	}

	if rows.Err() != nil {
		http.Error(w, "Error scanning results", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"organization_id":         orgID,
		"insights":                insights,
		"total":                   len(insights),
		"potential_savings_usd":   0.0,
		"filters": map[string]string{
			"severity": severity,
			"status":   status,
		},
	})
}

// AcknowledgeCostInsight acknowledges a cost optimization insight
func AcknowledgeCostInsight(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	insightID := vars["insight_id"]

	var req struct {
		Status string `json:"status"` // acknowledged, implemented, dismissed
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	// Update insight status
	query := `
		UPDATE cost_optimization_insights
		SET status = $1, acknowledged_at = NOW(), updated_at = NOW()
		WHERE insight_id = $2
		RETURNING organization_id
	`

	var orgIDFromDB string
	err := db.QueryRowContext(r.Context(), query, req.Status, insightID).Scan(&orgIDFromDB)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to update insight: %v", err), http.StatusInternalServerError)
		return
	}

	// Log audit event
	if enterpriseService != nil {
		auditLog := services.AuditLog{
			OrganizationID: &orgIDFromDB,
			Action:         "analytics.cost_insight_acknowledged",
			ResourceType:   strPtr("cost_insight"),
			ResourceID:     &insightID,
			Description:    fmt.Sprintf("Cost insight status changed to %s", req.Status),
			Severity:       "info",
		}
		enterpriseService.CreateAuditLog(r.Context(), auditLog)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"insight_id": insightID,
		"status":     req.Status,
		"timestamp":  time.Now(),
	})
}

// CreateCustomReport creates a custom analytics report
func CreateCustomReport(w http.ResponseWriter, r *http.Request) {
	var req struct {
		OrganizationID string                 `json:"organization_id"`
		ReportName     string                 `json:"report_name"`
		ReportType     string                 `json:"report_type"`
		QueryConfig    map[string]interface{} `json:"query_config"`
		IsScheduled    bool                   `json:"is_scheduled"`
		ScheduleCron   *string                `json:"schedule_cron,omitempty"`
		OutputFormat   string                 `json:"output_format"`
		Recipients     []string               `json:"recipients,omitempty"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	reportID := uuid.New().String()

	// Marshal JSON fields
	queryConfigJSON, _ := json.Marshal(req.QueryConfig)
	recipientsJSON, _ := json.Marshal(req.Recipients)

	// Insert into database
	query := `
		INSERT INTO custom_reports (
			report_id, organization_id, report_name, report_type, query_config,
			is_scheduled, schedule_cron, output_format, recipients, is_active
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		RETURNING created_at
	`

	var createdAt time.Time
	err := db.QueryRowContext(r.Context(), query,
		reportID, req.OrganizationID, req.ReportName, req.ReportType, queryConfigJSON,
		req.IsScheduled, req.ScheduleCron, req.OutputFormat, recipientsJSON, true,
	).Scan(&createdAt)

	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to create report: %v", err), http.StatusInternalServerError)
		return
	}

	report := map[string]interface{}{
		"report_id":       reportID,
		"organization_id": req.OrganizationID,
		"report_name":     req.ReportName,
		"report_type":     req.ReportType,
		"query_config":    req.QueryConfig,
		"is_scheduled":    req.IsScheduled,
		"schedule_cron":   req.ScheduleCron,
		"output_format":   req.OutputFormat,
		"recipients":      req.Recipients,
		"is_active":       true,
		"created_at":      createdAt,
	}

	// Log audit event
	if enterpriseService != nil {
		auditLog := services.AuditLog{
			OrganizationID: &req.OrganizationID,
			Action:         "analytics.custom_report_create",
			ResourceType:   strPtr("custom_report"),
			ResourceID:     &reportID,
			Description:    fmt.Sprintf("Custom report created: %s", req.ReportName),
			Severity:       "info",
		}
		enterpriseService.CreateAuditLog(r.Context(), auditLog)
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(report)
}

// GetCustomReports retrieves custom reports
func GetCustomReports(w http.ResponseWriter, r *http.Request) {
	orgID := r.URL.Query().Get("organization_id")
	reportType := r.URL.Query().Get("report_type")

	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	// Build where clause
	whereClause := "WHERE is_active = true"
	args := []interface{}{}
	argCount := 1

	if orgID != "" {
		whereClause += fmt.Sprintf(" AND organization_id = $%d", argCount)
		args = append(args, orgID)
		argCount++
	}
	if reportType != "" {
		whereClause += fmt.Sprintf(" AND report_type = $%d", argCount)
		args = append(args, reportType)
		argCount++
	}

	query := `
		SELECT report_id, organization_id, report_name, report_type, is_scheduled,
		       schedule_cron, output_format, created_at, last_run_at
		FROM custom_reports
		` + whereClause + `
		ORDER BY created_at DESC
	`

	rows, err := db.QueryContext(r.Context(), query, args...)
	if err != nil {
		http.Error(w, "Failed to query reports", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	reports := []map[string]interface{}{}
	for rows.Next() {
		var reportID, orgIDStr, reportName, repType string
		var isScheduled bool
		var scheduleCron, outputFormat *string
		var createdAt time.Time
		var lastRunAt *time.Time

		if err := rows.Scan(&reportID, &orgIDStr, &reportName, &repType, &isScheduled,
			&scheduleCron, &outputFormat, &createdAt, &lastRunAt); err == nil {
			reports = append(reports, map[string]interface{}{
				"report_id":       reportID,
				"organization_id": orgIDStr,
				"report_name":     reportName,
				"report_type":     repType,
				"is_scheduled":    isScheduled,
				"schedule_cron":   scheduleCron,
				"output_format":   outputFormat,
				"created_at":      createdAt,
				"last_run_at":     lastRunAt,
			})
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"reports": reports,
		"total":   len(reports),
		"filters": map[string]string{
			"organization_id": orgID,
			"report_type":     reportType,
		},
	})
}

// RunCustomReport executes a custom report
func RunCustomReport(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	reportID := vars["report_id"]

	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	// Create execution record
	executionID := uuid.New().String()
	startedAt := time.Now()

	// Insert execution record
	execQuery := `
		INSERT INTO report_executions (
			execution_id, report_id, status, started_at
		) VALUES ($1, $2, 'processing', $3)
	`

	_, err := db.ExecContext(r.Context(), execQuery, executionID, reportID, startedAt)
	if err != nil {
		http.Error(w, "Failed to create execution record", http.StatusInternalServerError)
		return
	}

	// Update last_run_at for the report
	updateQuery := `UPDATE custom_reports SET last_run_at = $1 WHERE report_id = $2`
	db.ExecContext(r.Context(), updateQuery, startedAt, reportID)

	// TODO: Trigger async report generation job via message queue
	// For now, return processing status

	result := map[string]interface{}{
		"execution_id": executionID,
		"report_id":    reportID,
		"status":       "processing",
		"result_url":   fmt.Sprintf("/api/v1/analytics/reports/%s/results/%s", reportID, executionID),
		"started_at":   startedAt,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

// GetRealtimeMetrics retrieves real-time platform metrics
func GetRealtimeMetrics(w http.ResponseWriter, r *http.Request) {
	orgID := r.URL.Query().Get("organization_id")

	db := database.GetDB()
	if db == nil {
		http.Error(w, "Database not initialized", http.StatusInternalServerError)
		return
	}

	// Query active calls
	activeCallsQuery := `
		SELECT COUNT(*) FROM calls
		WHERE organization_id = $1 AND status = 'active' AND ended_at IS NULL
	`
	var activeCalls int
	db.QueryRowContext(r.Context(), activeCallsQuery, orgID).Scan(&activeCalls)

	// Query active participants
	activeParticipantsQuery := `
		SELECT COUNT(DISTINCT cp.user_id)
		FROM call_participants cp
		JOIN calls c ON c.call_id = cp.call_id
		WHERE c.organization_id = $1 AND c.status = 'active' AND cp.left_at IS NULL
	`
	var activeParticipants int
	db.QueryRowContext(r.Context(), activeParticipantsQuery, orgID).Scan(&activeParticipants)

	// Query active agents
	activeAgentsQuery := `
		SELECT COUNT(*) FROM ai_agents
		WHERE organization_id = $1 AND is_active = true AND status = 'online'
	`
	var activeAgents int
	db.QueryRowContext(r.Context(), activeAgentsQuery, orgID).Scan(&activeAgents)

	// Query last minute stats
	lastMinuteQuery := `
		SELECT 
			COUNT(CASE WHEN started_at >= NOW() - INTERVAL '1 minute' THEN 1 END) as calls_started,
			COUNT(CASE WHEN ended_at >= NOW() - INTERVAL '1 minute' AND ended_at IS NOT NULL THEN 1 END) as calls_ended
		FROM calls
		WHERE organization_id = $1
	`
	var callsStarted, callsEnded int
	db.QueryRowContext(r.Context(), lastMinuteQuery, orgID).Scan(&callsStarted, &callsEnded)

	// Query AI API calls in last minute
	aiCallsQuery := `
		SELECT COUNT(*) FROM ai_usage_analytics
		WHERE organization_id = $1 AND created_at >= NOW() - INTERVAL '1 minute'
	`
	var aiAPICalls int
	db.QueryRowContext(r.Context(), aiCallsQuery, orgID).Scan(&aiAPICalls)

	// Note: CPU/Memory/Bandwidth would typically come from Prometheus/monitoring system
	// For now, we'll return 0 - should be integrated with actual monitoring

	metrics := map[string]interface{}{
		"organization_id": orgID,
		"timestamp":       time.Now(),
		"realtime": map[string]interface{}{
			"active_calls":         activeCalls,
			"active_participants":  activeParticipants,
			"active_agents":        activeAgents,
			"cpu_usage_percent":    0.0,  // TODO: Integrate with Prometheus
			"memory_usage_percent": 0.0,  // TODO: Integrate with Prometheus
			"bandwidth_usage_mbps": 0.0,  // TODO: Integrate with Prometheus
		},
		"last_minute": map[string]interface{}{
			"calls_started": callsStarted,
			"calls_ended":   callsEnded,
			"ai_api_calls":  aiAPICalls,
			"errors":        0, // TODO: Query error logs
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(metrics)
}
