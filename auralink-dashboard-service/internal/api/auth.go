package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

// SignUpRequest represents signup payload
type SignUpRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
	Name     string `json:"name,omitempty"`
}

// LoginRequest represents login payload
type LoginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

// AuthResponse represents auth response
type AuthResponse struct {
	AccessToken  string    `json:"access_token"`
	RefreshToken string    `json:"refresh_token,omitempty"`
	User         User      `json:"user"`
	ExpiresAt    time.Time `json:"expires_at"`
}

// User represents user data
type User struct {
	ID        string    `json:"id"`
	Email     string    `json:"email"`
	Name      string    `json:"name,omitempty"`
	CreatedAt time.Time `json:"created_at"`
}

// SignUp handles user registration
func SignUp(w http.ResponseWriter, r *http.Request) {
	var req SignUpRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, "VALIDATION_ERROR", "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate input
	if req.Email == "" || req.Password == "" {
		sendError(w, "VALIDATION_ERROR", "Email and password are required", http.StatusBadRequest)
		return
	}

	// Call Supabase signup endpoint
	supabaseURL := os.Getenv("SUPABASE_URL")
	anonKey := os.Getenv("SUPABASE_ANON_KEY")

	payload := map[string]string{
		"email":    req.Email,
		"password": req.Password,
	}
	
	data, _ := json.Marshal(payload)
	
	supabaseReq, err := http.NewRequest(
		"POST",
		supabaseURL+"/auth/v1/signup",
		bytes.NewReader(data),
	)
	if err != nil {
		sendError(w, "INTERNAL_ERROR", "Failed to create request", http.StatusInternalServerError)
		return
	}

	supabaseReq.Header.Set("Content-Type", "application/json")
	supabaseReq.Header.Set("apikey", anonKey)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(supabaseReq)
	if err != nil {
		sendError(w, "SUPABASE_ERROR", "Failed to register user", http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		sendError(w, "REGISTRATION_FAILED", string(body), resp.StatusCode)
		return
	}

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		sendError(w, "INTERNAL_ERROR", "Failed to parse response", http.StatusInternalServerError)
		return
	}

	// TODO: Create user record in our database
	
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(result)
}

// Login handles user authentication
func Login(w http.ResponseWriter, r *http.Request) {
	var req LoginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, "VALIDATION_ERROR", "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate input
	if req.Email == "" || req.Password == "" {
		sendError(w, "VALIDATION_ERROR", "Email and password are required", http.StatusBadRequest)
		return
	}

	// Call Supabase login endpoint
	supabaseURL := os.Getenv("SUPABASE_URL")
	anonKey := os.Getenv("SUPABASE_ANON_KEY")

	payload := map[string]string{
		"email":    req.Email,
		"password": req.Password,
	}
	
	data, _ := json.Marshal(payload)
	
	supabaseReq, err := http.NewRequest(
		"POST",
		supabaseURL+"/auth/v1/token?grant_type=password",
		bytes.NewReader(data),
	)
	if err != nil {
		sendError(w, "INTERNAL_ERROR", "Failed to create request", http.StatusInternalServerError)
		return
	}

	supabaseReq.Header.Set("Content-Type", "application/json")
	supabaseReq.Header.Set("apikey", anonKey)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(supabaseReq)
	if err != nil {
		sendError(w, "SUPABASE_ERROR", "Failed to authenticate", http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		sendError(w, "INVALID_CREDENTIALS", "Invalid email or password", http.StatusUnauthorized)
		return
	}

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		sendError(w, "INTERNAL_ERROR", "Failed to parse response", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(result)
}

// RefreshToken handles token refresh
func RefreshToken(w http.ResponseWriter, r *http.Request) {
	var req struct {
		RefreshToken string `json:"refresh_token"`
	}
	
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		sendError(w, "VALIDATION_ERROR", "Invalid request body", http.StatusBadRequest)
		return
	}

	if req.RefreshToken == "" {
		sendError(w, "VALIDATION_ERROR", "Refresh token is required", http.StatusBadRequest)
		return
	}

	// Call Supabase refresh endpoint
	supabaseURL := os.Getenv("SUPABASE_URL")
	anonKey := os.Getenv("SUPABASE_ANON_KEY")

	payload := map[string]string{
		"refresh_token": req.RefreshToken,
	}
	
	data, _ := json.Marshal(payload)
	
	supabaseReq, err := http.NewRequest(
		"POST",
		supabaseURL+"/auth/v1/token?grant_type=refresh_token",
		bytes.NewReader(data),
	)
	if err != nil {
		sendError(w, "INTERNAL_ERROR", "Failed to create request", http.StatusInternalServerError)
		return
	}

	supabaseReq.Header.Set("Content-Type", "application/json")
	supabaseReq.Header.Set("apikey", anonKey)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(supabaseReq)
	if err != nil {
		sendError(w, "SUPABASE_ERROR", "Failed to refresh token", http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		sendError(w, "INVALID_TOKEN", "Invalid refresh token", http.StatusUnauthorized)
		return
	}

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		sendError(w, "INTERNAL_ERROR", "Failed to parse response", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(result)
}

// Logout handles user logout
func Logout(w http.ResponseWriter, r *http.Request) {
	// Extract token from header
	authHeader := r.Header.Get("Authorization")
	if authHeader == "" {
		sendError(w, "UNAUTHORIZED", "Missing authorization header", http.StatusUnauthorized)
		return
	}

	// Call Supabase logout endpoint
	supabaseURL := os.Getenv("SUPABASE_URL")
	anonKey := os.Getenv("SUPABASE_ANON_KEY")

	supabaseReq, err := http.NewRequest(
		"POST",
		supabaseURL+"/auth/v1/logout",
		nil,
	)
	if err != nil {
		sendError(w, "INTERNAL_ERROR", "Failed to create request", http.StatusInternalServerError)
		return
	}

	supabaseReq.Header.Set("Authorization", authHeader)
	supabaseReq.Header.Set("apikey", anonKey)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(supabaseReq)
	if err != nil {
		sendError(w, "SUPABASE_ERROR", "Failed to logout", http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()

	w.WriteHeader(http.StatusNoContent)
}
