-- AuraLink Database Schema - Phase 6: AuraID & Mesh Network
-- Migration: 006_phase6_auraid_mesh_schema
-- Description: Universal identity layer, mesh network, federation, and trust system
-- Author: AuraLink Engineering
-- Date: 2025-10-16

-- ============================================================================
-- AURA_ID_REGISTRY TABLE
-- Universal identity registry for cross-app communication
-- ============================================================================
CREATE TABLE IF NOT EXISTS aura_id_registry (
    registry_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- AuraID (@username.aura) - primary identity
    aura_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Verification
    is_verified BOOLEAN DEFAULT FALSE,
    verification_method VARCHAR(50),
    verified_at TIMESTAMPTZ,
    
    -- Privacy controls
    privacy_level VARCHAR(20) DEFAULT 'public',
    allow_discovery BOOLEAN DEFAULT TRUE,
    allow_cross_app_calls BOOLEAN DEFAULT TRUE,
    block_unknown_callers BOOLEAN DEFAULT FALSE,
    
    -- Federation settings
    federated_domains TEXT[],
    federation_enabled BOOLEAN DEFAULT TRUE,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    suspended BOOLEAN DEFAULT FALSE,
    suspension_reason TEXT,
    
    -- Metadata
    public_metadata JSONB DEFAULT '{}',
    private_metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    
    CONSTRAINT aura_id_registry_privacy_check CHECK (privacy_level IN ('public', 'friends', 'private')),
    CONSTRAINT aura_id_registry_format CHECK (aura_id ~ '^@[a-zA-Z0-9_-]+\.aura$')
);

CREATE INDEX idx_aura_id_registry_user_id ON aura_id_registry(user_id);
CREATE INDEX idx_aura_id_registry_aura_id ON aura_id_registry(aura_id);
CREATE INDEX idx_aura_id_registry_verification ON aura_id_registry(is_verified);
CREATE INDEX idx_aura_id_registry_active ON aura_id_registry(is_active, suspended);

ALTER TABLE aura_id_registry ENABLE ROW LEVEL SECURITY;

CREATE POLICY aura_id_registry_select_public ON aura_id_registry
    FOR SELECT
    USING (privacy_level = 'public' OR user_id = current_setting('app.current_user_id')::UUID);

CREATE POLICY aura_id_registry_update_own ON aura_id_registry
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- ============================================================================
-- CROSS_APP_CONNECTIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS cross_app_connections (
    connection_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    aura_id VARCHAR(100) NOT NULL,
    
    app_id VARCHAR(100) NOT NULL,
    app_name VARCHAR(255) NOT NULL,
    app_domain VARCHAR(255) NOT NULL,
    
    sdk_version VARCHAR(50),
    platform VARCHAR(50),
    device_info JSONB DEFAULT '{}',
    
    is_active BOOLEAN DEFAULT TRUE,
    last_connection_at TIMESTAMPTZ DEFAULT NOW(),
    
    permissions JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (aura_id) REFERENCES aura_id_registry(aura_id) ON DELETE CASCADE
);

CREATE INDEX idx_cross_app_connections_aura_id ON cross_app_connections(aura_id);
CREATE INDEX idx_cross_app_connections_app_id ON cross_app_connections(app_id);

