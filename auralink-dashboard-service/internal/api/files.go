package api

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"github.com/auralink/dashboard-service/internal/middleware"
	"github.com/auralink/shared/storage"
	"github.com/auralink/shared/database"
)

const (
	MaxFileSize = 100 * 1024 * 1024 // 100 MB
)

// UploadFileRequest represents file upload request
type UploadFileRequest struct {
	CallID      string `json:"call_id"`
	RoomName    string `json:"room_name"`
	AccessLevel string `json:"access_level"` // public, call_participants, private
	ExpiresIn   int    `json:"expires_in_hours"`
}

// UploadFile handles file upload during calls
func UploadFile(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	// Parse multipart form (32 MB max memory)
	err := r.ParseMultipartForm(32 << 20)
	if err != nil {
		sendError(w, "VALIDATION_ERROR", "Failed to parse form", http.StatusBadRequest)
		return
	}

	// Get file from form
	file, header, err := r.FormFile("file")
	if err != nil {
		sendError(w, "VALIDATION_ERROR", "File is required", http.StatusBadRequest)
		return
	}
	defer file.Close()

	// Check file size
	if header.Size > MaxFileSize {
		sendError(w, "FILE_TOO_LARGE", fmt.Sprintf("File size exceeds %d MB", MaxFileSize/(1024*1024)), http.StatusBadRequest)
		return
	}

	// Get form parameters
	callID := r.FormValue("call_id")
	roomName := r.FormValue("room_name")
	accessLevel := r.FormValue("access_level")
	expiresInStr := r.FormValue("expires_in_hours")

	if callID == "" && roomName == "" {
		sendError(w, "VALIDATION_ERROR", "Either call_id or room_name is required", http.StatusBadRequest)
		return
	}

	if accessLevel == "" {
		accessLevel = "call_participants"
	}

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Verify call exists and user has access
	if callID != "" {
		var exists bool
		err = db.QueryRowContext(ctx, `
			SELECT EXISTS(
				SELECT 1 FROM calls c
				LEFT JOIN call_participants cp ON c.call_id = cp.call_id
				WHERE c.call_id = $1 AND (c.created_by = $2 OR cp.user_id = $2)
			)
		`, callID, userUUID).Scan(&exists)
		
		if err != nil || !exists {
			sendError(w, "FORBIDDEN", "Access denied to this call", http.StatusForbidden)
			return
		}

		// Get room name from call
		db.QueryRowContext(ctx, "SELECT room_name FROM calls WHERE call_id = $1", callID).Scan(&roomName)
	}

	// Get storage client
	storageClient := storage.GetClient()
	if storageClient == nil {
		sendError(w, "SERVER_ERROR", "Storage not available", http.StatusInternalServerError)
		return
	}

	// Upload file to storage
	storagePath, downloadURL, err := storageClient.UploadFile(ctx, file, storage.FileUploadOptions{
		FileName:    header.Filename,
		ContentType: header.Header.Get("Content-Type"),
		UserID:      userID,
		CallID:      callID,
		IsPublic:    accessLevel == "public",
	})

	if err != nil {
		sendError(w, "STORAGE_ERROR", fmt.Sprintf("Failed to upload file: %v", err), http.StatusInternalServerError)
		return
	}

	// Create database record
	fileID := uuid.New()
	var expiresAt *time.Time
	if expiresInStr != "" {
		if hours, err := strconv.Atoi(expiresInStr); err == nil && hours > 0 {
			expiry := time.Now().Add(time.Duration(hours) * time.Hour)
			expiresAt = &expiry
		}
	}

	query := `
		INSERT INTO files (
			file_id, call_id, room_name, uploader_id, uploader_identity,
			file_name, file_type, file_size, storage_path, storage_bucket,
			download_url, access_level, expires_at, scan_status
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
		RETURNING created_at
	`

	var callUUID *uuid.UUID
	if callID != "" {
		parsed, _ := uuid.Parse(callID)
		callUUID = &parsed
	}

	var createdAt time.Time
	err = db.QueryRowContext(ctx, query,
		fileID, callUUID, roomName, userUUID, userID,
		header.Filename, header.Header.Get("Content-Type"), header.Size,
		storagePath, "auralink-files", downloadURL, accessLevel,
		expiresAt, "pending",
	).Scan(&createdAt)

	if err != nil {
		// Try to delete uploaded file on error
		storageClient.DeleteFile(ctx, storagePath)
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to save file record: %v", err), http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"file_id":      fileID.String(),
		"file_name":    header.Filename,
		"file_size":    header.Size,
		"file_type":    header.Header.Get("Content-Type"),
		"download_url": downloadURL,
		"access_level": accessLevel,
		"created_at":   createdAt,
		"call_id":      callID,
		"room_name":    roomName,
	}

	if expiresAt != nil {
		response["expires_at"] = expiresAt
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(response)
}

// ListFiles lists files for a call or room
func ListFiles(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	callID := r.URL.Query().Get("call_id")
	roomName := r.URL.Query().Get("room_name")

	if callID == "" && roomName == "" {
		sendError(w, "VALIDATION_ERROR", "Either call_id or room_name is required", http.StatusBadRequest)
		return
	}

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	query := `
		SELECT f.file_id, f.file_name, f.file_type, f.file_size, f.download_url,
		       f.access_level, f.created_at, f.expires_at, f.scan_status,
		       u.display_name as uploader_name, u.aura_id as uploader_aura_id
		FROM files f
		LEFT JOIN users u ON f.uploader_id = u.user_id
		WHERE (f.access_level = 'public' OR f.uploader_id = $1 OR EXISTS (
			SELECT 1 FROM call_participants cp
			WHERE cp.call_id = f.call_id AND cp.user_id = $1
		))
	`

	var rows *sql.Rows
	var err error

	if callID != "" {
		query += " AND f.call_id = $2"
		rows, err = db.QueryContext(ctx, query, userUUID, callID)
	} else {
		query += " AND f.room_name = $2"
		rows, err = db.QueryContext(ctx, query, userUUID, roomName)
	}

	query += " ORDER BY f.created_at DESC"

	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to query files: %v", err), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	files := []map[string]interface{}{}
	for rows.Next() {
		var fileID, fileName, fileType, downloadURL, accessLevel, scanStatus string
		var fileSize int64
		var createdAt time.Time
		var expiresAt sql.NullTime
		var uploaderName, uploaderAuraID sql.NullString

		if err := rows.Scan(&fileID, &fileName, &fileType, &fileSize, &downloadURL,
			&accessLevel, &createdAt, &expiresAt, &scanStatus,
			&uploaderName, &uploaderAuraID); err != nil {
			continue
		}

		file := map[string]interface{}{
			"file_id":           fileID,
			"file_name":         fileName,
			"file_type":         fileType,
			"file_size":         fileSize,
			"download_url":      downloadURL,
			"access_level":      accessLevel,
			"scan_status":       scanStatus,
			"created_at":        createdAt,
			"uploader_name":     uploaderName.String,
			"uploader_aura_id":  uploaderAuraID.String,
		}

		if expiresAt.Valid {
			file["expires_at"] = expiresAt.Time
		}

		files = append(files, file)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"files": files,
		"total": len(files),
	})
}

