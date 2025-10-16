-- AuraLink Database Schema - Communication Service
-- Migration: 008_communication_service_schema
-- Description: Matrix integration, verification, trust calculation, and cross-app calling
-- Author: AuraLink Engineering
-- Date: 2025-10-16

-- ============================================================================
-- AURA_ID_VERIFICATIONS TABLE
-- Tracks verification attempts and methods for AuraIDs
-- ============================================================================
CREATE TABLE IF NOT EXISTS aura_id_verifications (
    verification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    aura_id VARCHAR(100) NOT NULL,
    
    verification_method VARCHAR(50) NOT NULL,
    verification_value VARCHAR(255),
    verification_code VARCHAR(20),
    
    status VARCHAR(50) DEFAULT 'pending',
    attempts INT DEFAULT 0,
    max_attempts INT DEFAULT 3,
    
    verified_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    
    trust_score_bonus DECIMAL(5, 2) DEFAULT 0,
    
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (aura_id) REFERENCES aura_id_registry(aura_id) ON DELETE CASCADE,
    CONSTRAINT verification_method_check CHECK (verification_method IN ('email', 'phone', 'document', 'social', 'biometric')),
    CONSTRAINT verification_status_check CHECK (status IN ('pending', 'verified', 'failed', 'expired'))
);

CREATE INDEX idx_aura_id_verifications_aura_id ON aura_id_verifications(aura_id);
CREATE INDEX idx_aura_id_verifications_status ON aura_id_verifications(status);
CREATE INDEX idx_aura_id_verifications_method ON aura_id_verifications(verification_method);

-- ============================================================================
-- MATRIX_USER_MAPPINGS TABLE
-- Maps AuraIDs to Matrix user IDs
-- ============================================================================
CREATE TABLE IF NOT EXISTS matrix_user_mappings (
    mapping_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    aura_id VARCHAR(100) UNIQUE NOT NULL,
    
    matrix_user_id VARCHAR(255) UNIQUE NOT NULL,
    matrix_access_token TEXT,
    matrix_device_id VARCHAR(255),
    
    homeserver_url TEXT NOT NULL,
    homeserver_domain VARCHAR(255) NOT NULL,
    
    is_active BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (aura_id) REFERENCES aura_id_registry(aura_id) ON DELETE CASCADE
);

CREATE INDEX idx_matrix_user_mappings_aura_id ON matrix_user_mappings(aura_id);
CREATE INDEX idx_matrix_user_mappings_matrix_user_id ON matrix_user_mappings(matrix_user_id);

-- ============================================================================
-- CROSS_APP_CALLS TABLE
-- Extended tracking for cross-application calls
-- ============================================================================
CREATE TABLE IF NOT EXISTS cross_app_calls (
    cross_call_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id VARCHAR(50),
    
    caller_aura_id VARCHAR(100) NOT NULL,
    callee_aura_id VARCHAR(100) NOT NULL,
    
    caller_app_id VARCHAR(100) NOT NULL,
    caller_app_name VARCHAR(255),
    callee_app_id VARCHAR(100) NOT NULL,
    callee_app_name VARCHAR(255),
    
    matrix_room_id VARCHAR(255),
    livekit_room_id VARCHAR(255),
    
    route_id UUID REFERENCES mesh_routes(route_id),
    signaling_type VARCHAR(50) DEFAULT 'matrix',
    
    call_type VARCHAR(50) DEFAULT 'audio_video',
    encryption_enabled BOOLEAN DEFAULT TRUE,
    
    media_quality_avg DECIMAL(5, 2),
    latency_avg_ms INT,
    packet_loss_avg DECIMAL(5, 4),
    
    aic_compression_enabled BOOLEAN DEFAULT FALSE,
    compression_ratio DECIMAL(5, 2),
    bandwidth_saved_mb DECIMAL(10, 2),
    
    call_status VARCHAR(50) DEFAULT 'initiated',
    end_reason VARCHAR(100),
    
    initiated_at TIMESTAMPTZ DEFAULT NOW(),
    ringing_at TIMESTAMPTZ,
    answered_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_seconds INT,
    
    metadata JSONB DEFAULT '{}',
    
    FOREIGN KEY (caller_aura_id) REFERENCES aura_id_registry(aura_id),
    FOREIGN KEY (callee_aura_id) REFERENCES aura_id_registry(aura_id),
    CONSTRAINT cross_app_calls_status_check CHECK (call_status IN ('initiated', 'ringing', 'answered', 'ended', 'failed', 'missed', 'rejected')),
    CONSTRAINT cross_app_calls_signaling_check CHECK (signaling_type IN ('matrix', 'sip', 'webrtc_direct'))
);

