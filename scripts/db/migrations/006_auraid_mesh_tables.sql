-- Migration 006: AuraID and Mesh Network Tables
-- Description: Creates core tables for universal identity (AuraID) and mesh networking
-- Author: AuraLink Team
-- Date: 2025-10-16

-- ==============================================================================
-- AURAID REGISTRY TABLES
-- ==============================================================================

-- Primary AuraID registry with privacy controls
CREATE TABLE IF NOT EXISTS aura_id_registry (
    registry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aura_id VARCHAR(255) UNIQUE NOT NULL,
    user_id UUID NOT NULL,
    username VARCHAR(50) NOT NULL,
    display_name VARCHAR(255),
    privacy_level VARCHAR(20) NOT NULL DEFAULT 'public' CHECK (privacy_level IN ('public', 'friends', 'private')),
    trust_score NUMERIC(5,2) DEFAULT 50.0 CHECK (trust_score >= 0 AND trust_score <= 100),
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT valid_aura_id_format CHECK (aura_id ~ '^@[a-zA-Z0-9_]{3,20}\.aura$'),
    CONSTRAINT fk_user_id FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_aura_id_registry_user_id ON aura_id_registry(user_id);
CREATE INDEX IF NOT EXISTS idx_aura_id_registry_username ON aura_id_registry(username);
CREATE INDEX IF NOT EXISTS idx_aura_id_registry_privacy ON aura_id_registry(privacy_level) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_aura_id_registry_trust_score ON aura_id_registry(trust_score) WHERE is_active = true;

-- AuraID verification tracking (email, phone, document, social, biometric)
CREATE TABLE IF NOT EXISTS aura_id_verifications (
    verification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aura_id VARCHAR(255) NOT NULL,
    registry_id UUID NOT NULL,
    verification_method VARCHAR(50) NOT NULL CHECK (verification_method IN ('email', 'phone', 'document', 'social', 'biometric')),
    verification_code VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'verified', 'failed', 'expired')),
    attempts INT DEFAULT 0,
    max_attempts INT DEFAULT 3,
    metadata JSONB,
    initiated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    verified_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '7 days',
    CONSTRAINT fk_registry_id FOREIGN KEY (registry_id) REFERENCES aura_id_registry(registry_id) ON DELETE CASCADE,
    CONSTRAINT max_attempts_check CHECK (attempts <= max_attempts)
);

-- Indexes for verification lookups
CREATE INDEX IF NOT EXISTS idx_verifications_aura_id ON aura_id_verifications(aura_id);
CREATE INDEX IF NOT EXISTS idx_verifications_registry_id ON aura_id_verifications(registry_id);
CREATE INDEX IF NOT EXISTS idx_verifications_status ON aura_id_verifications(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_verifications_expires ON aura_id_verifications(expires_at) WHERE status = 'pending';

-- AuraID to Matrix user mapping
CREATE TABLE IF NOT EXISTS matrix_user_mappings (
    mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aura_id VARCHAR(255) UNIQUE NOT NULL,
    registry_id UUID NOT NULL,
    matrix_user_id VARCHAR(255) UNIQUE NOT NULL,
    homeserver VARCHAR(255) NOT NULL DEFAULT 'auralink.network',
    matrix_access_token TEXT,
    device_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_registry_id FOREIGN KEY (registry_id) REFERENCES aura_id_registry(registry_id) ON DELETE CASCADE
);

-- Indexes for Matrix lookups
CREATE INDEX IF NOT EXISTS idx_matrix_mappings_aura_id ON matrix_user_mappings(aura_id);
CREATE INDEX IF NOT EXISTS idx_matrix_mappings_matrix_user ON matrix_user_mappings(matrix_user_id);
CREATE INDEX IF NOT EXISTS idx_matrix_mappings_homeserver ON matrix_user_mappings(homeserver);

-- ==============================================================================
-- MESH NETWORK TABLES
-- ==============================================================================

-- Mesh network nodes (user devices that can relay calls)
CREATE TABLE IF NOT EXISTS mesh_nodes (
    node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aura_id VARCHAR(255) NOT NULL,
    device_id VARCHAR(255) NOT NULL,
    device_type VARCHAR(50) NOT NULL CHECK (device_type IN ('mobile', 'desktop', 'tablet', 'iot')),
    device_name VARCHAR(255),
    platform VARCHAR(50),
    capabilities JSONB NOT NULL DEFAULT '{}',
    trust_score NUMERIC(5,2) DEFAULT 50.0 CHECK (trust_score >= 0 AND trust_score <= 100),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'offline', 'suspended')),
    current_load NUMERIC(5,2) DEFAULT 0.0 CHECK (current_load >= 0 AND current_load <= 100),
    available_bandwidth NUMERIC(10,2) DEFAULT 0.0,
    uptime_percentage NUMERIC(5,2) DEFAULT 0.0,
    reputation_score NUMERIC(5,2) DEFAULT 0.0,
    abuse_reports_count INT DEFAULT 0,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    registered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_device_per_aura UNIQUE (aura_id, device_id),
    CONSTRAINT fk_aura_id FOREIGN KEY (aura_id) REFERENCES aura_id_registry(aura_id) ON DELETE CASCADE
);