-- ============================================================================
-- MESH_NODES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS mesh_nodes (
    node_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    aura_id VARCHAR(100) NOT NULL,
    
    node_address VARCHAR(255) NOT NULL,
    node_type VARCHAR(50) DEFAULT 'peer',
    
    max_connections INT DEFAULT 50,
    current_connections INT DEFAULT 0,
    bandwidth_capacity_mbps INT DEFAULT 100,
    current_bandwidth_usage_mbps INT DEFAULT 0,
    
    region VARCHAR(100),
    country_code VARCHAR(2),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    avg_latency_ms DECIMAL(10, 2) DEFAULT 0,
    packet_loss_rate DECIMAL(5, 4) DEFAULT 0,
    uptime_percentage DECIMAL(5, 2) DEFAULT 100.0,
    
    reputation_score DECIMAL(5, 2) DEFAULT 50.0,
    trust_level VARCHAR(20) DEFAULT 'new',
    
    supports_video BOOLEAN DEFAULT TRUE,
    supports_audio BOOLEAN DEFAULT TRUE,
    supports_screen_share BOOLEAN DEFAULT TRUE,
    supports_aic_protocol BOOLEAN DEFAULT FALSE,
    
    is_online BOOLEAN DEFAULT FALSE,
    is_accepting_connections BOOLEAN DEFAULT TRUE,
    last_heartbeat_at TIMESTAMPTZ,
    
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (aura_id) REFERENCES aura_id_registry(aura_id) ON DELETE CASCADE,
    CONSTRAINT mesh_nodes_node_type_check CHECK (node_type IN ('peer', 'relay', 'edge', 'super_node')),
    CONSTRAINT mesh_nodes_trust_level_check CHECK (trust_level IN ('new', 'trusted', 'verified', 'suspicious', 'banned')),
    CONSTRAINT mesh_nodes_reputation_check CHECK (reputation_score >= 0 AND reputation_score <= 100)
);

CREATE INDEX idx_mesh_nodes_aura_id ON mesh_nodes(aura_id);
CREATE INDEX idx_mesh_nodes_node_type ON mesh_nodes(node_type);
CREATE INDEX idx_mesh_nodes_online ON mesh_nodes(is_online);
CREATE INDEX idx_mesh_nodes_trust ON mesh_nodes(trust_level, reputation_score DESC);
CREATE INDEX idx_mesh_nodes_region ON mesh_nodes(region, country_code);
CREATE INDEX idx_mesh_nodes_performance ON mesh_nodes(avg_latency_ms ASC, packet_loss_rate ASC);

-- ============================================================================
-- MESH_ROUTES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS mesh_routes (
    route_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    source_node_id UUID NOT NULL REFERENCES mesh_nodes(node_id) ON DELETE CASCADE,
    destination_node_id UUID NOT NULL REFERENCES mesh_nodes(node_id) ON DELETE CASCADE,
    
    path_nodes UUID[] NOT NULL,
    path_length INT NOT NULL,
    
    ai_score DECIMAL(5, 2),
    predicted_latency_ms INT,
    predicted_bandwidth_mbps INT,
    optimization_factors JSONB DEFAULT '{}',
    
    actual_latency_ms INT,
    actual_bandwidth_mbps INT,
    packet_loss_rate DECIMAL(5, 4),
    jitter_ms INT,
    
    is_active BOOLEAN DEFAULT TRUE,
    is_optimal BOOLEAN DEFAULT FALSE,
    fallback_route_id UUID,
    
    usage_count INT DEFAULT 0,
    success_rate DECIMAL(5, 2) DEFAULT 100.0,
    last_used_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    
    CONSTRAINT mesh_routes_different_nodes CHECK (source_node_id != destination_node_id)
);

CREATE INDEX idx_mesh_routes_source ON mesh_routes(source_node_id);
CREATE INDEX idx_mesh_routes_destination ON mesh_routes(destination_node_id);
CREATE INDEX idx_mesh_routes_optimal ON mesh_routes(is_optimal, is_active);
CREATE INDEX idx_mesh_routes_ai_score ON mesh_routes(ai_score DESC);