CREATE INDEX idx_cross_app_calls_caller ON cross_app_calls(caller_aura_id);
CREATE INDEX idx_cross_app_calls_callee ON cross_app_calls(callee_aura_id);
CREATE INDEX idx_cross_app_calls_status ON cross_app_calls(call_status);
CREATE INDEX idx_cross_app_calls_apps ON cross_app_calls(caller_app_id, callee_app_id);
CREATE INDEX idx_cross_app_calls_initiated ON cross_app_calls(initiated_at DESC);

-- ============================================================================
-- TRUST_SCORES TABLE
-- Centralized trust and reputation scoring
-- ============================================================================
CREATE TABLE IF NOT EXISTS trust_scores (
    trust_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    
    base_score DECIMAL(5, 2) DEFAULT 50.0,
    verification_bonus DECIMAL(5, 2) DEFAULT 0,
    behavior_score DECIMAL(5, 2) DEFAULT 0,
    penalty_score DECIMAL(5, 2) DEFAULT 0,
    
    total_score DECIMAL(5, 2) DEFAULT 50.0,
    trust_level VARCHAR(20) DEFAULT 'new',
    
    metrics JSONB DEFAULT '{}',
    
    successful_relays INT DEFAULT 0,
    failed_relays INT DEFAULT 0,
    abuse_reports_count INT DEFAULT 0,
    
    uptime_percentage DECIMAL(5, 2) DEFAULT 100.0,
    last_active_at TIMESTAMPTZ,
    
    last_calculated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT trust_entity_type_check CHECK (entity_type IN ('aura_id', 'mesh_node', 'federation_server')),
    CONSTRAINT trust_level_check CHECK (trust_level IN ('new', 'established', 'trusted', 'verified', 'caution', 'suspended')),
    CONSTRAINT trust_score_range CHECK (total_score >= 0 AND total_score <= 100)
);

CREATE UNIQUE INDEX idx_trust_scores_entity ON trust_scores(entity_type, entity_id);
CREATE INDEX idx_trust_scores_level ON trust_scores(trust_level);
CREATE INDEX idx_trust_scores_total ON trust_scores(total_score DESC);

-- ============================================================================
-- NOTIFICATION_QUEUE TABLE
-- Queue for unified notifications across apps
-- ============================================================================
CREATE TABLE IF NOT EXISTS notification_queue (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    aura_id VARCHAR(100) NOT NULL,
    
    notification_type VARCHAR(50) NOT NULL,
    priority VARCHAR(20) DEFAULT 'normal',
    
    caller_aura_id VARCHAR(100),
    caller_display_name VARCHAR(255),
    caller_app_name VARCHAR(255),
    
    cross_call_id UUID REFERENCES cross_app_calls(cross_call_id),
    
    target_apps JSONB DEFAULT '[]',
    recommended_app VARCHAR(100),
    ai_recommendation_score DECIMAL(5, 2),
    
    status VARCHAR(50) DEFAULT 'pending',
    delivered_to_app VARCHAR(100),
    
    expires_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (aura_id) REFERENCES aura_id_registry(aura_id) ON DELETE CASCADE,
    FOREIGN KEY (caller_aura_id) REFERENCES aura_id_registry(aura_id),
    CONSTRAINT notification_type_check CHECK (notification_type IN ('incoming_call', 'missed_call', 'message', 'system')),
    CONSTRAINT notification_priority_check CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    CONSTRAINT notification_status_check CHECK (status IN ('pending', 'delivered', 'expired', 'cancelled'))
);

CREATE INDEX idx_notification_queue_aura_id ON notification_queue(aura_id);
CREATE INDEX idx_notification_queue_status ON notification_queue(status);
CREATE INDEX idx_notification_queue_priority ON notification_queue(priority DESC, created_at ASC);

-- ============================================================================
-- MESH_ROUTE_CACHE TABLE
-- Caches AI-optimized routes for performance
-- ============================================================================
CREATE TABLE IF NOT EXISTS mesh_route_cache (
    cache_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    source_aura_id VARCHAR(100) NOT NULL,
    dest_aura_id VARCHAR(100) NOT NULL,
    
    route_id UUID REFERENCES mesh_routes(route_id),
    route_quality_score DECIMAL(5, 2),
    
    predicted_latency_ms INT,
    predicted_bandwidth_mbps INT,
    
    cache_hit_count INT DEFAULT 0,
    last_used_at TIMESTAMPTZ DEFAULT NOW(),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    
    FOREIGN KEY (source_aura_id) REFERENCES aura_id_registry(aura_id),
    FOREIGN KEY (dest_aura_id) REFERENCES aura_id_registry(aura_id)
);

CREATE UNIQUE INDEX idx_mesh_route_cache_pair ON mesh_route_cache(source_aura_id, dest_aura_id);
CREATE INDEX idx_mesh_route_cache_expires ON mesh_route_cache(expires_at);

