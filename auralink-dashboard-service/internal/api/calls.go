package api

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"github.com/auralink/dashboard-service/internal/middleware"
	"github.com/auralink/shared/database"
)

// ListCalls lists user's call history
func ListCalls(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	// Get query parameters
	status := r.URL.Query().Get("status")     // active, ended, all
	callType := r.URL.Query().Get("call_type") // one_to_one, group, conference, broadcast
	limit := r.URL.Query().Get("limit")
	if limit == "" {
		limit = "50"
	}

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Build query
	query := `
		SELECT DISTINCT c.call_id, c.room_id, c.room_name, c.call_type, c.status,
		       c.started_at, c.ended_at, c.duration_seconds, c.participant_count,
		       c.recording_enabled, c.recording_url, c.avg_quality_score,
		       c.metadata, c.created_at,
		       u.display_name as creator_name, u.aura_id as creator_aura_id,
		       COUNT(DISTINCT f.file_id) as files_shared
		FROM calls c
		LEFT JOIN users u ON c.created_by = u.user_id
		LEFT JOIN files f ON c.call_id = f.call_id
		WHERE (c.created_by = $1 OR EXISTS (
			SELECT 1 FROM call_participants cp 
			WHERE cp.call_id = c.call_id AND cp.user_id = $1
		))
	`

	args := []interface{}{userUUID}
	argPos := 2

	if status != "" && status != "all" {
		query += fmt.Sprintf(" AND c.status = $%d", argPos)
		args = append(args, status)
		argPos++
	}

	if callType != "" {
		query += fmt.Sprintf(" AND c.call_type = $%d", argPos)
		args = append(args, callType)
		argPos++
	}

	query += " GROUP BY c.call_id, u.display_name, u.aura_id"
	query += " ORDER BY c.created_at DESC"
	query += fmt.Sprintf(" LIMIT $%d", argPos)
	args = append(args, limit)

	rows, err := db.QueryContext(ctx, query, args...)
	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to query calls: %v", err), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	calls := []map[string]interface{}{}
	for rows.Next() {
		var callID, roomID, roomName, callType, status string
		var startedAt, endedAt sql.NullTime
		var durationSeconds, participantCount, filesShared sql.NullInt64
		var recordingEnabled bool
		var recordingURL sql.NullString
		var avgQualityScore sql.NullFloat64
		var metadata []byte
		var createdAt time.Time
		var creatorName, creatorAuraID sql.NullString

		if err := rows.Scan(&callID, &roomID, &roomName, &callType, &status,
			&startedAt, &endedAt, &durationSeconds, &participantCount,
			&recordingEnabled, &recordingURL, &avgQualityScore,
			&metadata, &createdAt, &creatorName, &creatorAuraID, &filesShared); err != nil {
			continue
		}

		var metadataMap map[string]interface{}
		json.Unmarshal(metadata, &metadataMap)

		call := map[string]interface{}{
			"call_id":           callID,
			"room_id":           roomID,
			"room_name":         roomName,
			"call_type":         callType,
			"status":            status,
			"participant_count": participantCount.Int64,
			"recording_enabled": recordingEnabled,
			"files_shared":      filesShared.Int64,
			"metadata":          metadataMap,
			"created_at":        createdAt,
			"creator_name":      creatorName.String,
			"creator_aura_id":   creatorAuraID.String,
		}

		if startedAt.Valid {
			call["started_at"] = startedAt.Time
		}
		if endedAt.Valid {
			call["ended_at"] = endedAt.Time
		}
		if durationSeconds.Valid {
			call["duration_seconds"] = durationSeconds.Int64
		}
		if recordingURL.Valid {
			call["recording_url"] = recordingURL.String
		}
		if avgQualityScore.Valid {
			call["avg_quality_score"] = avgQualityScore.Float64
		}

		calls = append(calls, call)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"calls": calls,
		"total": len(calls),
	})
}

