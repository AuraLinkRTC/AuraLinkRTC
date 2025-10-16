package api

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/json"
	"fmt"
	"math/big"
	"net/http"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"github.com/auralink/dashboard-service/internal/middleware"
	"github.com/auralink/shared/database"
	"golang.org/x/crypto/bcrypt"
)

// CreateLinkRequest represents shareable link creation request
type CreateLinkRequest struct {
	RoomID          string                 `json:"room_id"`
	CallID          string                 `json:"call_id"`
	LinkType        string                 `json:"link_type"` // room, call, agent
	Title           string                 `json:"title"`
	Description     string                 `json:"description"`
	AccessType      string                 `json:"access_type"` // public, password, restricted
	Password        string                 `json:"password"`
	MaxUses         *int                   `json:"max_uses"`
	ExpiresInHours  int                    `json:"expires_in_hours"`
	EnableRecording bool                   `json:"enable_recording"`
	EnableScreenShare bool                 `json:"enable_screen_share"`
	EnableChat      bool                   `json:"enable_chat"`
	AutoJoin        bool                   `json:"auto_join"`
	RequireApproval bool                   `json:"require_approval"`
	DefaultRole     string                 `json:"default_role"` // host, moderator, participant, viewer
	Metadata        map[string]interface{} `json:"metadata"`
}

// generateShortCode generates a random short code for links
func generateShortCode(length int) (string, error) {
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	result := make([]byte, length)
	for i := range result {
		num, err := rand.Int(rand.Reader, big.NewInt(int64(len(charset))))
		if err != nil {
			return "", err
		}
		result[i] = charset[num.Int64()]
	}
	return string(result), nil
}

// CreateLink creates a new shareable link
func CreateLink(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	var req CreateLinkRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, "VALIDATION_ERROR", "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validation
	if req.RoomID == "" && req.CallID == "" {
		sendError(w, "VALIDATION_ERROR", "Either room_id or call_id is required", http.StatusBadRequest)
		return
	}
	if req.LinkType == "" {
		req.LinkType = "room"
	}
	if req.AccessType == "" {
		req.AccessType = "public"
	}
	if req.DefaultRole == "" {
		req.DefaultRole = "participant"
	}

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Verify user has access to the room/call
	if req.CallID != "" {
		var exists bool
		err := db.QueryRowContext(ctx, `
			SELECT EXISTS(
				SELECT 1 FROM calls WHERE call_id = $1 AND created_by = $2
			)
		`, req.CallID, userUUID).Scan(&exists)
		
		if err != nil || !exists {
			sendError(w, "FORBIDDEN", "Access denied to this call", http.StatusForbidden)
			return
		}
	}

	// Generate unique short code
	var shortCode string
	for {
		code, err := generateShortCode(8)
		if err != nil {
			sendError(w, "SERVER_ERROR", "Failed to generate short code", http.StatusInternalServerError)
			return
		}
		
		// Check if code already exists
		var exists bool
		db.QueryRowContext(ctx, "SELECT EXISTS(SELECT 1 FROM shareable_links WHERE short_code = $1)", code).Scan(&exists)
		if !exists {
			shortCode = code
			break
		}
	}

	// Hash password if provided
	var passwordHash *string
	if req.AccessType == "password" && req.Password != "" {
		hash, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
		if err != nil {
			sendError(w, "SERVER_ERROR", "Failed to hash password", http.StatusInternalServerError)
			return
		}
		hashStr := string(hash)
		passwordHash = &hashStr
	}

	// Calculate expiration
	var expiresAt *time.Time
	if req.ExpiresInHours > 0 {
		expiry := time.Now().Add(time.Duration(req.ExpiresInHours) * time.Hour)
		expiresAt = &expiry
	}

	// Create link
	linkID := uuid.New()
	var callUUID *uuid.UUID
	if req.CallID != "" {
		parsed, _ := uuid.Parse(req.CallID)
		callUUID = &parsed
	}

	metadataJSON, _ := json.Marshal(req.Metadata)

	query := `
		INSERT INTO shareable_links (
			link_id, short_code, room_id, call_id, created_by, link_type,
			title, description, access_type, password_hash, max_uses,
			enable_recording, enable_screen_share, enable_chat, auto_join,
			require_approval, default_role, expires_at, metadata
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
		RETURNING created_at
	`

	var createdAt time.Time
	err := db.QueryRowContext(ctx, query,
		linkID, shortCode, req.RoomID, callUUID, userUUID, req.LinkType,
		req.Title, req.Description, req.AccessType, passwordHash, req.MaxUses,
		req.EnableRecording, req.EnableScreenShare, req.EnableChat, req.AutoJoin,
		req.RequireApproval, req.DefaultRole, expiresAt, metadataJSON,
	).Scan(&createdAt)

	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to create link: %v", err), http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"link_id":             linkID.String(),
		"short_code":          shortCode,
		"url":                 fmt.Sprintf("https://auralink.com/join/%s", shortCode),
		"room_id":             req.RoomID,
		"call_id":             req.CallID,
		"link_type":           req.LinkType,
		"title":               req.Title,
		"description":         req.Description,
		"access_type":         req.AccessType,
		"max_uses":            req.MaxUses,
		"enable_recording":    req.EnableRecording,
		"enable_screen_share": req.EnableScreenShare,
		"enable_chat":         req.EnableChat,
		"auto_join":           req.AutoJoin,
		"require_approval":    req.RequireApproval,
		"default_role":        req.DefaultRole,
		"metadata":            req.Metadata,
		"created_at":          createdAt,
		"is_active":           true,
	}

	if expiresAt != nil {
		response["expires_at"] = expiresAt
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(response)
}