-- ============================================================================
-- FEDERATION_SERVERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS federation_servers (
    server_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    server_domain VARCHAR(255) UNIQUE NOT NULL,
    server_name VARCHAR(255) NOT NULL,
    server_type VARCHAR(50) DEFAULT 'matrix',
    
    federation_url TEXT NOT NULL,
    api_endpoint TEXT,
    
    signing_key TEXT NOT NULL,
    verification_key TEXT,
    
    trust_level VARCHAR(20) DEFAULT 'pending',
    is_whitelisted BOOLEAN DEFAULT FALSE,
    is_blacklisted BOOLEAN DEFAULT FALSE,
    
    supports_video_calls BOOLEAN DEFAULT TRUE,
    supports_messaging BOOLEAN DEFAULT TRUE,
    supports_aic_protocol BOOLEAN DEFAULT FALSE,
    max_federation_users INT DEFAULT 10000,
    
    avg_response_time_ms INT,
    success_rate DECIMAL(5, 2) DEFAULT 100.0,
    uptime_percentage DECIMAL(5, 2) DEFAULT 100.0,
    
    is_online BOOLEAN DEFAULT FALSE,
    last_health_check_at TIMESTAMPTZ,
    
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_federation_at TIMESTAMPTZ,
    
    CONSTRAINT federation_servers_trust_check CHECK (trust_level IN ('pending', 'trusted', 'verified', 'blocked'))
);

CREATE INDEX idx_federation_servers_domain ON federation_servers(server_domain);
CREATE INDEX idx_federation_servers_trust ON federation_servers(trust_level);
CREATE INDEX idx_federation_servers_online ON federation_servers(is_online);

-- ============================================================================
-- FEDERATED_CALLS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS federated_calls (
    federated_call_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id VARCHAR(50),
    
    caller_aura_id VARCHAR(100) NOT NULL,
    callee_aura_id VARCHAR(100) NOT NULL,
    
    caller_server_id UUID REFERENCES federation_servers(server_id),
    callee_server_id UUID REFERENCES federation_servers(server_id),
    
    bridge_node_id UUID REFERENCES mesh_nodes(node_id),
    routing_path UUID[],
    
    media_type VARCHAR(50) DEFAULT 'audio_video',
    
    avg_latency_ms INT,
    bandwidth_used_mbps DECIMAL(10, 2),
    quality_score DECIMAL(5, 2),
    
    aic_enabled BOOLEAN DEFAULT FALSE,
    compression_ratio DECIMAL(5, 2),
    
    call_status VARCHAR(50) DEFAULT 'initiated',
    
    initiated_at TIMESTAMPTZ DEFAULT NOW(),
    connected_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_seconds INT,
    
    metadata JSONB DEFAULT '{}',
    
    FOREIGN KEY (caller_aura_id) REFERENCES aura_id_registry(aura_id),
    FOREIGN KEY (callee_aura_id) REFERENCES aura_id_registry(aura_id),
    CONSTRAINT federated_calls_status_check CHECK (call_status IN ('initiated', 'ringing', 'connected', 'ended', 'failed'))
);

CREATE INDEX idx_federated_calls_caller ON federated_calls(caller_aura_id);
CREATE INDEX idx_federated_calls_callee ON federated_calls(callee_aura_id);
CREATE INDEX idx_federated_calls_status ON federated_calls(call_status);

-- ============================================================================
-- NODE_REPUTATION_EVENTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS node_reputation_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    node_id UUID NOT NULL REFERENCES mesh_nodes(node_id) ON DELETE CASCADE,
    
    event_type VARCHAR(50) NOT NULL,
    event_severity VARCHAR(20) DEFAULT 'info',
    
    reputation_change DECIMAL(5, 2) DEFAULT 0,
    previous_score DECIMAL(5, 2),
    new_score DECIMAL(5, 2),
    
    related_call_id VARCHAR(50),
    related_route_id UUID REFERENCES mesh_routes(route_id) ON DELETE SET NULL,
    
    description TEXT,
    evidence JSONB DEFAULT '{}',
    
    reviewed BOOLEAN DEFAULT FALSE,
    reviewer_id UUID REFERENCES users(user_id),
    review_notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT node_reputation_events_severity_check CHECK (event_severity IN ('info', 'warning', 'critical'))
);