// GetFile retrieves file details
func GetFile(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	fileID := vars["file_id"]
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	query := `
		SELECT f.file_id, f.file_name, f.file_type, f.file_size, f.download_url,
		       f.access_level, f.created_at, f.expires_at, f.scan_status, f.storage_path,
		       u.display_name as uploader_name, u.aura_id as uploader_aura_id
		FROM files f
		LEFT JOIN users u ON f.uploader_id = u.user_id
		WHERE f.file_id = $1
	`

	var fileName, fileType, downloadURL, accessLevel, scanStatus, storagePath string
	var fileSize int64
	var createdAt time.Time
	var expiresAt sql.NullTime
	var uploaderName, uploaderAuraID sql.NullString

	err := db.QueryRowContext(ctx, query, fileID).Scan(
		&fileID, &fileName, &fileType, &fileSize, &downloadURL,
		&accessLevel, &createdAt, &expiresAt, &scanStatus, &storagePath,
		&uploaderName, &uploaderAuraID,
	)

	if err == sql.ErrNoRows {
		sendError(w, "NOT_FOUND", "File not found", http.StatusNotFound)
		return
	} else if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to get file: %v", err), http.StatusInternalServerError)
		return
	}

	// Check access permissions
	if accessLevel != "public" {
		var hasAccess bool
		db.QueryRowContext(ctx, `
			SELECT EXISTS(
				SELECT 1 FROM files f
				LEFT JOIN call_participants cp ON f.call_id = cp.call_id
				WHERE f.file_id = $1 AND (f.uploader_id = $2 OR cp.user_id = $2)
			)
		`, fileID, userUUID).Scan(&hasAccess)

		if !hasAccess {
			sendError(w, "FORBIDDEN", "Access denied to this file", http.StatusForbidden)
			return
		}
	}

	// Generate fresh signed URL
	storageClient := storage.GetClient()
	if storageClient != nil {
		newURL, err := storageClient.GetSignedURL(ctx, storagePath, 3600) // 1 hour
		if err == nil {
			downloadURL = newURL
		}
	}

	file := map[string]interface{}{
		"file_id":          fileID,
		"file_name":        fileName,
		"file_type":        fileType,
		"file_size":        fileSize,
		"download_url":     downloadURL,
		"access_level":     accessLevel,
		"scan_status":      scanStatus,
		"created_at":       createdAt,
		"uploader_name":    uploaderName.String,
		"uploader_aura_id": uploaderAuraID.String,
	}

	if expiresAt.Valid {
		file["expires_at"] = expiresAt.Time
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(file)
}

