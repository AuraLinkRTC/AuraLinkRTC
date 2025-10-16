-- AuraLink Database Schema - Initial Migration
-- Migration: 001_initial_schema
-- Description: Core tables for users, organizations, sessions, and API keys
-- Author: AuraLink Engineering
-- Date: 2025-10-15

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For text search

-- ============================================================================
-- USERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    
    -- AuraID: Universal identity (@username.aura)
    aura_id VARCHAR(100) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    
    -- Profile
    display_name VARCHAR(100),
    avatar_url TEXT,
    bio TEXT,
    
    -- Organization
    organization_id UUID,
    
    -- Role: user, admin, moderator, agent
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    
    -- Constraints
    CONSTRAINT users_role_check CHECK (role IN ('user', 'admin', 'moderator', 'agent')),
    CONSTRAINT users_aura_id_format CHECK (aura_id ~ '^@[a-zA-Z0-9_-]+\.aura$')
);

-- Indexes for users
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_aura_id ON users(aura_id);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_organization_id ON users(organization_id);
CREATE INDEX idx_users_created_at ON users(created_at DESC);
CREATE INDEX idx_users_search ON users USING gin(username gin_trgm_ops, display_name gin_trgm_ops);

-- RLS for users
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY users_select_own ON users
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id')::UUID OR role = 'admin');

CREATE POLICY users_update_own ON users
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id')::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id')::UUID);

-- ============================================================================
-- ORGANIZATIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS organizations (
    organization_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    
    -- Owner
    owner_id UUID NOT NULL,
    
    -- Plan: free, pro, enterprise
    plan VARCHAR(20) NOT NULL DEFAULT 'free',
    
    -- Limits
    max_users INT DEFAULT 10,
    max_calls_per_month INT DEFAULT 1000,
    max_storage_gb INT DEFAULT 10,
    
    -- Billing
    billing_email VARCHAR(255),
    stripe_customer_id VARCHAR(100),
    
    -- Settings
    settings JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT organizations_plan_check CHECK (plan IN ('free', 'pro', 'enterprise')),
    CONSTRAINT organizations_slug_format CHECK (slug ~ '^[a-z0-9-]+$')
);

-- Indexes for organizations
CREATE INDEX idx_organizations_slug ON organizations(slug);
CREATE INDEX idx_organizations_owner_id ON organizations(owner_id);
CREATE INDEX idx_organizations_plan ON organizations(plan);

-- RLS for organizations
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;

CREATE POLICY organizations_select_member ON organizations
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM users 
            WHERE user_id = current_setting('app.current_user_id')::UUID
        )
    );

-- ============================================================================
-- API KEYS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS api_keys (
    key_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    organization_id UUID,
    
    -- Key
    key_hash VARCHAR(255) NOT NULL, -- bcrypt hash of the key
    key_prefix VARCHAR(10) NOT NULL, -- First 8 chars for identification (e.g., "ak_live_")
    key_name VARCHAR(100) NOT NULL,
    
    -- Permissions
    scopes JSONB DEFAULT '["read"]', -- read, write, admin
    
    -- Rate limiting
    rate_limit_per_minute INT DEFAULT 60,
    
    -- Usage
    last_used_at TIMESTAMPTZ,
    usage_count BIGINT DEFAULT 0,
    
    -- Expiration
    expires_at TIMESTAMPTZ,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Foreign keys
    CONSTRAINT api_keys_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT api_keys_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES organizations(organization_id) ON DELETE CASCADE
);

-- Indexes for api_keys
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_organization_id ON api_keys(organization_id);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_expires_at ON api_keys(expires_at);

-- RLS for api_keys
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY api_keys_select_own ON api_keys
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- ============================================================================
-- SESSIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    
    -- Token
    refresh_token_hash VARCHAR(255) NOT NULL,
    
    -- Device info
    ip_address INET,
    user_agent TEXT,
    device_id VARCHAR(100),
    device_name VARCHAR(100),
    
    -- Location (optional)
    country_code VARCHAR(2),
    city VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Foreign keys
    CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Indexes for sessions
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_refresh_token_hash ON sessions(refresh_token_hash);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX idx_sessions_is_active ON sessions(is_active) WHERE is_active = TRUE;

-- RLS for sessions
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY sessions_select_own ON sessions
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- ============================================================================
-- Foreign Key Relationships
-- ============================================================================
ALTER TABLE users
    ADD CONSTRAINT users_organization_id_fkey 
    FOREIGN KEY (organization_id) 
    REFERENCES organizations(organization_id) 
    ON DELETE SET NULL;

ALTER TABLE organizations
    ADD CONSTRAINT organizations_owner_id_fkey 
    FOREIGN KEY (owner_id) 
    REFERENCES users(user_id) 
    ON DELETE CASCADE;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_api_keys_updated_at BEFORE UPDATE ON api_keys
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to generate AuraID from username
CREATE OR REPLACE FUNCTION generate_aura_id(username_input VARCHAR)
RETURNS VARCHAR AS $$
BEGIN
    RETURN '@' || LOWER(username_input) || '.aura';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to validate email format
CREATE OR REPLACE FUNCTION is_valid_email(email_input VARCHAR)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN email_input ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to clean expired sessions
CREATE OR REPLACE FUNCTION clean_expired_sessions()
RETURNS INT AS $$
DECLARE
    deleted_count INT;
BEGIN
    DELETE FROM sessions WHERE expires_at < NOW() OR (is_active = FALSE AND last_activity_at < NOW() - INTERVAL '30 days');
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert default admin user (password should be changed immediately)
-- Password: admin123 (bcrypt hash - CHANGE IN PRODUCTION!)
INSERT INTO users (user_id, email, aura_id, username, display_name, role, email_verified)
VALUES (
    '00000000-0000-0000-0000-000000000001'::UUID,
    'admin@auralink.com',
    '@admin.aura',
    'admin',
    'AuraLink Admin',
    'admin',
    TRUE
) ON CONFLICT (email) DO NOTHING;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE users IS 'User profiles with AuraID universal identity';
COMMENT ON TABLE organizations IS 'Multi-tenant organization management';
COMMENT ON TABLE api_keys IS 'API key management for programmatic access';
COMMENT ON TABLE sessions IS 'User session tracking for authentication';

COMMENT ON COLUMN users.aura_id IS 'Universal identity in format @username.aura';
COMMENT ON COLUMN users.role IS 'User role: user, admin, moderator, agent';
COMMENT ON COLUMN api_keys.key_hash IS 'Bcrypt hash of the API key (never store plain text)';
COMMENT ON COLUMN api_keys.scopes IS 'JSON array of permission scopes';

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