-- ============================================================================
-- AI_ROUTING_TRAINING_DATA TABLE
-- Collects data for ML model training
-- ============================================================================
CREATE TABLE IF NOT EXISTS ai_routing_training_data (
    training_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    route_id UUID REFERENCES mesh_routes(route_id),
    cross_call_id UUID REFERENCES cross_app_calls(cross_call_id),
    
    features JSONB NOT NULL,
    
    predicted_quality DECIMAL(5, 2),
    actual_quality DECIMAL(5, 2),
    
    prediction_error DECIMAL(5, 2),
    
    call_successful BOOLEAN,
    model_version VARCHAR(50),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT features_required CHECK (jsonb_typeof(features) = 'object')
);

CREATE INDEX idx_ai_routing_training_route ON ai_routing_training_data(route_id);
CREATE INDEX idx_ai_routing_training_call ON ai_routing_training_data(cross_call_id);
CREATE INDEX idx_ai_routing_training_created ON ai_routing_training_data(created_at DESC);

-- ============================================================================
-- FEDERATION_POLICY TABLE
-- Defines federation rules per organization
-- ============================================================================
CREATE TABLE IF NOT EXISTS federation_policy (
    policy_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(organization_id) ON DELETE CASCADE,
    
    policy_name VARCHAR(255) NOT NULL,
    policy_type VARCHAR(50) DEFAULT 'whitelist',
    
    is_active BOOLEAN DEFAULT TRUE,
    
    allowed_domains TEXT[],
    blocked_domains TEXT[],
    
    require_mutual_trust BOOLEAN DEFAULT TRUE,
    minimum_trust_score DECIMAL(5, 2) DEFAULT 50.0,
    
    allow_anonymous_federation BOOLEAN DEFAULT FALSE,
    require_encryption BOOLEAN DEFAULT TRUE,
    
    max_federation_bandwidth_mbps INT DEFAULT 1000,
    rate_limit_per_server INT DEFAULT 100,
    
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT federation_policy_type_check CHECK (policy_type IN ('whitelist', 'blacklist', 'open'))
);

CREATE INDEX idx_federation_policy_org ON federation_policy(organization_id);
CREATE INDEX idx_federation_policy_active ON federation_policy(is_active);

-- ============================================================================
-- DEVICE_REGISTRY TABLE
-- Tracks user devices for mesh node association
-- ============================================================================
CREATE TABLE IF NOT EXISTS device_registry (
    device_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    aura_id VARCHAR(100) NOT NULL,
    
    device_name VARCHAR(255),
    device_type VARCHAR(50),
    platform VARCHAR(50),
    
    device_token VARCHAR(500),
    push_enabled BOOLEAN DEFAULT TRUE,
    
    mesh_node_id UUID REFERENCES mesh_nodes(node_id),
    
    capabilities JSONB DEFAULT '{}',
    
    is_active BOOLEAN DEFAULT TRUE,
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    FOREIGN KEY (aura_id) REFERENCES aura_id_registry(aura_id) ON DELETE CASCADE,
    CONSTRAINT device_type_check CHECK (device_type IN ('mobile', 'desktop', 'tablet', 'iot', 'web'))
);

CREATE INDEX idx_device_registry_aura_id ON device_registry(aura_id);
CREATE INDEX idx_device_registry_mesh_node ON device_registry(mesh_node_id);
CREATE INDEX idx_device_registry_active ON device_registry(is_active);

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Calculate trust score
CREATE OR REPLACE FUNCTION calculate_trust_score(
    p_entity_type VARCHAR,
    p_entity_id UUID
) RETURNS DECIMAL AS $$
DECLARE
    v_base_score DECIMAL := 50.0;
    v_verification_bonus DECIMAL := 0;
    v_behavior_score DECIMAL := 0;
    v_penalty_score DECIMAL := 0;
    v_total_score DECIMAL;
    v_trust_level VARCHAR;