CREATE INDEX idx_node_reputation_events_node ON node_reputation_events(node_id);
CREATE INDEX idx_node_reputation_events_type ON node_reputation_events(event_type);
CREATE INDEX idx_node_reputation_events_severity ON node_reputation_events(event_severity);

-- ============================================================================
-- ABUSE_REPORTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS abuse_reports (
    report_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    reporter_aura_id VARCHAR(100) NOT NULL,
    reported_aura_id VARCHAR(100),
    reported_node_id UUID REFERENCES mesh_nodes(node_id),
    
    report_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'medium',
    
    description TEXT NOT NULL,
    evidence JSONB DEFAULT '{}',
    
    related_call_id VARCHAR(50),
    related_federated_call_id UUID REFERENCES federated_calls(federated_call_id),
    
    status VARCHAR(50) DEFAULT 'pending',
    resolution TEXT,
    
    actions_taken JSONB DEFAULT '[]',
    
    assigned_to UUID REFERENCES users(user_id),
    reviewed_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (reporter_aura_id) REFERENCES aura_id_registry(aura_id),
    FOREIGN KEY (reported_aura_id) REFERENCES aura_id_registry(aura_id),
    CONSTRAINT abuse_reports_type_check CHECK (report_type IN ('spam', 'harassment', 'malicious_node', 'security_threat', 'other')),
    CONSTRAINT abuse_reports_severity_check CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT abuse_reports_status_check CHECK (status IN ('pending', 'investigating', 'resolved', 'dismissed'))
);

CREATE INDEX idx_abuse_reports_reporter ON abuse_reports(reporter_aura_id);
CREATE INDEX idx_abuse_reports_reported_aura ON abuse_reports(reported_aura_id);
CREATE INDEX idx_abuse_reports_status ON abuse_reports(status);

-- ============================================================================
-- NOTIFICATION_PREFERENCES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS notification_preferences (
    preference_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    aura_id VARCHAR(100) UNIQUE NOT NULL,
    
    preferred_apps JSONB DEFAULT '[]',
    
    enable_smart_routing BOOLEAN DEFAULT TRUE,
    route_work_calls_to_app VARCHAR(100),
    route_personal_calls_to_app VARCHAR(100),
    
    dnd_enabled BOOLEAN DEFAULT FALSE,
    dnd_start_time TIME,
    dnd_end_time TIME,
    dnd_days_of_week INT[],
    
    enable_push_notifications BOOLEAN DEFAULT TRUE,
    enable_sms_notifications BOOLEAN DEFAULT FALSE,
    enable_email_notifications BOOLEAN DEFAULT TRUE,
    
    ring_all_apps BOOLEAN DEFAULT FALSE,
    ring_timeout_seconds INT DEFAULT 30,
    
    enable_call_screening BOOLEAN DEFAULT FALSE,
    screen_unknown_callers BOOLEAN DEFAULT FALSE,
    
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (aura_id) REFERENCES aura_id_registry(aura_id) ON DELETE CASCADE
);

CREATE INDEX idx_notification_preferences_aura_id ON notification_preferences(aura_id);

-- ============================================================================
-- FEDERATION_AUDIT_LOG TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS federation_audit_log (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50) NOT NULL,
    
    actor_aura_id VARCHAR(100),
    actor_server_id UUID REFERENCES federation_servers(server_id),
    actor_node_id UUID REFERENCES mesh_nodes(node_id),
    
    target_aura_id VARCHAR(100),
    target_server_id UUID REFERENCES federation_servers(server_id),
    target_node_id UUID REFERENCES mesh_nodes(node_id),
    
    description TEXT,
    event_data JSONB DEFAULT '{}',
    
    result VARCHAR(50) DEFAULT 'success',
    error_message TEXT,
    
    ip_address INET,
    user_agent TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT federation_audit_log_result_check CHECK (result IN ('success', 'failure', 'pending'))
);

