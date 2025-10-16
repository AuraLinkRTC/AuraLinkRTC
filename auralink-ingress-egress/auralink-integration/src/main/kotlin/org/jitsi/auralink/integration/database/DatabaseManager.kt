package org.jitsi.auralink.integration.database

import com.zaxxer.hikari.HikariConfig
import com.zaxxer.hikari.HikariDataSource
import org.jitsi.auralink.integration.config.AuraLinkConfig
import org.slf4j.LoggerFactory
import java.sql.Connection
import java.sql.SQLException
import javax.sql.DataSource

/**
 * Database connection manager for AuraLink Ingress-Egress Service
 * Provides PostgreSQL connectivity with connection pooling using HikariCP
 */
class DatabaseManager(private val config: AuraLinkConfig) {
    
    private val logger = LoggerFactory.getLogger(DatabaseManager::class.java)
    private var dataSource: HikariDataSource? = null
    
    /**
     * Initialize database connection pool
     */
    fun initialize() {
        try {
            logger.info("Initializing database connection pool")
            
            val hikariConfig = HikariConfig().apply {
                jdbcUrl = config.database.url
                username = config.database.username
                password = config.database.password
                
                // Connection pool settings
                maximumPoolSize = config.database.pool.size
                maxLifetime = config.database.pool.maxLifetime.toLong()
                connectionTimeout = config.database.pool.connectionTimeout.toLong()
                idleTimeout = config.database.pool.idleTimeout.toLong()
                leakDetectionThreshold = config.database.pool.leakDetectionThreshold.toLong()
                
                // Schema
                schema = config.database.schema
                
                // Connection test query
                connectionTestQuery = "SELECT 1"
                
                // Pool name
                poolName = "AuraLink-Ingress-Egress-Pool"
                
                // Additional settings
                isAutoCommit = true
                isReadOnly = false
                
                // Driver class
                driverClassName = "org.postgresql.Driver"
                
                // Prepared statement cache
                addDataSourceProperty("cachePrepStmts", "true")
                addDataSourceProperty("prepStmtCacheSize", "250")
                addDataSourceProperty("prepStmtCacheSqlLimit", "2048")
            }
            
            dataSource = HikariDataSource(hikariConfig)
            
            // Test connection
            testConnection()
            
            // Run migrations if enabled
            if (config.database.autoMigrate) {
                runMigrations()
            }
            
            logger.info("Database connection pool initialized successfully")
        } catch (e: Exception) {
            logger.error("Failed to initialize database connection pool", e)
            throw DatabaseInitializationException("Database initialization failed", e)
        }
    }
    
    /**
     * Get a connection from the pool
     */
    fun getConnection(): Connection {
        return dataSource?.connection 
            ?: throw IllegalStateException("Database not initialized")
    }
    
    /**
     * Test database connectivity
     */
    private fun testConnection() {
        try {
            getConnection().use { conn ->
                conn.createStatement().use { stmt ->
                    val rs = stmt.executeQuery("SELECT 1")
                    if (rs.next()) {
                        logger.info("Database connection test successful")
                    }
                }
            }
        } catch (e: SQLException) {
            logger.error("Database connection test failed", e)
            throw DatabaseConnectionException("Failed to connect to database", e)
        }
    }
    
