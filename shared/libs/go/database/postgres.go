package database

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

// PostgresConfig holds PostgreSQL connection configuration
type PostgresConfig struct {
	Host            string
	Port            int
	Database        string
	User            string
	Password        string
	SSLMode         string
	MaxConns        int32
	MinConns        int32
	MaxConnLifetime time.Duration
	MaxConnIdleTime time.Duration
	HealthCheckPeriod time.Duration
}

// DefaultPostgresConfig returns default PostgreSQL configuration
func DefaultPostgresConfig() PostgresConfig {
	return PostgresConfig{
		Host:              "localhost",
		Port:              5432,
		SSLMode:           "prefer",
		MaxConns:          25,
		MinConns:          5,
		MaxConnLifetime:   time.Hour,
		MaxConnIdleTime:   30 * time.Minute,
		HealthCheckPeriod: time.Minute,
	}
}

// PostgresPool wraps pgxpool.Pool with additional functionality
type PostgresPool struct {
	pool *pgxpool.Pool
	config PostgresConfig
}

// NewPostgresPool creates a new PostgreSQL connection pool
func NewPostgresPool(ctx context.Context, config PostgresConfig) (*PostgresPool, error) {
	// Build connection string
	connString := fmt.Sprintf(
		"host=%s port=%d dbname=%s user=%s password=%s sslmode=%s",
		config.Host,
		config.Port,
		config.Database,
		config.User,
		config.Password,
		config.SSLMode,
	)

	// Parse config
	poolConfig, err := pgxpool.ParseConfig(connString)
	if err != nil {
		return nil, fmt.Errorf("failed to parse pool config: %w", err)
	}

	// Configure pool settings
	poolConfig.MaxConns = config.MaxConns
	poolConfig.MinConns = config.MinConns
	poolConfig.MaxConnLifetime = config.MaxConnLifetime
	poolConfig.MaxConnIdleTime = config.MaxConnIdleTime
	poolConfig.HealthCheckPeriod = config.HealthCheckPeriod

	// Configure connection settings
	poolConfig.ConnConfig.ConnectTimeout = 10 * time.Second
	poolConfig.ConnConfig.RuntimeParams = map[string]string{
		"application_name": "auralink",
	}

	// Create pool
	pool, err := pgxpool.NewWithConfig(ctx, poolConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create connection pool: %w", err)
	}

	// Test connection
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	return &PostgresPool{
		pool:   pool,
		config: config,
	}, nil
}

// Pool returns the underlying pgxpool.Pool
func (p *PostgresPool) Pool() *pgxpool.Pool {
	return p.pool
}

// Acquire acquires a connection from the pool
func (p *PostgresPool) Acquire(ctx context.Context) (*pgxpool.Conn, error) {
	return p.pool.Acquire(ctx)
}

// Query executes a query that returns rows
func (p *PostgresPool) Query(ctx context.Context, sql string, args ...interface{}) (pgx.Rows, error) {
	return p.pool.Query(ctx, sql, args...)
}

// QueryRow executes a query that returns at most one row
func (p *PostgresPool) QueryRow(ctx context.Context, sql string, args ...interface{}) pgx.Row {
	return p.pool.QueryRow(ctx, sql, args...)
}

// Exec executes a query that doesn't return rows
func (p *PostgresPool) Exec(ctx context.Context, sql string, args ...interface{}) error {
	_, err := p.pool.Exec(ctx, sql, args...)
	return err
}

// BeginTx starts a transaction
func (p *PostgresPool) BeginTx(ctx context.Context) (pgx.Tx, error) {
	return p.pool.Begin(ctx)
}

// BeginTxWithOptions starts a transaction with options
func (p *PostgresPool) BeginTxWithOptions(ctx context.Context, txOptions pgx.TxOptions) (pgx.Tx, error) {
	return p.pool.BeginTx(ctx, txOptions)
}

// Close closes all connections in the pool
func (p *PostgresPool) Close() {
	p.pool.Close()
}

// Ping verifies a connection to the database is still alive
func (p *PostgresPool) Ping(ctx context.Context) error {
	return p.pool.Ping(ctx)
}

// Stats returns pool statistics
func (p *PostgresPool) Stats() *pgxpool.Stat {
	return p.pool.Stat()
}

// HealthCheck performs a health check on the database
func (p *PostgresPool) HealthCheck(ctx context.Context) error {
	// Ping database
	if err := p.Ping(ctx); err != nil {
		return fmt.Errorf("ping failed: %w", err)
	}

	// Check pool stats
	stats := p.Stats()
	if stats.TotalConns() == 0 {
		return fmt.Errorf("no connections in pool")
	}

	// Execute simple query
	var result int
	if err := p.QueryRow(ctx, "SELECT 1").Scan(&result); err != nil {
		return fmt.Errorf("query failed: %w", err)
	}

	return nil
}

// WithTransaction executes a function within a transaction
func (p *PostgresPool) WithTransaction(ctx context.Context, fn func(pgx.Tx) error) error {
	tx, err := p.BeginTx(ctx)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}

	defer func() {
		if err != nil {
			_ = tx.Rollback(ctx)
		}
	}()

	err = fn(tx)
	if err != nil {
		return err
	}

	if err = tx.Commit(ctx); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	return nil
}

// SetUserContext sets the current user ID in the database session for RLS
func (p *PostgresPool) SetUserContext(ctx context.Context, conn *pgxpool.Conn, userID string) error {
	_, err := conn.Exec(ctx, "SELECT set_config('app.current_user_id', $1, false)", userID)
	return err
}

// ClearUserContext clears the user context from the database session
func (p *PostgresPool) ClearUserContext(ctx context.Context, conn *pgxpool.Conn) error {
	_, err := conn.Exec(ctx, "SELECT set_config('app.current_user_id', '', false)")
	return err
}