CREATE INDEX idx_federation_audit_log_type ON federation_audit_log(event_type);
CREATE INDEX idx_federation_audit_log_category ON federation_audit_log(event_category);
CREATE INDEX idx_federation_audit_log_created ON federation_audit_log(created_at DESC);

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Update node reputation
CREATE OR REPLACE FUNCTION update_node_reputation(
    p_node_id UUID,
    p_event_type VARCHAR,
    p_reputation_change DECIMAL,
    p_description TEXT DEFAULT NULL
) RETURNS void AS $$
DECLARE
    v_current_score DECIMAL;
    v_new_score DECIMAL;
    v_new_trust_level VARCHAR;
BEGIN
    SELECT reputation_score INTO v_current_score FROM mesh_nodes WHERE node_id = p_node_id;
    v_new_score := GREATEST(0, LEAST(100, v_current_score + p_reputation_change));
    
    IF v_new_score >= 90 THEN v_new_trust_level := 'verified';
    ELSIF v_new_score >= 70 THEN v_new_trust_level := 'trusted';
    ELSIF v_new_score >= 30 THEN v_new_trust_level := 'new';
    ELSIF v_new_score >= 10 THEN v_new_trust_level := 'suspicious';
    ELSE v_new_trust_level := 'banned';
    END IF;
    
    UPDATE mesh_nodes SET reputation_score = v_new_score, trust_level = v_new_trust_level, updated_at = NOW() WHERE node_id = p_node_id;
    INSERT INTO node_reputation_events (node_id, event_type, reputation_change, previous_score, new_score, description)
    VALUES (p_node_id, p_event_type, p_reputation_change, v_current_score, v_new_score, p_description);
END;
$$ LANGUAGE plpgsql;

-- Find optimal route
CREATE OR REPLACE FUNCTION find_optimal_route(
    p_source_node_id UUID,
    p_destination_node_id UUID
) RETURNS TABLE (route_id UUID, path_nodes UUID[], predicted_latency_ms INT, ai_score DECIMAL) AS $$
BEGIN
    RETURN QUERY
    SELECT mr.route_id, mr.path_nodes, mr.predicted_latency_ms, mr.ai_score
    FROM mesh_routes mr
    WHERE mr.source_node_id = p_source_node_id AND mr.destination_node_id = p_destination_node_id
      AND mr.is_active = TRUE AND mr.expires_at > NOW()
    ORDER BY mr.is_optimal DESC, mr.ai_score DESC, mr.predicted_latency_ms ASC LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Check AuraID availability
CREATE OR REPLACE FUNCTION is_aura_id_available(p_aura_id VARCHAR) RETURNS BOOLEAN AS $$
BEGIN
    RETURN NOT EXISTS (SELECT 1 FROM aura_id_registry WHERE aura_id = p_aura_id);
END;
$$ LANGUAGE plpgsql;

-- Resolve AuraID to user
CREATE OR REPLACE FUNCTION resolve_aura_id(p_aura_id VARCHAR)
RETURNS TABLE (user_id UUID, display_name VARCHAR, is_verified BOOLEAN, privacy_level VARCHAR, is_online BOOLEAN) AS $$
BEGIN
    RETURN QUERY
    SELECT u.user_id, u.display_name, air.is_verified, air.privacy_level,
           EXISTS(SELECT 1 FROM mesh_nodes mn WHERE mn.aura_id = p_aura_id AND mn.is_online = TRUE) as is_online
    FROM aura_id_registry air
    JOIN users u ON air.user_id = u.user_id
    WHERE air.aura_id = p_aura_id AND air.is_active = TRUE AND air.suspended = FALSE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_aura_id_registry_updated_at BEFORE UPDATE ON aura_id_registry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_mesh_nodes_updated_at BEFORE UPDATE ON mesh_nodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_federation_servers_updated_at BEFORE UPDATE ON federation_servers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Migration complete
COMMENT ON SCHEMA public IS 'Phase 6: AuraID & Mesh Network - Complete';