BEGIN
    IF p_entity_type = 'aura_id' THEN
        SELECT 
            CASE 
                WHEN verification_method = 'document' THEN 25
                WHEN verification_method = 'phone' THEN 15
                WHEN verification_method = 'email' THEN 10
                ELSE 0
            END INTO v_verification_bonus
        FROM aura_id_registry air
        LEFT JOIN aura_id_verifications aiv ON air.aura_id = aiv.aura_id AND aiv.status = 'verified'
        WHERE air.registry_id = p_entity_id
        LIMIT 1;
        
    ELSIF p_entity_type = 'mesh_node' THEN
        SELECT 
            (uptime_percentage / 5) + 
            (CASE WHEN reputation_score > 0 THEN reputation_score / 5 ELSE 0 END)
            INTO v_behavior_score
        FROM mesh_nodes
        WHERE node_id = p_entity_id;
        
        SELECT COUNT(*) * -20 INTO v_penalty_score
        FROM abuse_reports
        WHERE reported_node_id = p_entity_id AND status != 'dismissed';
    END IF;
    
    v_total_score := GREATEST(0, LEAST(100, v_base_score + v_verification_bonus + v_behavior_score + v_penalty_score));
    
    IF v_total_score >= 80 THEN v_trust_level := 'verified';
    ELSIF v_total_score >= 60 THEN v_trust_level := 'trusted';
    ELSIF v_total_score >= 40 THEN v_trust_level := 'established';
    ELSIF v_total_score >= 20 THEN v_trust_level := 'new';
    ELSE v_trust_level := 'caution';
    END IF;
    
    INSERT INTO trust_scores (entity_type, entity_id, base_score, verification_bonus, behavior_score, penalty_score, total_score, trust_level)
    VALUES (p_entity_type, p_entity_id, v_base_score, v_verification_bonus, v_behavior_score, v_penalty_score, v_total_score, v_trust_level)
    ON CONFLICT ((entity_type, entity_id))
    DO UPDATE SET 
        base_score = v_base_score,
        verification_bonus = v_verification_bonus,
        behavior_score = v_behavior_score,
        penalty_score = v_penalty_score,
        total_score = v_total_score,
        trust_level = v_trust_level,
        last_calculated_at = NOW(),
        updated_at = NOW();
    
    RETURN v_total_score;
END;
$$ LANGUAGE plpgsql;

-- Queue notification with app recommendation
CREATE OR REPLACE FUNCTION queue_call_notification(
    p_aura_id VARCHAR,
    p_caller_aura_id VARCHAR,
    p_cross_call_id UUID
) RETURNS UUID AS $$
DECLARE
    v_notification_id UUID;
    v_recommended_app VARCHAR;
    v_ai_score DECIMAL;
BEGIN
    SELECT preferred_apps->0->>'app_id', 0.85
    INTO v_recommended_app, v_ai_score
    FROM notification_preferences
    WHERE aura_id = p_aura_id
    LIMIT 1;
    
    INSERT INTO notification_queue (
        aura_id, 
        notification_type, 
        priority, 
        caller_aura_id, 
        cross_call_id,
        recommended_app,
        ai_recommendation_score,
        expires_at
    ) VALUES (
        p_aura_id,
        'incoming_call',
        'urgent',
        p_caller_aura_id,
        p_cross_call_id,
        v_recommended_app,
        v_ai_score,
        NOW() + INTERVAL '30 seconds'
    )
    RETURNING notification_id INTO v_notification_id;
    
    RETURN v_notification_id;
END;
$$ LANGUAGE plpgsql;

-- Get cached route or create new
CREATE OR REPLACE FUNCTION get_or_create_route_cache(
    p_source_aura_id VARCHAR,
    p_dest_aura_id VARCHAR
) RETURNS UUID AS $$
DECLARE
    v_cache_id UUID;
    v_route_id UUID;
BEGIN
    SELECT cache_id, route_id
    INTO v_cache_id, v_route_id
    FROM mesh_route_cache
    WHERE source_aura_id = p_source_aura_id 
      AND dest_aura_id = p_dest_aura_id
      AND expires_at > NOW()
    LIMIT 1;
    
    IF v_cache_id IS NOT NULL THEN
        UPDATE mesh_route_cache 
        SET cache_hit_count = cache_hit_count + 1,
            last_used_at = NOW()
        WHERE cache_id = v_cache_id;
        
        RETURN v_route_id;
    ELSE
        RETURN NULL;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

CREATE TRIGGER update_aura_id_verifications_updated_at BEFORE UPDATE ON aura_id_verifications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_matrix_user_mappings_updated_at BEFORE UPDATE ON matrix_user_mappings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_trust_scores_updated_at BEFORE UPDATE ON trust_scores
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_federation_policy_updated_at BEFORE UPDATE ON federation_policy
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_device_registry_updated_at BEFORE UPDATE ON device_registry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Auto-calculate trust score on abuse report
CREATE OR REPLACE FUNCTION trigger_recalculate_trust_on_abuse() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'resolved' AND NEW.reported_node_id IS NOT NULL THEN
        PERFORM calculate_trust_score('mesh_node', NEW.reported_node_id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER recalculate_trust_on_abuse_resolution
    AFTER UPDATE ON abuse_reports
    FOR EACH ROW
    WHEN (NEW.status = 'resolved')
    EXECUTE FUNCTION trigger_recalculate_trust_on_abuse();

-- Migration complete
COMMENT ON SCHEMA public IS 'Communication Service Schema - Complete';
