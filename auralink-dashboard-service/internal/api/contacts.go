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

// CreateContactRequest represents contact creation request
type CreateContactRequest struct {
	ContactUserID    string `json:"contact_user_id"`    // UUID of the user to add as contact
	ContactAuraID    string `json:"contact_aura_id"`    // Or AuraID to lookup
	RelationshipType string `json:"relationship_type"`  // friend, colleague
	Nickname         string `json:"nickname"`
	Notes            string `json:"notes"`
	Tags             []string `json:"tags"`
}

// CreateContact creates a new contact
func CreateContact(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	var req CreateContactRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, "VALIDATION_ERROR", "Invalid request body", http.StatusBadRequest)
		return
	}

	if req.ContactUserID == "" && req.ContactAuraID == "" {
		sendError(w, "VALIDATION_ERROR", "Either contact_user_id or contact_aura_id is required", http.StatusBadRequest)
		return
	}

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Resolve contact user ID from AuraID if needed
	var contactUserID uuid.UUID
	if req.ContactUserID != "" {
		contactUserID, _ = uuid.Parse(req.ContactUserID)
	} else {
		err := db.QueryRowContext(ctx, "SELECT user_id FROM users WHERE aura_id = $1", req.ContactAuraID).Scan(&contactUserID)
		if err == sql.ErrNoRows {
			sendError(w, "NOT_FOUND", "User with this AuraID not found", http.StatusNotFound)
			return
		} else if err != nil {
			sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to lookup user: %v", err), http.StatusInternalServerError)
			return
		}
	}

	// Prevent adding self as contact
	if contactUserID == userUUID {
		sendError(w, "VALIDATION_ERROR", "Cannot add yourself as a contact", http.StatusBadRequest)
		return
	}

	// Set defaults
	if req.RelationshipType == "" {
		req.RelationshipType = "friend"
	}

	// Insert contact
	contactID := uuid.New()
	tagsJSON, _ := json.Marshal(req.Tags)
	
	query := `
		INSERT INTO contacts (contact_id, user_id, contact_user_id, relationship_type, nickname, notes, tags, metadata)
		VALUES ($1, $2, $3, $4, $5, $6, $7, '{}')
		RETURNING created_at
	`

	var createdAt time.Time
	err := db.QueryRowContext(ctx, query,
		contactID, userUUID, contactUserID, req.RelationshipType, req.Nickname, req.Notes, tagsJSON,
	).Scan(&createdAt)

	if err != nil {
		if err.Error() == "pq: duplicate key value violates unique constraint \"contacts_unique_pair\"" {
			sendError(w, "CONFLICT", "Contact already exists", http.StatusConflict)
			return
		}
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to create contact: %v", err), http.StatusInternalServerError)
		return
	}

	// Get contact details
	var displayName, auraID, email string
	db.QueryRowContext(ctx, "SELECT display_name, aura_id, email FROM users WHERE user_id = $1", contactUserID).Scan(&displayName, &auraID, &email)

	response := map[string]interface{}{
		"contact_id":        contactID.String(),
		"user_id":           userID,
		"contact_user_id":   contactUserID.String(),
		"contact_name":      displayName,
		"contact_aura_id":   auraID,
		"contact_email":     email,
		"relationship_type": req.RelationshipType,
		"nickname":          req.Nickname,
		"notes":             req.Notes,
		"tags":              req.Tags,
		"created_at":        createdAt,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(response)
}

// ListContacts lists user's contacts
func ListContacts(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	// Get query parameters
	relationshipType := r.URL.Query().Get("relationship_type")
	isFavorite := r.URL.Query().Get("is_favorite")

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	query := `
		SELECT c.contact_id, c.contact_user_id, c.relationship_type, c.nickname,
		       c.notes, c.tags, c.is_favorite, c.is_blocked, c.created_at, c.updated_at,
		       u.display_name, u.aura_id, u.email, u.avatar_url, u.status
		FROM contacts c
		LEFT JOIN users u ON c.contact_user_id = u.user_id
		WHERE c.user_id = $1
	`

	args := []interface{}{userUUID}
	argPos := 2

	if relationshipType != "" {
		query += fmt.Sprintf(" AND c.relationship_type = $%d", argPos)
		args = append(args, relationshipType)
		argPos++
	}

	if isFavorite == "true" {
		query += " AND c.is_favorite = TRUE"
	}

	query += " ORDER BY c.is_favorite DESC, u.display_name ASC"

	rows, err := db.QueryContext(ctx, query, args...)
	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to query contacts: %v", err), http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	contacts := []map[string]interface{}{}
	for rows.Next() {
		var contactID, contactUserID, relationshipType, nickname, notes string
		var tags []byte
		var isFavorite, isBlocked bool
		var createdAt, updatedAt time.Time
		var displayName, auraID, email, avatarURL, status sql.NullString

		if err := rows.Scan(&contactID, &contactUserID, &relationshipType, &nickname,
			&notes, &tags, &isFavorite, &isBlocked, &createdAt, &updatedAt,
			&displayName, &auraID, &email, &avatarURL, &status); err != nil {
			continue
		}

		var tagsList []string
		json.Unmarshal(tags, &tagsList)

		contact := map[string]interface{}{
			"contact_id":        contactID,
			"contact_user_id":   contactUserID,
			"contact_name":      displayName.String,
			"contact_aura_id":   auraID.String,
			"contact_email":     email.String,
			"contact_avatar":    avatarURL.String,
			"contact_status":    status.String,
			"relationship_type": relationshipType,
			"nickname":          nickname,
			"notes":             notes,
			"tags":              tagsList,
			"is_favorite":       isFavorite,
			"is_blocked":        isBlocked,
			"created_at":        createdAt,
			"updated_at":        updatedAt,
		}

		contacts = append(contacts, contact)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"contacts": contacts,
		"total":    len(contacts),
	})
}

