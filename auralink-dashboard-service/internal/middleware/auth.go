// Package middleware provides HTTP middleware functions
package middleware

import (
	"context"
	"net/http"
	"strings"

	"github.com/golang-jwt/jwt/v5"
	"github.com/auralink/dashboard-service/internal/config"
)

// Claims represents JWT claims
type Claims struct {
	Sub   string `json:"sub"`
	Email string `json:"email"`
	Role  string `json:"role"`
	jwt.RegisteredClaims
}

// ContextKey for storing user info in context
type ContextKey string

const (
	UserIDKey    ContextKey = "user_id"
	EmailKey     ContextKey = "email"
	RoleKey      ContextKey = "role"
)

// AuthMiddleware creates authentication middleware
func AuthMiddleware(cfg *config.Config) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Extract token from Authorization header
			authHeader := r.Header.Get("Authorization")
			if authHeader == "" {
				http.Error(w, `{"code":"UNAUTHORIZED","message":"Missing authorization header"}`, http.StatusUnauthorized)
				return
			}

			// Check Bearer prefix
			parts := strings.Split(authHeader, " ")
			if len(parts) != 2 || parts[0] != "Bearer" {
				http.Error(w, `{"code":"UNAUTHORIZED","message":"Invalid authorization header format"}`, http.StatusUnauthorized)
				return
			}

			tokenString := parts[1]

			// Parse and verify token
			token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
				// Verify signing method
				if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
					return nil, jwt.ErrSignatureInvalid
				}
				return []byte(cfg.Auth.JWTSecret), nil
			})

			if err != nil || !token.Valid {
				http.Error(w, `{"code":"INVALID_TOKEN","message":"Invalid or expired token"}`, http.StatusUnauthorized)
				return
			}

			// Extract claims
			if claims, ok := token.Claims.(*Claims); ok {
				// Add user info to context
				ctx := context.WithValue(r.Context(), UserIDKey, claims.Sub)
				ctx = context.WithValue(ctx, EmailKey, claims.Email)
				ctx = context.WithValue(ctx, RoleKey, claims.Role)

				// Call next handler with updated context
				next.ServeHTTP(w, r.WithContext(ctx))
			} else {
				http.Error(w, `{"code":"INVALID_TOKEN","message":"Invalid token claims"}`, http.StatusUnauthorized)
				return
			}
		})
	}
}

// RequireRole creates a middleware that requires a specific role
func RequireRole(role string) func(http.Handler) http.Handler {
	roleHierarchy := map[string]int{
		"user":      0,
		"moderator": 1,
		"admin":     2,
	}

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			userRole, ok := r.Context().Value(RoleKey).(string)
			if !ok {
				http.Error(w, `{"code":"FORBIDDEN","message":"User role not found"}`, http.StatusForbidden)
				return
			}

			requiredLevel := roleHierarchy[role]
			userLevel := roleHierarchy[userRole]

			if userLevel < requiredLevel {
				http.Error(w, `{"code":"FORBIDDEN","message":"Insufficient permissions"}`, http.StatusForbidden)
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}
