package resilience

import (
	"context"
	"errors"
	"sync"
	"time"
)

// CircuitState represents the state of a circuit breaker
type CircuitState int

const (
	StateClosed CircuitState = iota
	StateHalfOpen
	StateOpen
)

var (
	// ErrCircuitOpen is returned when the circuit breaker is open
	ErrCircuitOpen = errors.New("circuit breaker is open")
	// ErrTooManyRequests is returned when too many requests are made in half-open state
	ErrTooManyRequests = errors.New("too many requests")
)

// CircuitBreaker implements the circuit breaker pattern
type CircuitBreaker struct {
	name           string
	maxFailures    uint32
	timeout        time.Duration
	maxRequests    uint32
	interval       time.Duration
	
	mu              sync.RWMutex
	state           CircuitState
	failures        uint32
	successes       uint32
	requests        uint32
	lastFailureTime time.Time
	lastStateChange time.Time
}

// CircuitBreakerConfig holds circuit breaker configuration
type CircuitBreakerConfig struct {
	Name        string        // Name of the circuit breaker
	MaxFailures uint32        // Maximum failures before opening
	Timeout     time.Duration // Timeout before half-open
	MaxRequests uint32        // Maximum requests in half-open state
	Interval    time.Duration // Interval to reset failure count in closed state
}

// NewCircuitBreaker creates a new circuit breaker
func NewCircuitBreaker(config CircuitBreakerConfig) *CircuitBreaker {
	if config.MaxFailures == 0 {
		config.MaxFailures = 5
	}
	if config.Timeout == 0 {
		config.Timeout = 60 * time.Second
	}
	if config.MaxRequests == 0 {
		config.MaxRequests = 1
	}
	if config.Interval == 0 {
		config.Interval = 60 * time.Second
	}

	return &CircuitBreaker{
		name:            config.Name,
		maxFailures:     config.MaxFailures,
		timeout:         config.Timeout,
		maxRequests:     config.MaxRequests,
		interval:        config.Interval,
		state:           StateClosed,
		lastStateChange: time.Now(),
	}
}

// Execute runs the given function with circuit breaker protection
func (cb *CircuitBreaker) Execute(ctx context.Context, fn func() error) error {
	if err := cb.beforeRequest(); err != nil {
		return err
	}

	// Execute the function
	err := fn()
	
	cb.afterRequest(err)
	return err
}

// beforeRequest checks if the request can be made
func (cb *CircuitBreaker) beforeRequest() error {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	now := time.Now()

	switch cb.state {
	case StateOpen:
		// Check if timeout has passed
		if now.Sub(cb.lastStateChange) > cb.timeout {
			cb.setState(StateHalfOpen, now)
			cb.requests = 0
			cb.successes = 0
			cb.failures = 0
			return nil
		}
		return ErrCircuitOpen

	case StateHalfOpen:
		// Allow limited requests in half-open state
		if cb.requests >= cb.maxRequests {
			return ErrTooManyRequests
		}
		cb.requests++
		return nil

	case StateClosed:
		// Reset failure count if interval has passed
		if now.Sub(cb.lastStateChange) > cb.interval {
			cb.failures = 0
			cb.lastStateChange = now
		}
		return nil

	default:
		return nil
	}
}

// afterRequest records the result of the request
func (cb *CircuitBreaker) afterRequest(err error) {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	now := time.Now()

	if err != nil {
		cb.onFailure(now)
	} else {
		cb.onSuccess(now)
	}
}

// onSuccess handles a successful request
func (cb *CircuitBreaker) onSuccess(now time.Time) {
	switch cb.state {
	case StateHalfOpen:
		cb.successes++
		// If enough successes, close the circuit
		if cb.successes >= cb.maxRequests {
			cb.setState(StateClosed, now)
			cb.failures = 0
			cb.successes = 0
			cb.requests = 0
		}

	case StateClosed:
		// Nothing to do in closed state on success
	}
}

// onFailure handles a failed request
func (cb *CircuitBreaker) onFailure(now time.Time) {
	cb.failures++
	cb.lastFailureTime = now

	switch cb.state {
	case StateHalfOpen:
		// Any failure in half-open state opens the circuit
		cb.setState(StateOpen, now)
		cb.requests = 0
		cb.successes = 0

	case StateClosed:
		// Open circuit if max failures reached
		if cb.failures >= cb.maxFailures {
			cb.setState(StateOpen, now)
		}
	}
}

// setState changes the circuit breaker state
func (cb *CircuitBreaker) setState(state CircuitState, now time.Time) {
	cb.state = state
	cb.lastStateChange = now
}

// State returns the current state of the circuit breaker
func (cb *CircuitBreaker) State() CircuitState {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.state
}

// Name returns the name of the circuit breaker
func (cb *CircuitBreaker) Name() string {
	return cb.name
}

// Stats returns statistics about the circuit breaker
func (cb *CircuitBreaker) Stats() CircuitBreakerStats {
	cb.mu.RLock()
	defer cb.mu.RUnlock()

	return CircuitBreakerStats{
		Name:            cb.name,
		State:           cb.state,
		Failures:        cb.failures,
		Successes:       cb.successes,
		Requests:        cb.requests,
		LastFailureTime: cb.lastFailureTime,
		LastStateChange: cb.lastStateChange,
	}
}

// CircuitBreakerStats holds circuit breaker statistics
type CircuitBreakerStats struct {
	Name            string
	State           CircuitState
	Failures        uint32
	Successes       uint32
	Requests        uint32
	LastFailureTime time.Time
	LastStateChange time.Time
}

// String returns a string representation of the circuit state
func (s CircuitState) String() string {
	switch s {
	case StateClosed:
		return "closed"
	case StateOpen:
		return "open"
	case StateHalfOpen:
		return "half-open"
	default:
		return "unknown"
	}
}