// UpdateContactRequest represents contact update request
type UpdateContactRequest struct {
	RelationshipType *string  `json:"relationship_type,omitempty"`
	Nickname         *string  `json:"nickname,omitempty"`
	Notes            *string  `json:"notes,omitempty"`
	Tags             []string `json:"tags,omitempty"`
	IsFavorite       *bool    `json:"is_favorite,omitempty"`
	IsBlocked        *bool    `json:"is_blocked,omitempty"`
}

// UpdateContact updates a contact
func UpdateContact(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	contactID := vars["contact_id"]
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	var req UpdateContactRequest
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
	var ownerID uuid.UUID
	err := db.QueryRowContext(ctx, "SELECT user_id FROM contacts WHERE contact_id = $1", contactID).Scan(&ownerID)
	if err == sql.ErrNoRows {
		sendError(w, "NOT_FOUND", "Contact not found", http.StatusNotFound)
		return
	} else if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to get contact: %v", err), http.StatusInternalServerError)
		return
	}

	if ownerID != userUUID {
		sendError(w, "FORBIDDEN", "You can only update your own contacts", http.StatusForbidden)
		return
	}

	// Build update query dynamically
	updates := []string{}
	args := []interface{}{}
	argPos := 1

	if req.RelationshipType != nil {
		updates = append(updates, fmt.Sprintf("relationship_type = $%d", argPos))
		args = append(args, *req.RelationshipType)
		argPos++
	}
	if req.Nickname != nil {
		updates = append(updates, fmt.Sprintf("nickname = $%d", argPos))
		args = append(args, *req.Nickname)
		argPos++
	}
	if req.Notes != nil {
		updates = append(updates, fmt.Sprintf("notes = $%d", argPos))
		args = append(args, *req.Notes)
		argPos++
	}
	if req.Tags != nil {
		tagsJSON, _ := json.Marshal(req.Tags)
		updates = append(updates, fmt.Sprintf("tags = $%d", argPos))
		args = append(args, tagsJSON)
		argPos++
	}
	if req.IsFavorite != nil {
		updates = append(updates, fmt.Sprintf("is_favorite = $%d", argPos))
		args = append(args, *req.IsFavorite)
		argPos++
	}
	if req.IsBlocked != nil {
		updates = append(updates, fmt.Sprintf("is_blocked = $%d", argPos))
		args = append(args, *req.IsBlocked)
		argPos++
	}

	if len(updates) == 0 {
		sendError(w, "VALIDATION_ERROR", "No fields to update", http.StatusBadRequest)
		return
	}

	query := fmt.Sprintf("UPDATE contacts SET %s, updated_at = NOW() WHERE contact_id = $%d", 
		fmt.Sprintf("%s", updates[0]), argPos)
	for i := 1; i < len(updates); i++ {
		query = fmt.Sprintf("UPDATE contacts SET %s, %s, updated_at = NOW() WHERE contact_id = $%d",
			updates[0], updates[i], argPos)
	}
	args = append(args, contactID)

	_, err = db.ExecContext(ctx, query, args...)
	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to update contact: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"contact_id": contactID,
		"updated":    true,
	})
}

// DeleteContact deletes a contact
func DeleteContact(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	contactID := vars["contact_id"]
	userID := r.Context().Value(middleware.UserIDKey).(string)
	userUUID, _ := uuid.Parse(userID)

	db := database.GetDB()
	if db == nil {
		sendError(w, "SERVER_ERROR", "Database not available", http.StatusInternalServerError)
		return
	}

	// Verify ownership
	var ownerID uuid.UUID
	err := db.QueryRowContext(ctx, "SELECT user_id FROM contacts WHERE contact_id = $1", contactID).Scan(&ownerID)
	if err == sql.ErrNoRows {
		sendError(w, "NOT_FOUND", "Contact not found", http.StatusNotFound)
		return
	} else if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to get contact: %v", err), http.StatusInternalServerError)
		return
	}

	if ownerID != userUUID {
		sendError(w, "FORBIDDEN", "You can only delete your own contacts", http.StatusForbidden)
		return
	}

	// Delete contact
	_, err = db.ExecContext(ctx, "DELETE FROM contacts WHERE contact_id = $1", contactID)
	if err != nil {
		sendError(w, "DATABASE_ERROR", fmt.Sprintf("Failed to delete contact: %v", err), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}