// ListLinks lists user's shareable links
func ListLinks(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	query := `
		SELECT link_id, short_code, room_id, call_id, link_type, title, description,
		       access_type, max_uses, current_uses, enable_recording, enable_screen_share,
		       enable_chat, auto_join, require_approval, default_role, expires_at,
		       is_active, total_clicks, unique_visitors, created_at, last_used_at
		FROM shareable_links
		WHERE created_by = $1
		ORDER BY created_at DESC
		LIMIT 100
	`

	rows, err := db.QueryContext(ctx, query, userUUID)
	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to query links: %v", err), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	links := []map[string]interface{}{}
	for rows.Next() {
		var linkID, shortCode, linkType, title, description, accessType, defaultRole string
		var roomID, callID sql.NullString
		var maxUses, currentUses, totalClicks, uniqueVisitors sql.NullInt64
		var enableRecording, enableScreenShare, enableChat, autoJoin, requireApproval, isActive bool
		var expiresAt, lastUsedAt sql.NullTime
		var createdAt time.Time

		if err := rows.Scan(&linkID, &shortCode, &roomID, &callID, &linkType, &title, &description,
			&accessType, &maxUses, &currentUses, &enableRecording, &enableScreenShare,
			&enableChat, &autoJoin, &requireApproval, &defaultRole, &expiresAt,
			&isActive, &totalClicks, &uniqueVisitors, &createdAt, &lastUsedAt); err != nil {
			continue
		}

		link := map[string]interface{}{
			"link_id":             linkID,
			"short_code":          shortCode,
			"url":                 fmt.Sprintf("https://auralink.com/join/%s", shortCode),
			"link_type":           linkType,
			"title":               title,
			"description":         description,
			"access_type":         accessType,
			"current_uses":        currentUses.Int64,
			"enable_recording":    enableRecording,
			"enable_screen_share": enableScreenShare,
			"enable_chat":         enableChat,
			"auto_join":           autoJoin,
			"require_approval":    requireApproval,
			"default_role":        defaultRole,
			"is_active":           isActive,
			"total_clicks":        totalClicks.Int64,
			"unique_visitors":     uniqueVisitors.Int64,
			"created_at":          createdAt,
		}

		if roomID.Valid {
			link["room_id"] = roomID.String
		}
		if callID.Valid {
			link["call_id"] = callID.String
		}
		if maxUses.Valid {
			link["max_uses"] = maxUses.Int64
		}
		if expiresAt.Valid {
			link["expires_at"] = expiresAt.Time
		}
		if lastUsedAt.Valid {
			link["last_used_at"] = lastUsedAt.Time
		}

		links = append(links, link)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"links": links,
		"total": len(links),
	})
}

