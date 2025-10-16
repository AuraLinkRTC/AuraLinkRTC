package resilience

import (
	"context"
	"errors"
	"math/rand"
	"time"
)

var (
	// ErrMaxRetriesExceeded is returned when max retries are exceeded
	ErrMaxRetriesExceeded = errors.New("max retries exceeded")
)

// RetryConfig holds retry configuration
type RetryConfig struct {
	MaxAttempts     int           // Maximum number of attempts (including initial)
	InitialDelay    time.Duration // Initial delay before first retry
	MaxDelay        time.Duration // Maximum delay between retries
	Multiplier      float64       // Backoff multiplier
	RandomizationFactor float64   // Randomization factor (0-1)
	RetryableErrors []error       // Specific errors to retry
}

// DefaultRetryConfig returns a default retry configuration
func DefaultRetryConfig() RetryConfig {
	return RetryConfig{
		MaxAttempts:         3,
		InitialDelay:        100 * time.Millisecond,
		MaxDelay:            10 * time.Second,
		Multiplier:          2.0,
		RandomizationFactor: 0.1,
	}
}

// RetryFunc is a function that can be retried
type RetryFunc func(ctx context.Context) error

// Retry executes a function with exponential backoff retry
func Retry(ctx context.Context, config RetryConfig, fn RetryFunc) error {
	if config.MaxAttempts <= 0 {
		config.MaxAttempts = 1
	}

	var lastErr error
	delay := config.InitialDelay

	for attempt := 1; attempt <= config.MaxAttempts; attempt++ {
		// Execute the function
		err := fn(ctx)
		if err == nil {
			return nil
		}

		lastErr = err

		// Check if error is retryable
		if len(config.RetryableErrors) > 0 && !isRetryableError(err, config.RetryableErrors) {
			return err
		}

		// Don't retry if context is cancelled
		if ctx.Err() != nil {
			return ctx.Err()
		}

		// Last attempt, don't wait
		if attempt == config.MaxAttempts {
			break
		}

		// Calculate backoff delay with jitter
		backoffDelay := calculateBackoff(delay, config.MaxDelay, config.Multiplier, config.RandomizationFactor)

		// Wait for backoff or context cancellation
		select {
		case <-time.After(backoffDelay):
			delay = backoffDelay
		case <-ctx.Done():
			return ctx.Err()
		}
	}

	return lastErr
}

// RetryWithCallback executes a function with retry and calls a callback on each attempt
func RetryWithCallback(
	ctx context.Context,
	config RetryConfig,
	fn RetryFunc,
	onRetry func(attempt int, err error, delay time.Duration),
) error {
	if config.MaxAttempts <= 0 {
		config.MaxAttempts = 1
	}

	var lastErr error
	delay := config.InitialDelay

	for attempt := 1; attempt <= config.MaxAttempts; attempt++ {
		// Execute the function
		err := fn(ctx)
		if err == nil {
			return nil
		}

		lastErr = err

		// Check if error is retryable
		if len(config.RetryableErrors) > 0 && !isRetryableError(err, config.RetryableErrors) {
			return err
		}

		// Don't retry if context is cancelled
		if ctx.Err() != nil {
			return ctx.Err()
		}

		// Last attempt, don't wait
		if attempt == config.MaxAttempts {
			break
		}

		// Calculate backoff delay
		backoffDelay := calculateBackoff(delay, config.MaxDelay, config.Multiplier, config.RandomizationFactor)

		// Call retry callback
		if onRetry != nil {
			onRetry(attempt, err, backoffDelay)
		}

		// Wait for backoff or context cancellation
		select {
		case <-time.After(backoffDelay):
			delay = backoffDelay
		case <-ctx.Done():
			return ctx.Err()
		}
	}

	return lastErr
}

// calculateBackoff calculates the next backoff delay with jitter
func calculateBackoff(
	currentDelay time.Duration,
	maxDelay time.Duration,
	multiplier float64,
	randomizationFactor float64,
) time.Duration {
	// Apply multiplier
	nextDelay := time.Duration(float64(currentDelay) * multiplier)

	// Cap at max delay
	if nextDelay > maxDelay {
		nextDelay = maxDelay
	}

	// Apply jitter
	if randomizationFactor > 0 {
		delta := randomizationFactor * float64(nextDelay)
		minDelay := float64(nextDelay) - delta
		maxJitter := float64(nextDelay) + delta
		
		// Random jitter between [minDelay, maxJitter]
		nextDelay = time.Duration(minDelay + rand.Float64()*(maxJitter-minDelay))
	}

	return nextDelay
}

