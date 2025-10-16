package api

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/google/uuid"
	"github.com/auralink/shared/database"
)

// LiveKit webhook events
type WebhookEvent struct {
	Event     string          `json:"event"`
	Room      *RoomInfo       `json:"room,omitempty"`
	Participant *ParticipantInfo `json:"participant,omitempty"`
	Track     *TrackInfo      `json:"track,omitempty"`
	CreatedAt int64           `json:"createdAt"`
}

type RoomInfo struct {
	Sid              string `json:"sid"`
	Name             string `json:"name"`
	EmptyTimeout     uint32 `json:"emptyTimeout"`
	MaxParticipants  uint32 `json:"maxParticipants"`
	CreationTime     int64  `json:"creationTime"`
	NumParticipants  uint32 `json:"numParticipants"`
	Metadata         string `json:"metadata"`
}

type ParticipantInfo struct {
	Sid        string `json:"sid"`
	Identity   string `json:"identity"`
	Name       string `json:"name"`
	State      string `json:"state"`
	Metadata   string `json:"metadata"`
	JoinedAt   int64  `json:"joinedAt"`
	Permission *ParticipantPermission `json:"permission,omitempty"`
}

type ParticipantPermission struct {
	CanPublish     bool `json:"canPublish"`
	CanSubscribe   bool `json:"canSubscribe"`
	CanPublishData bool `json:"canPublishData"`
}

type TrackInfo struct {
	Sid      string `json:"sid"`
	Type     string `json:"type"`
	Name     string `json:"name"`
	Muted    bool   `json:"muted"`
	Width    uint32 `json:"width,omitempty"`
	Height   uint32 `json:"height,omitempty"`
	Simulcast bool  `json:"simulcast,omitempty"`
}

// LiveKitWebhook handles webhooks from LiveKit server
func LiveKitWebhook(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	var event WebhookEvent
	if err := json.NewDecoder(r.Body).Decode(&event); err != nil {
		sendError(w, "VALIDATION_ERROR", "Invalid webhook payload", http.StatusBadRequest)
		return
	}

	db := database.GetDB()
	if db == nil {
		// Log error but return 200 to prevent retries
		fmt.Printf("Database not available for webhook processing\n")
		w.WriteHeader(http.StatusOK)
		return
	}

	// Process event based on type
	switch event.Event {
	case "room_started":
		handleRoomStarted(ctx, db, &event)
	case "room_finished":
		handleRoomFinished(ctx, db, &event)
	case "participant_joined":
		handleParticipantJoined(ctx, db, &event)
	case "participant_left":
		handleParticipantLeft(ctx, db, &event)
	case "track_published":
		handleTrackPublished(ctx, db, &event)
	case "track_unpublished":
		handleTrackUnpublished(ctx, db, &event)
	default:
		fmt.Printf("Unknown webhook event: %s\n", event.Event)
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"received": true,
	})
}

func handleRoomStarted(ctx context.Context, db *sql.DB, event *WebhookEvent) {
	if event.Room == nil {
		return
	}

	// Update call status to active
	_, err := db.ExecContext(ctx, `
		UPDATE calls 
		SET status = 'active', started_at = NOW()
		WHERE room_id = $1 AND status = 'waiting'
	`, event.Room.Sid)

	if err != nil {
		fmt.Printf("Failed to update room started: %v\n", err)
	}
}

func handleRoomFinished(ctx context.Context, db *sql.DB, event *WebhookEvent) {
	if event.Room == nil {
		return
	}

	// Update call status to ended
	_, err := db.ExecContext(ctx, `
		UPDATE calls 
		SET status = 'ended', ended_at = NOW(),
		    duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::INT
		WHERE room_id = $1 AND status = 'active'
	`, event.Room.Sid)

	if err != nil {
		fmt.Printf("Failed to update room finished: %v\n", err)
	}

	// Update all participants to left
	_, _ = db.ExecContext(ctx, `
		UPDATE call_participants cp
		SET status = 'left', left_at = NOW(),
		    duration_seconds = EXTRACT(EPOCH FROM (NOW() - joined_at))::INT
		FROM calls c
		WHERE cp.call_id = c.call_id AND c.room_id = $1 AND cp.status != 'left'
	`, event.Room.Sid)
}

