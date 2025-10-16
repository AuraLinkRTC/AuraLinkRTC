// AuraLink Dashboard Service - Billing & Subscriptions
// Package api provides billing and subscription management endpoints
package api

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/gorilla/mux"
	"github.com/google/uuid"
)

// Subscription represents a billing subscription
type Subscription struct {
	SubscriptionID           string     `json:"subscription_id"`
	OrganizationID           string     `json:"organization_id"`
	PlanName                 string     `json:"plan_name"`
	PlanInterval             string     `json:"plan_interval"`
	AmountUSD                float64    `json:"amount_usd"`
	Currency                 string     `json:"currency"`
	Status                   string     `json:"status"`
	StripeSubscriptionID     *string    `json:"stripe_subscription_id,omitempty"`
	StripeCustomerID         *string    `json:"stripe_customer_id,omitempty"`
	StripePriceID            *string    `json:"stripe_price_id,omitempty"`
	IncludedMinutes          int        `json:"included_minutes"`
	AdditionalMinutePriceUSD float64    `json:"additional_minute_price_usd"`
	IncludedAICalls          int        `json:"included_ai_calls"`
	AdditionalAICallPriceUSD float64    `json:"additional_ai_call_price_usd"`
	TrialEndsAt              *time.Time `json:"trial_ends_at,omitempty"`
	CurrentPeriodStart       time.Time  `json:"current_period_start"`
	CurrentPeriodEnd         time.Time  `json:"current_period_end"`
	CancelAtPeriodEnd        bool       `json:"cancel_at_period_end"`
	CancelledAt              *time.Time `json:"cancelled_at,omitempty"`
	CreatedAt                time.Time  `json:"created_at"`
	UpdatedAt                time.Time  `json:"updated_at"`
}

// Invoice represents a billing invoice
type Invoice struct {
	InvoiceID           string                 `json:"invoice_id"`
	OrganizationID      string                 `json:"organization_id"`
	SubscriptionID      *string                `json:"subscription_id,omitempty"`
	InvoiceNumber       string                 `json:"invoice_number"`
	SubtotalUSD         float64                `json:"subtotal_usd"`
	TaxUSD              float64                `json:"tax_usd"`
	TotalUSD            float64                `json:"total_usd"`
	Currency            string                 `json:"currency"`
	Status              string                 `json:"status"`
	StripeInvoiceID     *string                `json:"stripe_invoice_id,omitempty"`
	StripePaymentIntent *string                `json:"stripe_payment_intent_id,omitempty"`
	LineItems           []map[string]interface{} `json:"line_items"`
	InvoiceDate         string                 `json:"invoice_date"`
	DueDate             *string                `json:"due_date,omitempty"`
	PaidAt              *time.Time             `json:"paid_at,omitempty"`
	PaymentMethod       *string                `json:"payment_method,omitempty"`
	PDFURL              *string                `json:"pdf_url,omitempty"`
	CreatedAt           time.Time              `json:"created_at"`
	UpdatedAt           time.Time              `json:"updated_at"`
}

// UsageRecord represents a usage tracking record
type UsageRecord struct {
	RecordID           string     `json:"record_id"`
	OrganizationID     string     `json:"organization_id"`
	SubscriptionID     *string    `json:"subscription_id,omitempty"`
	UsageType          string     `json:"usage_type"`
	Quantity           int        `json:"quantity"`
	UnitPriceUSD       float64    `json:"unit_price_usd"`
	TotalCostUSD       float64    `json:"total_cost_usd"`
	ResourceID         *string    `json:"resource_id,omitempty"`
	BillingPeriodStart string     `json:"billing_period_start"`
	BillingPeriodEnd   string     `json:"billing_period_end"`
	Billed             bool       `json:"billed"`
	InvoiceID          *string    `json:"invoice_id,omitempty"`
	RecordedAt         time.Time  `json:"recorded_at"`
}

// CreateSubscription creates a new subscription
func CreateSubscription(w http.ResponseWriter, r *http.Request) {
	var req struct {
		OrganizationID           string  `json:"organization_id"`
		PlanName                 string  `json:"plan_name"`
		PlanInterval             string  `json:"plan_interval"`
		StripeCustomerID         *string `json:"stripe_customer_id,omitempty"`
		StripePriceID            *string `json:"stripe_price_id,omitempty"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Validate plan
	if req.PlanName != "free" && req.PlanName != "pro" && req.PlanName != "enterprise" && req.PlanName != "custom" {
		http.Error(w, "Invalid plan name", http.StatusBadRequest)
		return
	}

	subscriptionID := uuid.New().String()
	now := time.Now()
	periodEnd := now.AddDate(0, 1, 0) // 1 month from now

	// Set plan-specific defaults
	var amount float64
	var includedMinutes, includedAICalls int

	switch req.PlanName {
	case "free":
		amount = 0
		includedMinutes = 1000
		includedAICalls = 100
	case "pro":
		amount = 49.00
		includedMinutes = 10000
		includedAICalls = 1000
	case "enterprise":
		amount = 499.00
		includedMinutes = 100000
		includedAICalls = 10000
	}

	// TODO: Create subscription in Stripe and database
	subscription := Subscription{
		SubscriptionID:           subscriptionID,
		OrganizationID:           req.OrganizationID,
		PlanName:                 req.PlanName,
		PlanInterval:             req.PlanInterval,
		AmountUSD:                amount,
		Currency:                 "USD",
		Status:                   "active",
		StripeCustomerID:         req.StripeCustomerID,
		StripePriceID:            req.StripePriceID,
		IncludedMinutes:          includedMinutes,
		AdditionalMinutePriceUSD: 0.01,
		IncludedAICalls:          includedAICalls,
		AdditionalAICallPriceUSD: 0.05,
		CurrentPeriodStart:       now,
		CurrentPeriodEnd:         periodEnd,
		CancelAtPeriodEnd:        false,
		CreatedAt:                now,
		UpdatedAt:                now,
	}

	// Log audit event
	logAuditEvent(r, req.OrganizationID, "billing.subscription_create", "subscription", subscriptionID, "Subscription created")

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(subscription)
}

// GetSubscription retrieves a subscription
func GetSubscription(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	subscriptionID := vars["subscription_id"]

	// TODO: Query database
	subscription := Subscription{
		SubscriptionID: subscriptionID,
		CreatedAt:      time.Now(),
		UpdatedAt:      time.Now(),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(subscription)
}

// UpdateSubscription updates a subscription
func UpdateSubscription(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	subscriptionID := vars["subscription_id"]

	var req struct {
		PlanName      *string `json:"plan_name,omitempty"`
		PlanInterval  *string `json:"plan_interval,omitempty"`
		StripePriceID *string `json:"stripe_price_id,omitempty"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// TODO: Update in Stripe and database
	// Log audit event
	logAuditEvent(r, "", "billing.subscription_update", "subscription", subscriptionID, "Subscription updated")

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"subscription_id": subscriptionID,
		"updated":         true,
		"timestamp":       time.Now(),
	})
}