// isRetryableError checks if an error is in the list of retryable errors
func isRetryableError(err error, retryableErrors []error) bool {
	for _, retryableErr := range retryableErrors {
		if errors.Is(err, retryableErr) {
			return true
		}
	}
	return false
}

// ExponentialBackoff implements exponential backoff strategy
type ExponentialBackoff struct {
	InitialInterval     time.Duration
	MaxInterval         time.Duration
	Multiplier          float64
	RandomizationFactor float64
	currentInterval     time.Duration
}

// NewExponentialBackoff creates a new exponential backoff
func NewExponentialBackoff() *ExponentialBackoff {
	return &ExponentialBackoff{
		InitialInterval:     500 * time.Millisecond,
		MaxInterval:         60 * time.Second,
		Multiplier:          1.5,
		RandomizationFactor: 0.5,
		currentInterval:     500 * time.Millisecond,
	}
}

// NextBackoff returns the next backoff duration
func (eb *ExponentialBackoff) NextBackoff() time.Duration {
	// Calculate next interval
	nextInterval := time.Duration(float64(eb.currentInterval) * eb.Multiplier)
	
	// Cap at max
	if nextInterval > eb.MaxInterval {
		nextInterval = eb.MaxInterval
	}

	// Apply randomization
	delta := eb.RandomizationFactor * float64(nextInterval)
	minInterval := float64(nextInterval) - delta
	maxInterval := float64(nextInterval) + delta
	
	randomInterval := time.Duration(minInterval + rand.Float64()*(maxInterval-minInterval))
	
	eb.currentInterval = nextInterval
	return randomInterval
}

// Reset resets the backoff to initial interval
func (eb *ExponentialBackoff) Reset() {
	eb.currentInterval = eb.InitialInterval
}

// ConstantBackoff implements constant backoff strategy
type ConstantBackoff struct {
	Interval time.Duration
}

// NewConstantBackoff creates a new constant backoff
func NewConstantBackoff(interval time.Duration) *ConstantBackoff {
	return &ConstantBackoff{
		Interval: interval,
	}
}

// NextBackoff returns the constant backoff duration
func (cb *ConstantBackoff) NextBackoff() time.Duration {
	return cb.Interval
}

// Reset is a no-op for constant backoff
func (cb *ConstantBackoff) Reset() {
	// No-op
}

// LinearBackoff implements linear backoff strategy
type LinearBackoff struct {
	InitialInterval time.Duration
	MaxInterval     time.Duration
	Increment       time.Duration
	currentInterval time.Duration
}

// NewLinearBackoff creates a new linear backoff
func NewLinearBackoff(initial, max, increment time.Duration) *LinearBackoff {
	return &LinearBackoff{
		InitialInterval: initial,
		MaxInterval:     max,
		Increment:       increment,
		currentInterval: initial,
	}
}

// NextBackoff returns the next linear backoff duration
func (lb *LinearBackoff) NextBackoff() time.Duration {
	current := lb.currentInterval
	
	// Increment for next time
	next := lb.currentInterval + lb.Increment
	if next > lb.MaxInterval {
		next = lb.MaxInterval
	}
	
	lb.currentInterval = next
	return current
}

// Reset resets the backoff to initial interval
func (lb *LinearBackoff) Reset() {
	lb.currentInterval = lb.InitialInterval
}

// FibonacciBackoff implements Fibonacci backoff strategy
type FibonacciBackoff struct {
	InitialInterval time.Duration
	MaxInterval     time.Duration
	prev            time.Duration
	current         time.Duration
}

// NewFibonacciBackoff creates a new Fibonacci backoff
func NewFibonacciBackoff(initial, max time.Duration) *FibonacciBackoff {
	return &FibonacciBackoff{
		InitialInterval: initial,
		MaxInterval:     max,
		prev:            0,
		current:         initial,
	}
}

// NextBackoff returns the next Fibonacci backoff duration
func (fb *FibonacciBackoff) NextBackoff() time.Duration {
	result := fb.current
	
	// Calculate next Fibonacci number
	next := fb.prev + fb.current
	if next > fb.MaxInterval {
		next = fb.MaxInterval
	}
	
	fb.prev = fb.current
	fb.current = next
	
	return result
}

// Reset resets the backoff to initial values
func (fb *FibonacciBackoff) Reset() {
	fb.prev = 0
	fb.current = fb.InitialInterval
}

// Backoff interface for different backoff strategies
type Backoff interface {
	NextBackoff() time.Duration
	Reset()
}