-- Indexes for mesh node queries
CREATE INDEX IF NOT EXISTS idx_mesh_nodes_aura_id ON mesh_nodes(aura_id);
CREATE INDEX IF NOT EXISTS idx_mesh_nodes_status ON mesh_nodes(status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_mesh_nodes_trust_score ON mesh_nodes(trust_score) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_mesh_nodes_last_seen ON mesh_nodes(last_seen_at) WHERE status = 'active';

-- Mesh routing paths with AI-predicted quality scores
CREATE TABLE IF NOT EXISTS mesh_routes (
    route_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_aura_id VARCHAR(255) NOT NULL,
    dest_aura_id VARCHAR(255) NOT NULL,
    path_type VARCHAR(50) NOT NULL CHECK (path_type IN ('p2p_direct', 'single_relay', 'multi_hop', 'centralized')),
    relay_nodes JSONB DEFAULT '[]',
    predicted_latency_ms INT,
    predicted_bandwidth_mbps NUMERIC(10,2),
    quality_score NUMERIC(5,2) CHECK (quality_score >= 0 AND quality_score <= 100),
    actual_latency_ms INT,
    actual_quality_score NUMERIC(5,2),
    success_count INT DEFAULT 0,
    failure_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_used_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT fk_source_aura FOREIGN KEY (source_aura_id) REFERENCES aura_id_registry(aura_id) ON DELETE CASCADE,
    CONSTRAINT fk_dest_aura FOREIGN KEY (dest_aura_id) REFERENCES aura_id_registry(aura_id) ON DELETE CASCADE
);

-- Indexes for route lookups
CREATE INDEX IF NOT EXISTS idx_mesh_routes_source_dest ON mesh_routes(source_aura_id, dest_aura_id);
CREATE INDEX IF NOT EXISTS idx_mesh_routes_quality ON mesh_routes(quality_score DESC) WHERE quality_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_mesh_routes_last_used ON mesh_routes(last_used_at DESC);

-- Mesh route cache (Redis-backed persistent storage)
CREATE TABLE IF NOT EXISTS mesh_route_cache (
    cache_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key VARCHAR(512) UNIQUE NOT NULL,
    route_id UUID,
    route_data JSONB NOT NULL,
    hit_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '5 minutes',
    CONSTRAINT fk_route_id FOREIGN KEY (route_id) REFERENCES mesh_routes(route_id) ON DELETE SET NULL
);

-- Indexes for cache operations
CREATE INDEX IF NOT EXISTS idx_route_cache_key ON mesh_route_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_route_cache_expires ON mesh_route_cache(expires_at) WHERE expires_at > NOW();

-- ==============================================================================
-- TRIGGERS
-- ==============================================================================

-- Auto-update updated_at timestamp on aura_id_registry
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_aura_id_registry_updated_at
    BEFORE UPDATE ON aura_id_registry
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Auto-cleanup expired verifications (called by scheduled job)
CREATE OR REPLACE FUNCTION cleanup_expired_verifications_trigger()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.expires_at < NOW() AND NEW.status = 'pending' THEN
        NEW.status = 'expired';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER check_verification_expiry
    BEFORE UPDATE ON aura_id_verifications
    FOR EACH ROW
    WHEN (OLD.status = 'pending')
    EXECUTE FUNCTION cleanup_expired_verifications_trigger();

-- ==============================================================================
-- COMMENTS
-- ==============================================================================

COMMENT ON TABLE aura_id_registry IS 'Universal identity registry for AuraLink cross-app communication';
COMMENT ON TABLE aura_id_verifications IS 'Multi-method verification tracking for AuraIDs';
COMMENT ON TABLE matrix_user_mappings IS 'Mapping between AuraIDs and Matrix federation user IDs';
COMMENT ON TABLE mesh_nodes IS 'Device nodes that can participate in mesh network routing';
COMMENT ON TABLE mesh_routes IS 'AI-optimized routing paths between AuraIDs';
COMMENT ON TABLE mesh_route_cache IS 'Cache for frequently used routes (5-minute TTL)';

-- ==============================================================================
-- GRANTS (adjust based on your RLS setup)
-- ==============================================================================

-- Grant access to authenticated users
GRANT SELECT, INSERT, UPDATE ON aura_id_registry TO authenticated;
GRANT SELECT, INSERT, UPDATE ON aura_id_verifications TO authenticated;
GRANT SELECT ON matrix_user_mappings TO authenticated;
GRANT SELECT, INSERT, UPDATE ON mesh_nodes TO authenticated;
GRANT SELECT ON mesh_routes TO authenticated;
GRANT SELECT ON mesh_route_cache TO authenticated;

-- Grant full access to service role
GRANT ALL ON aura_id_registry TO service_role;
GRANT ALL ON aura_id_verifications TO service_role;
GRANT ALL ON matrix_user_mappings TO service_role;
GRANT ALL ON mesh_nodes TO service_role;
GRANT ALL ON mesh_routes TO service_role;
GRANT ALL ON mesh_route_cache TO service_role;

-- Migration complete