func handleParticipantJoined(ctx context.Context, db *sql.DB, event *WebhookEvent) {
	if event.Participant == nil || event.Room == nil {
		return
	}

	// Get call_id from room
	var callID uuid.UUID
	err := db.QueryRowContext(ctx, "SELECT call_id FROM calls WHERE room_id = $1", event.Room.Sid).Scan(&callID)
	if err != nil {
		fmt.Printf("Failed to get call_id for room: %v\n", err)
		return
	}

	// Update participant status
	_, err = db.ExecContext(ctx, `
		UPDATE call_participants
		SET status = 'connected', joined_at = NOW()
		WHERE call_id = $1 AND identity = $2
	`, callID, event.Participant.Identity)

	if err != nil {
		fmt.Printf("Failed to update participant joined: %v\n", err)
	}
}

func handleParticipantLeft(ctx context.Context, db *sql.DB, event *WebhookEvent) {
	if event.Participant == nil || event.Room == nil {
		return
	}

	// Get call_id from room
	var callID uuid.UUID
	err := db.QueryRowContext(ctx, "SELECT call_id FROM calls WHERE room_id = $1", event.Room.Sid).Scan(&callID)
	if err != nil {
		return
	}

	// Update participant status
	_, err = db.ExecContext(ctx, `
		UPDATE call_participants
		SET status = 'left', left_at = NOW(),
		    duration_seconds = EXTRACT(EPOCH FROM (NOW() - joined_at))::INT
		WHERE call_id = $1 AND identity = $2
	`, callID, event.Participant.Identity)

	if err != nil {
		fmt.Printf("Failed to update participant left: %v\n", err)
	}
}

func handleTrackPublished(ctx context.Context, db *sql.DB, event *WebhookEvent) {
	if event.Participant == nil || event.Track == nil || event.Room == nil {
		return
	}

	// Get call_id and participant_id
	var callID, participantID uuid.UUID
	err := db.QueryRowContext(ctx, `
		SELECT cp.call_id, cp.participant_id
		FROM call_participants cp
		JOIN calls c ON cp.call_id = c.call_id
		WHERE c.room_id = $1 AND cp.identity = $2
	`, event.Room.Sid, event.Participant.Identity).Scan(&callID, &participantID)

	if err != nil {
		return
	}

	// Update participant media state
	if event.Track.Type == "audio" {
		_, _ = db.ExecContext(ctx, `
			UPDATE call_participants
			SET audio_enabled = NOT $3
			WHERE participant_id = $1
		`, participantID, event.Track.Muted)
	} else if event.Track.Type == "video" {
		_, _ = db.ExecContext(ctx, `
			UPDATE call_participants
			SET video_enabled = NOT $3
			WHERE participant_id = $1
		`, participantID, event.Track.Muted)
	}
}

func handleTrackUnpublished(ctx context.Context, db *sql.DB, event *WebhookEvent) {
	if event.Participant == nil || event.Track == nil || event.Room == nil {
		return
	}

	// Get participant_id
	var participantID uuid.UUID
	err := db.QueryRowContext(ctx, `
		SELECT cp.participant_id
		FROM call_participants cp
		JOIN calls c ON cp.call_id = c.call_id
		WHERE c.room_id = $1 AND cp.identity = $2
	`, event.Room.Sid, event.Participant.Identity).Scan(&participantID)

	if err != nil {
		return
	}

	// Update participant media state
	if event.Track.Type == "audio" {
		_, _ = db.ExecContext(ctx, "UPDATE call_participants SET audio_enabled = false WHERE participant_id = $1", participantID)
	} else if event.Track.Type == "video" {
		_, _ = db.ExecContext(ctx, "UPDATE call_participants SET video_enabled = false WHERE participant_id = $1", participantID)
	}
}