// DeleteFile deletes a file
func DeleteFile(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	fileID := vars["file_id"]
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Check if user owns the file
	var storagePath string
	var uploaderID uuid.UUID
	err := db.QueryRowContext(ctx, "SELECT storage_path, uploader_id FROM files WHERE file_id = $1", fileID).Scan(&storagePath, &uploaderID)
	if err == sql.ErrNoRows {
		sendError(w, "NOT_FOUND", "File not found", http.StatusNotFound)
		return
	} else if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to get file: %v", err), http.StatusInternalServerError)
		return
	}

	if uploaderID != userUUID {
		sendError(w, "FORBIDDEN", "Only the uploader can delete this file", http.StatusForbidden)
		return
	}

	// Delete from storage
	storageClient := storage.GetClient()
	if storageClient != nil {
		err = storageClient.DeleteFile(ctx, storagePath)
		if err != nil {
			fmt.Printf("Failed to delete file from storage: %v\n", err)
			// Continue with database deletion
		}
	}

	// Delete from database
	_, err = db.ExecContext(ctx, "DELETE FROM files WHERE file_id = $1", fileID)
	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to delete file: %v", err), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// DownloadFile streams file for download
func DownloadFile(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	fileID := vars["file_id"]
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Get file info and check access
	var fileName, fileType, downloadURL, accessLevel string
	err := db.QueryRowContext(ctx, `
		SELECT f.file_name, f.file_type, f.download_url, f.access_level
		FROM files f
		WHERE f.file_id = $1
	`, fileID).Scan(&fileName, &fileType, &downloadURL, &accessLevel)

	if err == sql.ErrNoRows {
		sendError(w, "NOT_FOUND", "File not found", http.StatusNotFound)
		return
	} else if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to get file: %v", err), http.StatusInternalServerError)
		return
	}

	// Check access permissions
	if accessLevel != "public" {
		var hasAccess bool
		db.QueryRowContext(ctx, `
			SELECT EXISTS(
				SELECT 1 FROM files f
				LEFT JOIN call_participants cp ON f.call_id = cp.call_id
				WHERE f.file_id = $1 AND (f.uploader_id = $2 OR cp.user_id = $2)
			)
		`, fileID, userUUID).Scan(&hasAccess)

		if !hasAccess {
			sendError(w, "FORBIDDEN", "Access denied to this file", http.StatusForbidden)
			return
		}
	}

	// Redirect to download URL (signed URL from storage)
	http.Redirect(w, r, downloadURL, http.StatusTemporaryRedirect)
}