    /**
     * Run database migrations
     */
    private fun runMigrations() {
        logger.info("Running database migrations")
        try {
            getConnection().use { conn ->
                // Create schema if not exists
                conn.createStatement().use { stmt ->
                    stmt.execute("CREATE SCHEMA IF NOT EXISTS ${config.database.schema}")
                }
                
                // Create migrations tracking table
                conn.createStatement().use { stmt ->
                    stmt.execute("""
                        CREATE TABLE IF NOT EXISTS ${config.database.schema}.schema_migrations (
                            version VARCHAR(255) PRIMARY KEY,
                            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """.trimIndent())
                }
                
                // Create bridge registration table
                executeMigration(conn, "001_create_bridge_table", """
                    CREATE TABLE IF NOT EXISTS ${config.database.schema}.bridges (
                        bridge_id VARCHAR(255) PRIMARY KEY,
                        region VARCHAR(50) NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        capacity INT DEFAULT 0,
                        current_load INT DEFAULT 0,
                        last_heartbeat TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """.trimIndent())
                
                // Create conference tracking table
                executeMigration(conn, "002_create_conference_table", """
                    CREATE TABLE IF NOT EXISTS ${config.database.schema}.conferences (
                        conference_id VARCHAR(255) PRIMARY KEY,
                        bridge_id VARCHAR(255) REFERENCES ${config.database.schema}.bridges(bridge_id),
                        room_name VARCHAR(255) NOT NULL,
                        participant_count INT DEFAULT 0,
                        status VARCHAR(20) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        ended_at TIMESTAMP
                    )
                """.trimIndent())
                
                // Create participant tracking table
                executeMigration(conn, "003_create_participant_table", """
                    CREATE TABLE IF NOT EXISTS ${config.database.schema}.participants (
                        participant_id VARCHAR(255) PRIMARY KEY,
                        conference_id VARCHAR(255) REFERENCES ${config.database.schema}.conferences(conference_id),
                        aura_id VARCHAR(255),
                        display_name VARCHAR(255),
                        join_source VARCHAR(50),
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        left_at TIMESTAMP
                    )
                """.trimIndent())
                
                // Create external bridge sessions table
                executeMigration(conn, "004_create_external_sessions_table", """
                    CREATE TABLE IF NOT EXISTS ${config.database.schema}.external_sessions (
                        session_id VARCHAR(255) PRIMARY KEY,
                        session_type VARCHAR(50) NOT NULL,
                        conference_id VARCHAR(255) REFERENCES ${config.database.schema}.conferences(conference_id),
                        external_id VARCHAR(255),
                        status VARCHAR(20) NOT NULL,
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        ended_at TIMESTAMP
                    )
                """.trimIndent())
                
                // Create indexes
                executeMigration(conn, "005_create_indexes", """
                    CREATE INDEX IF NOT EXISTS idx_bridges_status ON ${config.database.schema}.bridges(status);
                    CREATE INDEX IF NOT EXISTS idx_conferences_bridge ON ${config.database.schema}.conferences(bridge_id);
                    CREATE INDEX IF NOT EXISTS idx_conferences_status ON ${config.database.schema}.conferences(status);
                    CREATE INDEX IF NOT EXISTS idx_participants_conference ON ${config.database.schema}.participants(conference_id);
                    CREATE INDEX IF NOT EXISTS idx_participants_aura_id ON ${config.database.schema}.participants(aura_id);
                    CREATE INDEX IF NOT EXISTS idx_external_sessions_conference ON ${config.database.schema}.external_sessions(conference_id);
                    CREATE INDEX IF NOT EXISTS idx_external_sessions_type ON ${config.database.schema}.external_sessions(session_type);
                """.trimIndent())
                
                logger.info("Database migrations completed successfully")
            }
        } catch (e: SQLException) {
            logger.error("Database migration failed", e)
            throw DatabaseMigrationException("Migration failed", e)
        }
    }
    
    /**
     * Execute a single migration
     */
    private fun executeMigration(conn: Connection, version: String, sql: String) {
        // Check if migration already applied
        val checkStmt = conn.prepareStatement(
            "SELECT version FROM ${config.database.schema}.schema_migrations WHERE version = ?"
        )
        checkStmt.setString(1, version)
        val rs = checkStmt.executeQuery()
        
        if (rs.next()) {
            logger.debug("Migration $version already applied, skipping")
            return
        }
        
        // Execute migration
        logger.info("Applying migration: $version")
        conn.createStatement().use { stmt ->
            stmt.execute(sql)
        }
        
        // Record migration
        val insertStmt = conn.prepareStatement(
            "INSERT INTO ${config.database.schema}.schema_migrations (version) VALUES (?)"
        )
        insertStmt.setString(1, version)
        insertStmt.executeUpdate()
        
        logger.info("Migration $version applied successfully")
    }
    
    /**
     * Check database health
     */
    fun checkHealth(): Boolean {
        return try {
            getConnection().use { conn ->
                conn.createStatement().use { stmt ->
                    val rs = stmt.executeQuery("SELECT 1")
                    rs.next()
                }
            }
            true
        } catch (e: Exception) {
            logger.error("Database health check failed", e)
            false
        }
    }
    
    /**
     * Get current pool statistics
     */
    fun getPoolStats(): Map<String, Any> {
        val ds = dataSource ?: return emptyMap()
        
        return mapOf(
            "active_connections" to ds.hikariPoolMXBean.activeConnections,
            "idle_connections" to ds.hikariPoolMXBean.idleConnections,
            "total_connections" to ds.hikariPoolMXBean.totalConnections,
            "threads_awaiting_connection" to ds.hikariPoolMXBean.threadsAwaitingConnection
        )
    }
    
    /**
     * Shutdown database connection pool
     */
    fun shutdown() {
        logger.info("Shutting down database connection pool")
        dataSource?.close()
        dataSource = null
        logger.info("Database connection pool closed")
    }
}

/**
 * Database initialization exception
 */
class DatabaseInitializationException(message: String, cause: Throwable? = null) : 
    Exception(message, cause)

/**
 * Database connection exception
 */
class DatabaseConnectionException(message: String, cause: Throwable? = null) : 
    Exception(message, cause)

/**
 * Database migration exception
 */
class DatabaseMigrationException(message: String, cause: Throwable? = null) : 
    Exception(message, cause)