// GetLink retrieves link details
func GetLink(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	linkID := vars["link_id"]

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	query := `
		SELECT link_id, short_code, room_id, call_id, link_type, title, description,
		       access_type, max_uses, current_uses, enable_recording, enable_screen_share,
		       enable_chat, auto_join, require_approval, default_role, expires_at,
		       is_active, total_clicks, unique_visitors, created_at, last_used_at, metadata
		FROM shareable_links
		WHERE link_id = $1
	`

	var shortCode, linkType, title, description, accessType, defaultRole string
	var roomID, callID sql.NullString
	var maxUses, currentUses, totalClicks, uniqueVisitors sql.NullInt64
	var enableRecording, enableScreenShare, enableChat, autoJoin, requireApproval, isActive bool
	var expiresAt, lastUsedAt sql.NullTime
	var createdAt time.Time
	var metadata []byte

	err := db.QueryRowContext(ctx, query, linkID).Scan(
		&linkID, &shortCode, &roomID, &callID, &linkType, &title, &description,
		&accessType, &maxUses, &currentUses, &enableRecording, &enableScreenShare,
		&enableChat, &autoJoin, &requireApproval, &defaultRole, &expiresAt,
		&isActive, &totalClicks, &uniqueVisitors, &createdAt, &lastUsedAt, &metadata,
	)

	if err == sql.ErrNoRows {
		sendError(w, "NOT_FOUND", "Link not found", http.StatusNotFound)
		return
	} else if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to get link: %v", err), http.StatusInternalServerError)
		return
	}

	var metadataMap map[string]interface{}
	json.Unmarshal(metadata, &metadataMap)

	link := map[string]interface{}{
		"link_id":             linkID,
		"short_code":          shortCode,
		"url":                 fmt.Sprintf("https://auralink.com/join/%s", shortCode),
		"link_type":           linkType,
		"title":               title,
		"description":         description,
		"access_type":         accessType,
		"current_uses":        currentUses.Int64,
		"enable_recording":    enableRecording,
		"enable_screen_share": enableScreenShare,
		"enable_chat":         enableChat,
		"auto_join":           autoJoin,
		"require_approval":    requireApproval,
		"default_role":        defaultRole,
		"is_active":           isActive,
		"total_clicks":        totalClicks.Int64,
		"unique_visitors":     uniqueVisitors.Int64,
		"created_at":          createdAt,
		"metadata":            metadataMap,
	}

	if roomID.Valid {
		link["room_id"] = roomID.String
	}
	if callID.Valid {
		link["call_id"] = callID.String
	}
	if maxUses.Valid {
		link["max_uses"] = maxUses.Int64
	}
	if expiresAt.Valid {
		link["expires_at"] = expiresAt.Time
	}
	if lastUsedAt.Valid {
		link["last_used_at"] = lastUsedAt.Time
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(link)
}

// ValidateLinkRequest represents link validation request
type ValidateLinkRequest struct {
	Password string `json:"password"`
}

