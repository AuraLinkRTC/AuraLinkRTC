package api

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"github.com/auralink/dashboard-service/internal/middleware"
	"github.com/auralink/shared/livekit"
	"github.com/auralink/shared/database"
)

// CreateRoomRequest represents room creation request
type CreateRoomRequest struct {
	Name              string                 `json:"name"`
	CallType          string                 `json:"call_type"` // one_to_one, group, conference, broadcast
	MaxParticipants   int                    `json:"max_participants"`
	RecordingEnabled  bool                   `json:"recording_enabled"`
	ScreenShareEnabled bool                  `json:"screen_sharing_enabled"`
	FileShareEnabled  bool                   `json:"file_sharing_enabled"`
	Metadata          map[string]interface{} `json:"metadata"`
}

// CreateRoom creates a new WebRTC room and database entry
func CreateRoom(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := r.Context().Value(middleware.UserIDKey).(string)

	var req CreateRoomRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, "VALIDATION_ERROR", "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validation
	if req.Name == "" {
		sendError(w, "VALIDATION_ERROR", "Room name is required", http.StatusBadRequest)
		return
	}
	if req.CallType == "" {
		req.CallType = "group"
	}
	if req.MaxParticipants == 0 {
		req.MaxParticipants = 50
	}

	// Get database connection
	db := database.GetDB() // Assumes database is initialized
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Get LiveKit client
	lkClient := livekit.GetClient() // Assumes LiveKit client is initialized
	if lkClient == nil {
		sendError(w, "SERVER_ERROR", "LiveKit not available", http.StatusInternalServerError)
		return
	}

	// Generate unique room name
	roomName := fmt.Sprintf("room_%s_%d", uuid.New().String()[:8], time.Now().Unix())

	// Create room in LiveKit
	metadataJSON, _ := json.Marshal(req.Metadata)
	lkRoom, err := lkClient.CreateRoom(ctx, livekit.RoomOptions{
		Name:            roomName,
		EmptyTimeout:    300, // 5 minutes
		MaxParticipants: uint32(req.MaxParticipants),
		Metadata:        string(metadataJSON),
	})
	if err != nil {
		sendError(w, "LIVEKIT_ERROR", fmt.Sprintf("Failed to create room: %v", err), http.StatusInternalServerError)
		return
	}

	// Create database entry
	callID := uuid.New()
	userUUID, _ := uuid.Parse(userID)
	
	query := `
		INSERT INTO calls (
			call_id, room_id, room_name, created_by, call_type, status,
			max_participants, recording_enabled, screen_sharing_enabled, file_sharing_enabled, metadata
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
		RETURNING call_id, created_at
	`
	
	var createdAt time.Time
	err = db.QueryRowContext(ctx, query,
		callID, lkRoom.Sid, roomName, userUUID, req.CallType, "waiting",
		req.MaxParticipants, req.RecordingEnabled, req.ScreenShareEnabled,
		req.FileShareEnabled, metadataJSON,
	).Scan(&callID, &createdAt)
	
	if err != nil {
		// Rollback: delete LiveKit room
		lkClient.DeleteRoom(ctx, roomName)
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to create call: %v", err), http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"call_id":                 callID.String(),
		"room_id":                 lkRoom.Sid,
		"room_name":               roomName,
		"created_by":              userID,
		"call_type":               req.CallType,
		"max_participants":        req.MaxParticipants,
		"recording_enabled":       req.RecordingEnabled,
		"screen_sharing_enabled":  req.ScreenShareEnabled,
		"file_sharing_enabled":    req.FileShareEnabled,
		"metadata":                req.Metadata,
		"created_at":              createdAt,
		"status":                  "waiting",
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(response)
}

// ListRooms lists user's calls/rooms
func ListRooms(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	// Get query parameters
	status := r.URL.Query().Get("status") // active, ended, all
	if status == "" {
		status = "all"
	}

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Query for user's calls (either created by them or they participated in)
	query := `
		SELECT DISTINCT c.call_id, c.room_id, c.room_name, c.call_type, c.status,
		       c.started_at, c.ended_at, c.duration_seconds, c.participant_count,
		       c.recording_enabled, c.metadata, c.created_at,
		       u.display_name as creator_name, u.aura_id as creator_aura_id
		FROM calls c
		LEFT JOIN users u ON c.created_by = u.user_id
		WHERE (c.created_by = $1 OR EXISTS (
			SELECT 1 FROM call_participants cp 
			WHERE cp.call_id = c.call_id AND cp.user_id = $1
		))
	`
	
	if status != "all" {
		query += " AND c.status = $2"
	}
	
	query += " ORDER BY c.created_at DESC LIMIT 100"

	var rows *sql.Rows
	var err error
	
	if status != "all" {
		rows, err = db.QueryContext(ctx, query, userUUID, status)
	} else {
		rows, err = db.QueryContext(ctx, query, userUUID)
	}
	
	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to query calls: %v", err), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	calls := []map[string]interface{}{}
	for rows.Next() {
		var callID, roomID, roomName, callType, status string
		var startedAt, endedAt sql.NullTime
		var durationSeconds, participantCount sql.NullInt64
		var recordingEnabled bool
		var metadata []byte
		var createdAt time.Time
		var creatorName, creatorAuraID sql.NullString

		if err := rows.Scan(&callID, &roomID, &roomName, &callType, &status,
			&startedAt, &endedAt, &durationSeconds, &participantCount,
			&recordingEnabled, &metadata, &createdAt, &creatorName, &creatorAuraID); err != nil {
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

		calls = append(calls, call)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"calls": calls,
		"total": len(calls),
	})
}

// GetRoom retrieves room/call details
func GetRoom(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	callID := vars["room_id"]

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	query := `
		SELECT c.call_id, c.room_id, c.room_name, c.call_type, c.status,
		       c.started_at, c.ended_at, c.duration_seconds, c.participant_count,
		       c.max_participants, c.recording_enabled, c.screen_sharing_enabled,
		       c.file_sharing_enabled, c.metadata, c.created_at, c.avg_quality_score,
		       u.display_name as creator_name, u.aura_id as creator_aura_id
		FROM calls c
		LEFT JOIN users u ON c.created_by = u.user_id
		WHERE c.call_id = $1
	`

	var room map[string]interface{}
	var roomID, roomName, callType, status string
	var startedAt, endedAt sql.NullTime
	var durationSeconds, participantCount sql.NullInt64
	var maxParticipants int
	var recordingEnabled, screenShareEnabled, fileShareEnabled bool
	var metadata []byte
	var createdAt time.Time
	var avgQualityScore sql.NullFloat64
	var creatorName, creatorAuraID sql.NullString

	err := db.QueryRowContext(ctx, query, callID).Scan(
		&callID, &roomID, &roomName, &callType, &status,
		&startedAt, &endedAt, &durationSeconds, &participantCount,
		&maxParticipants, &recordingEnabled, &screenShareEnabled,
		&fileShareEnabled, &metadata, &createdAt, &avgQualityScore,
		&creatorName, &creatorAuraID,
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

	room = map[string]interface{}{
		"call_id":                callID,
		"room_id":                roomID,
		"room_name":              roomName,
		"call_type":              callType,
		"status":                 status,
		"participant_count":      participantCount.Int64,
		"max_participants":       maxParticipants,
		"recording_enabled":      recordingEnabled,
		"screen_sharing_enabled": screenShareEnabled,
		"file_sharing_enabled":   fileShareEnabled,
		"metadata":               metadataMap,
		"created_at":             createdAt,
		"creator_name":           creatorName.String,
		"creator_aura_id":        creatorAuraID.String,
	}

	if startedAt.Valid {
		room["started_at"] = startedAt.Time
	}
	if endedAt.Valid {
		room["ended_at"] = endedAt.Time
	}
	if durationSeconds.Valid {
		room["duration_seconds"] = durationSeconds.Int64
	}
	if avgQualityScore.Valid {
		room["avg_quality_score"] = avgQualityScore.Float64
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(room)
}

// DeleteRoom deletes a room/call
func DeleteRoom(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	callID := vars["room_id"]
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Check if user owns the call
	var roomName string
	var createdBy uuid.UUID
	err := db.QueryRowContext(ctx, "SELECT room_name, created_by FROM calls WHERE call_id = $1", callID).Scan(&roomName, &createdBy)
	if err == sql.ErrNoRows {
		sendError(w, "NOT_FOUND", "Call not found", http.StatusNotFound)
		return
	} else if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to get call: %v", err), http.StatusInternalServerError)
		return
	}

	if createdBy != userUUID {
		sendError(w, "FORBIDDEN", "Only the creator can delete this call", http.StatusForbidden)
		return
	}

	// Delete from LiveKit
	lkClient := livekit.GetClient()
	if lkClient != nil {
		err = lkClient.DeleteRoom(ctx, roomName)
		if err != nil {
			// Log error but continue with database deletion
			fmt.Printf("Failed to delete LiveKit room: %v\n", err)
		}
	}

	// Delete from database (CASCADE will handle related records)
	_, err = db.ExecContext(ctx, "DELETE FROM calls WHERE call_id = $1", callID)
	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to delete call: %v", err), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// JoinRoomRequest represents join room request
type JoinRoomRequest struct {
	DisplayName string `json:"display_name"`
	Metadata    string `json:"metadata"`
}

// GenerateRoomToken generates a JWT token for joining a room
func GenerateRoomToken(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	callID := vars["room_id"]
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	var req JoinRoomRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, "VALIDATION_ERROR", "Invalid request body", http.StatusBadRequest)
		return
	}

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Get call details
	var roomName, status string
	var maxParticipants, participantCount int
	err := db.QueryRowContext(ctx, "SELECT room_name, status, max_participants, participant_count FROM calls WHERE call_id = $1", callID).Scan(&roomName, &status, &maxParticipants, &participantCount)
	if err == sql.ErrNoRows {
		sendError(w, "NOT_FOUND", "Call not found", http.StatusNotFound)
		return
	} else if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to get call: %v", err), http.StatusInternalServerError)
		return
	}

	// Check room capacity
	if participantCount >= maxParticipants {
		sendError(w, "ROOM_FULL", "Room has reached maximum capacity", http.StatusForbidden)
		return
	}

	// Get user info
	var displayName, auraID string
	err = db.QueryRowContext(ctx, "SELECT display_name, aura_id FROM users WHERE user_id = $1", userUUID).Scan(&displayName, &auraID)
	if err != nil {
		displayName = req.DisplayName
	} else if req.DisplayName != "" {
		displayName = req.DisplayName
	}

	// Generate LiveKit token
	lkClient := livekit.GetClient()
	if lkClient == nil {
		sendError(w, "SERVER_ERROR", "LiveKit not available", http.StatusInternalServerError)
		return
	}

	token, err := lkClient.GenerateAccessToken(livekit.TokenOptions{
		Identity:       userID,
		RoomName:       roomName,
		Name:           displayName,
		Metadata:       req.Metadata,
		CanPublish:     true,
		CanSubscribe:   true,
		CanPublishData: true,
		ValidFor:       24 * time.Hour,
	})

	if err != nil {
		sendError(w, "TOKEN_ERROR", fmt.Sprintf("Failed to generate token: %v", err), http.StatusInternalServerError)
		return
	}

	// Create participant record
	participantID := uuid.New()
	_, err = db.ExecContext(ctx, `
		INSERT INTO call_participants (participant_id, call_id, user_id, identity, display_name, role, status, metadata)
		VALUES ($1, $2, $3, $4, $5, 'participant', 'waiting', $6)
		ON CONFLICT DO NOTHING
	`, participantID, callID, userUUID, userID, displayName, req.Metadata)

	if err != nil {
		fmt.Printf("Failed to create participant record: %v\n", err)
		// Continue anyway, token is valid
	}

	// Update call status to active if it's the first participant
	if status == "waiting" {
		_, _ = db.ExecContext(ctx, "UPDATE calls SET status = 'active', started_at = NOW() WHERE call_id = $1", callID)
	}

	response := map[string]interface{}{
		"token":            token,
		"call_id":          callID,
		"room_name":        roomName,
		"identity":         userID,
		"display_name":     displayName,
		"participant_id":   participantID.String(),
		"aura_id":          auraID,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}