// RecordQualityMetrics records quality metrics for a participant
func RecordQualityMetrics(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	var req struct {
		CallID           string  `json:"call_id"`
		ParticipantID    string  `json:"participant_id"`
		PacketLoss       float64 `json:"packet_loss_percent"`
		Jitter           int     `json:"jitter_ms"`
		Latency          int     `json:"latency_ms"`
		Bandwidth        int     `json:"bandwidth_kbps"`
		VideoResolution  string  `json:"video_resolution"`
		VideoFPS         int     `json:"video_fps"`
		AudioBitrate     int     `json:"audio_bitrate_kbps"`
		VideoBitrate     int     `json:"video_bitrate_kbps"`
		ConnectionType   string  `json:"connection_type"`
		ICEState         string  `json:"ice_state"`
		QualityScore     float64 `json:"quality_score"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, "VALIDATION_ERROR", "Invalid request body", http.StatusBadRequest)
		return
	}

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	callUUID, _ := uuid.Parse(req.CallID)
	participantUUID, _ := uuid.Parse(req.ParticipantID)

	// Insert quality metric
	_, err := db.ExecContext(ctx, `
		INSERT INTO quality_metrics (
			metric_id, call_id, participant_id, packet_loss_percent, jitter_ms,
			latency_ms, bandwidth_kbps, video_resolution, video_fps, audio_bitrate_kbps,
			video_bitrate_kbps, connection_type, ice_state, quality_score
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
	`, uuid.New(), callUUID, participantUUID, req.PacketLoss, req.Jitter,
		req.Latency, req.Bandwidth, req.VideoResolution, req.VideoFPS, req.AudioBitrate,
		req.VideoBitrate, req.ConnectionType, req.ICEState, req.QualityScore)

	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to record metrics: %v", err), http.StatusInternalServerError)
		return
	}

	// Update participant average quality score
	_, _ = db.ExecContext(ctx, `
		UPDATE call_participants
		SET avg_quality_score = (
			SELECT AVG(quality_score)
			FROM quality_metrics
			WHERE participant_id = $1
		),
		packet_loss_percent = $2,
		avg_latency_ms = $3
		WHERE participant_id = $1
	`, participantUUID, req.PacketLoss, req.Latency)

	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"recorded": true,
	})
}

// GetCallQuality retrieves quality metrics for a call
func GetCallQuality(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	callID := r.URL.Query().Get("call_id")
	participantID := r.URL.Query().Get("participant_id")

	if callID == "" {
		sendError(w, "VALIDATION_ERROR", "call_id is required", http.StatusBadRequest)
		return
	}

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	query := `
		SELECT metric_id, participant_id, recorded_at, packet_loss_percent, jitter_ms,
		       latency_ms, bandwidth_kbps, video_resolution, video_fps, audio_bitrate_kbps,
		       video_bitrate_kbps, connection_type, ice_state, quality_score
		FROM quality_metrics
		WHERE call_id = $1
	`

	var rows *sql.Rows
	var err error

	if participantID != "" {
		query += " AND participant_id = $2"
		rows, err = db.QueryContext(ctx, query, callID, participantID)
	} else {
		rows, err = db.QueryContext(ctx, query, callID)
	}

	query += " ORDER BY recorded_at DESC LIMIT 100"

	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to query metrics: %v", err), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	metrics := []map[string]interface{}{}
	for rows.Next() {
		var metricID, partID, videoResolution, connectionType, iceState string
		var recordedAt time.Time
		var packetLoss, qualityScore float64
		var jitter, latency, bandwidth, videoFPS, audioBitrate, videoBitrate int

		if err := rows.Scan(&metricID, &partID, &recordedAt, &packetLoss, &jitter,
			&latency, &bandwidth, &videoResolution, &videoFPS, &audioBitrate,
			&videoBitrate, &connectionType, &iceState, &qualityScore); err != nil {
			continue
		}

		metric := map[string]interface{}{
			"metric_id":          metricID,
			"participant_id":     partID,
			"recorded_at":        recordedAt,
			"packet_loss_percent": packetLoss,
			"jitter_ms":          jitter,
			"latency_ms":         latency,
			"bandwidth_kbps":     bandwidth,
			"video_resolution":   videoResolution,
			"video_fps":          videoFPS,
			"audio_bitrate_kbps": audioBitrate,
			"video_bitrate_kbps": videoBitrate,
			"connection_type":    connectionType,
			"ice_state":          iceState,
			"quality_score":      qualityScore,
		}

		metrics = append(metrics, metric)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"metrics": metrics,
		"total":   len(metrics),
	})
}