// GetCall retrieves call details
func GetCall(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	callID := vars["call_id"]
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Verify user has access to this call
	var hasAccess bool
	err := db.QueryRowContext(ctx, `
		SELECT EXISTS(
			SELECT 1 FROM calls c
			LEFT JOIN call_participants cp ON c.call_id = cp.call_id
			WHERE c.call_id = $1 AND (c.created_by = $2 OR cp.user_id = $2)
		)
	`, callID, userUUID).Scan(&hasAccess)

	if err != nil || !hasAccess {
		sendError(w, "FORBIDDEN", "Access denied to this call", http.StatusForbidden)
		return
	}

	query := `
		SELECT c.call_id, c.room_id, c.room_name, c.call_type, c.status,
		       c.started_at, c.ended_at, c.duration_seconds, c.participant_count,
		       c.max_participants, c.recording_enabled, c.recording_url,
		       c.screen_sharing_enabled, c.file_sharing_enabled,
		       c.avg_quality_score, c.total_data_transferred_mb,
		       c.metadata, c.created_at,
		       u.display_name as creator_name, u.aura_id as creator_aura_id,
		       COUNT(DISTINCT f.file_id) as files_shared
		FROM calls c
		LEFT JOIN users u ON c.created_by = u.user_id
		LEFT JOIN files f ON c.call_id = f.call_id
		WHERE c.call_id = $1
		GROUP BY c.call_id, u.display_name, u.aura_id
	`

	var roomID, roomName, callType, status string
	var startedAt, endedAt sql.NullTime
	var durationSeconds, participantCount, maxParticipants, filesShared sql.NullInt64
	var recordingEnabled, screenShareEnabled, fileShareEnabled bool
	var recordingURL sql.NullString
	var avgQualityScore, totalDataTransferred sql.NullFloat64
	var metadata []byte
	var createdAt time.Time
	var creatorName, creatorAuraID sql.NullString

	err = db.QueryRowContext(ctx, query, callID).Scan(
		&callID, &roomID, &roomName, &callType, &status,
		&startedAt, &endedAt, &durationSeconds, &participantCount,
		&maxParticipants, &recordingEnabled, &recordingURL,
		&screenShareEnabled, &fileShareEnabled,
		&avgQualityScore, &totalDataTransferred,
		&metadata, &createdAt, &creatorName, &creatorAuraID, &filesShared,
	)

	if err == sql.ErrNoRows {
		sendError(w, "NOT_FOUND", "Call not found", http.StatusNotFound)
		return
	} else if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to get call: %v", err), http.StatusInternalServerError)
		return
	}

	var metadataMap map[string]interface{}
	json.Unmarshal(metadata, &metadataMap)

	call := map[string]interface{}{
		"call_id":                callID,
		"room_id":                roomID,
		"room_name":              roomName,
		"call_type":              callType,
		"status":                 status,
		"participant_count":      participantCount.Int64,
		"max_participants":       maxParticipants.Int64,
		"recording_enabled":      recordingEnabled,
		"screen_sharing_enabled": screenShareEnabled,
		"file_sharing_enabled":   fileShareEnabled,
		"files_shared":           filesShared.Int64,
		"metadata":               metadataMap,
		"created_at":             createdAt,
		"creator_name":           creatorName.String,
		"creator_aura_id":        creatorAuraID.String,
	}

	if startedAt.Valid {
		call["started_at"] = startedAt.Time
	}
	if endedAt.Valid {
		call["ended_at"] = endedAt.Time
	}
	if durationSeconds.Valid {
		call["duration_seconds"] = durationSeconds.Int64
	}
	if recordingURL.Valid {
		call["recording_url"] = recordingURL.String
	}
	if avgQualityScore.Valid {
		call["avg_quality_score"] = avgQualityScore.Float64
	}
	if totalDataTransferred.Valid {
		call["total_data_transferred_mb"] = totalDataTransferred.Float64
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(call)
}

// GetCallParticipants retrieves call participants
func GetCallParticipants(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	callID := vars["call_id"]
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Verify user has access to this call
	var hasAccess bool
	err := db.QueryRowContext(ctx, `
		SELECT EXISTS(
			SELECT 1 FROM calls c
			LEFT JOIN call_participants cp ON c.call_id = cp.call_id
			WHERE c.call_id = $1 AND (c.created_by = $2 OR cp.user_id = $2)
		)
	`, callID, userUUID).Scan(&hasAccess)

	if err != nil || !hasAccess {
		sendError(w, "FORBIDDEN", "Access denied to this call", http.StatusForbidden)
		return
	}

	query := `
		SELECT cp.participant_id, cp.identity, cp.display_name, cp.role, cp.status,
		       cp.joined_at, cp.left_at, cp.duration_seconds,
		       cp.audio_enabled, cp.video_enabled, cp.screen_sharing,
		       cp.avg_quality_score, cp.packet_loss_percent, cp.avg_latency_ms,
		       cp.connection_type, cp.metadata,
		       u.aura_id, u.display_name as user_display_name
		FROM call_participants cp
		LEFT JOIN users u ON cp.user_id = u.user_id
		WHERE cp.call_id = $1
		ORDER BY cp.joined_at ASC
	`

	rows, err := db.QueryContext(ctx, query, callID)
	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to query participants: %v", err), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	participants := []map[string]interface{}{}
	for rows.Next() {
		var participantID, identity, displayName, role, status string
		var joinedAt time.Time
		var leftAt sql.NullTime
		var durationSeconds sql.NullInt64
		var audioEnabled, videoEnabled, screenSharing bool
		var avgQualityScore, packetLoss sql.NullFloat64
		var avgLatency sql.NullInt64
		var connectionType sql.NullString
		var metadata []byte
		var auraID, userDisplayName sql.NullString

		if err := rows.Scan(&participantID, &identity, &displayName, &role, &status,
			&joinedAt, &leftAt, &durationSeconds,
			&audioEnabled, &videoEnabled, &screenSharing,
			&avgQualityScore, &packetLoss, &avgLatency,
			&connectionType, &metadata, &auraID, &userDisplayName); err != nil {
			continue
		}

		var metadataMap map[string]interface{}
		json.Unmarshal(metadata, &metadataMap)

		participant := map[string]interface{}{
			"participant_id":  participantID,
			"identity":        identity,
			"display_name":    displayName,
			"role":            role,
			"status":          status,
			"joined_at":       joinedAt,
			"audio_enabled":   audioEnabled,
			"video_enabled":   videoEnabled,
			"screen_sharing":  screenSharing,
			"connection_type": connectionType.String,
			"metadata":        metadataMap,
			"aura_id":         auraID.String,
		}

		if userDisplayName.Valid {
			participant["user_display_name"] = userDisplayName.String
		}
		if leftAt.Valid {
			participant["left_at"] = leftAt.Time
		}
		if durationSeconds.Valid {
			participant["duration_seconds"] = durationSeconds.Int64
		}
		if avgQualityScore.Valid {
			participant["avg_quality_score"] = avgQualityScore.Float64
		}
		if packetLoss.Valid {
			participant["packet_loss_percent"] = packetLoss.Float64
		}
		if avgLatency.Valid {
			participant["avg_latency_ms"] = avgLatency.Int64
		}

		participants = append(participants, participant)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"call_id":      callID,
		"participants": participants,
		"total":        len(participants),
	})
}