// ValidateLink validates and provides access to a shareable link
func ValidateLink(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	shortCode := vars["short_code"]

	var req ValidateLinkRequest
	json.NewDecoder(r.Body).Decode(&req)

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Get link details
	query := `
		SELECT link_id, room_id, call_id, access_type, password_hash, max_uses,
		       current_uses, is_active, expires_at, require_approval
		FROM shareable_links
		WHERE short_code = $1
	`

	var linkID, accessType string
	var roomID, callID sql.NullString
	var passwordHash sql.NullString
	var maxUses, currentUses sql.NullInt64
	var isActive, requireApproval bool
	var expiresAt sql.NullTime

	err := db.QueryRowContext(ctx, query, shortCode).Scan(
		&linkID, &roomID, &callID, &accessType, &passwordHash, &maxUses,
		&currentUses, &isActive, &expiresAt, &requireApproval,
	)

	if err == sql.ErrNoRows {
		sendError(w, "NOT_FOUND", "Link not found", http.StatusNotFound)
		return
	} else if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to get link: %v", err), http.StatusInternalServerError)
		return
	}

	// Validate link
	if !isActive {
		sendError(w, "LINK_INACTIVE", "This link is no longer active", http.StatusForbidden)
		return
	}

	if expiresAt.Valid && time.Now().After(expiresAt.Time) {
		sendError(w, "LINK_EXPIRED", "This link has expired", http.StatusForbidden)
		return
	}

	if maxUses.Valid && currentUses.Int64 >= maxUses.Int64 {
		sendError(w, "LINK_EXHAUSTED", "This link has reached its usage limit", http.StatusForbidden)
		return
	}

	// Check password if required
	if accessType == "password" {
		if req.Password == "" {
			sendError(w, "PASSWORD_REQUIRED", "Password is required", http.StatusUnauthorized)
			return
		}
		if passwordHash.Valid {
			err := bcrypt.CompareHashAndPassword([]byte(passwordHash.String), []byte(req.Password))
			if err != nil {
				sendError(w, "INVALID_PASSWORD", "Incorrect password", http.StatusUnauthorized)
				return
			}
		}
	}

	// Update analytics
	_, _ = db.ExecContext(ctx, `
		UPDATE shareable_links 
		SET total_clicks = total_clicks + 1, last_used_at = NOW()
		WHERE link_id = $1
	`, linkID)

	response := map[string]interface{}{
		"valid":            true,
		"link_id":          linkID,
		"room_id":          roomID.String,
		"call_id":          callID.String,
		"require_approval": requireApproval,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// UpdateLink updates a shareable link
func UpdateLink(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	linkID := vars["link_id"]
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	var req map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, "VALIDATION_ERROR", "Invalid request body", http.StatusBadRequest)
		return
	}

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Verify ownership
	var createdBy uuid.UUID
	err := db.QueryRowContext(ctx, "SELECT created_by FROM shareable_links WHERE link_id = $1", linkID).Scan(&createdBy)
	if err == sql.ErrNoRows {
		sendError(w, "NOT_FOUND", "Link not found", http.StatusNotFound)
		return
	} else if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to get link: %v", err), http.StatusInternalServerError)
		return
	}

	if createdBy != userUUID {
		sendError(w, "FORBIDDEN", "Only the creator can update this link", http.StatusForbidden)
		return
	}

	// Build update query dynamically
	updates := []string{}
	args := []interface{}{}
	argCount := 1

	if title, ok := req["title"]; ok {
		updates = append(updates, fmt.Sprintf("title = $%d", argCount))
		args = append(args, title)
		argCount++
	}
	if description, ok := req["description"]; ok {
		updates = append(updates, fmt.Sprintf("description = $%d", argCount))
		args = append(args, description)
		argCount++
	}
	if isActive, ok := req["is_active"]; ok {
		updates = append(updates, fmt.Sprintf("is_active = $%d", argCount))
		args = append(args, isActive)
		argCount++
	}

	if len(updates) == 0 {
		sendError(w, "VALIDATION_ERROR", "No fields to update", http.StatusBadRequest)
		return
	}

	args = append(args, linkID)
	query := fmt.Sprintf("UPDATE shareable_links SET %s WHERE link_id = $%d", 
		string(updates[0]), argCount)
	for i := 1; i < len(updates); i++ {
		query = fmt.Sprintf("%s, %s", query, updates[i])
	}

	_, err = db.ExecContext(ctx, query, args...)
	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to update link: %v", err), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"message": "Link updated successfully",
	})
}

// DeleteLink deletes a shareable link
func DeleteLink(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	linkID := vars["link_id"]
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Verify ownership
	var createdBy uuid.UUID
	err := db.QueryRowContext(ctx, "SELECT created_by FROM shareable_links WHERE link_id = $1", linkID).Scan(&createdBy)
	if err == sql.ErrNoRows {
		sendError(w, "NOT_FOUND", "Link not found", http.StatusNotFound)
		return
	} else if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to get link: %v", err), http.StatusInternalServerError)
		return
	}

	if createdBy != userUUID {
		sendError(w, "FORBIDDEN", "Only the creator can delete this link", http.StatusForbidden)
		return
	}

	_, err = db.ExecContext(ctx, "DELETE FROM shareable_links WHERE link_id = $1", linkID)
	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to delete link: %v", err), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}