// CancelSubscription cancels a subscription
func CancelSubscription(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	subscriptionID := vars["subscription_id"]

	var req struct {
		CancelAtPeriodEnd bool `json:"cancel_at_period_end"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// TODO: Cancel in Stripe and update database
	// Log audit event
	logAuditEvent(r, "", "billing.subscription_cancel", "subscription", subscriptionID, "Subscription cancelled")

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"subscription_id":    subscriptionID,
		"cancelled":          true,
		"cancel_at_period_end": req.CancelAtPeriodEnd,
		"timestamp":          time.Now(),
	})
}

// GetInvoices retrieves invoices for an organization
func GetInvoices(w http.ResponseWriter, r *http.Request) {
	orgID := r.URL.Query().Get("organization_id")
	status := r.URL.Query().Get("status")

	// TODO: Query database
	invoices := []Invoice{}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"invoices": invoices,
		"total":    len(invoices),
		"filters": map[string]string{
			"organization_id": orgID,
			"status":          status,
		},
	})
}

// GetInvoice retrieves a specific invoice
func GetInvoice(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	invoiceID := vars["invoice_id"]

	// TODO: Query database
	invoice := Invoice{
		InvoiceID: invoiceID,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(invoice)
}

// RecordUsage records a usage event for billing
func RecordUsage(w http.ResponseWriter, r *http.Request) {
	var req struct {
		OrganizationID     string  `json:"organization_id"`
		SubscriptionID     *string `json:"subscription_id,omitempty"`
		UsageType          string  `json:"usage_type"`
		Quantity           int     `json:"quantity"`
		UnitPriceUSD       float64 `json:"unit_price_usd"`
		ResourceID         *string `json:"resource_id,omitempty"`
		BillingPeriodStart string  `json:"billing_period_start"`
		BillingPeriodEnd   string  `json:"billing_period_end"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	recordID := uuid.New().String()
	totalCost := float64(req.Quantity) * req.UnitPriceUSD

	// TODO: Insert into database
	record := UsageRecord{
		RecordID:           recordID,
		OrganizationID:     req.OrganizationID,
		SubscriptionID:     req.SubscriptionID,
		UsageType:          req.UsageType,
		Quantity:           req.Quantity,
		UnitPriceUSD:       req.UnitPriceUSD,
		TotalCostUSD:       totalCost,
		ResourceID:         req.ResourceID,
		BillingPeriodStart: req.BillingPeriodStart,
		BillingPeriodEnd:   req.BillingPeriodEnd,
		Billed:             false,
		RecordedAt:         time.Now(),
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(record)
}

// GetUsageRecords retrieves usage records
func GetUsageRecords(w http.ResponseWriter, r *http.Request) {
	orgID := r.URL.Query().Get("organization_id")
	usageType := r.URL.Query().Get("usage_type")
	startDate := r.URL.Query().Get("start_date")
	endDate := r.URL.Query().Get("end_date")

	// TODO: Query database
	records := []UsageRecord{}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"records": records,
		"total":   len(records),
		"filters": map[string]string{
			"organization_id": orgID,
			"usage_type":      usageType,
			"start_date":      startDate,
			"end_date":        endDate,
		},
	})
}

// GetUsageSummary retrieves usage summary and costs
func GetUsageSummary(w http.ResponseWriter, r *http.Request) {
	orgID := r.URL.Query().Get("organization_id")
	period := r.URL.Query().Get("period")

	// TODO: Calculate summary from database
	summary := map[string]interface{}{
		"organization_id": orgID,
		"period":          period,
		"total_cost_usd":  0.0,
		"by_type": map[string]interface{}{
			"call_minutes": map[string]interface{}{
				"quantity": 0,
				"cost_usd": 0.0,
			},
			"ai_calls": map[string]interface{}{
				"quantity": 0,
				"cost_usd": 0.0,
			},
			"storage_gb": map[string]interface{}{
				"quantity": 0,
				"cost_usd": 0.0,
			},
		},
		"next_invoice_estimate_usd": 0.0,
		"current_period_start":      time.Now().Format("2006-01-02"),
		"current_period_end":        time.Now().AddDate(0, 1, 0).Format("2006-01-02"),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(summary)
}
