-- Migration 008: Cross-App Communication and Trust System Tables
-- Description: Creates tables for cross-app calling, notifications, trust scores, and federation
-- Author: AuraLink Team
-- Date: 2025-10-16

-- ==============================================================================
-- CROSS-APP COMMUNICATION TABLES
-- ==============================================================================

-- Extended call metadata with cross-app context
CREATE TABLE IF NOT EXISTS cross_app_calls (
    cross_call_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    caller_aura_id VARCHAR(255) NOT NULL,
    callee_aura_id VARCHAR(255) NOT NULL,
    caller_app VARCHAR(255),
    callee_app VARCHAR(255),
    route_id UUID,
    livekit_room_id VARCHAR(255),
    call_type VARCHAR(50) CHECK (call_type IN ('audio', 'video', 'audio_video', 'screen_share')),
    status VARCHAR(50) NOT NULL DEFAULT 'ringing' CHECK (status IN ('ringing', 'answered', 'completed', 'missed', 'declined', 'failed')),
    start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    answer_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    duration INT GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (end_time - answer_time))::INT) STORED,
    quality_metrics JSONB DEFAULT '{}',
    avg_latency_ms INT,
    packet_loss NUMERIC(5,4),
    jitter_ms INT,
    mos_score NUMERIC(3,2),
    bandwidth_used_mbps NUMERIC(10,2),
    compression_ratio NUMERIC(5,4),
    aic_enabled BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    CONSTRAINT fk_caller_aura FOREIGN KEY (caller_aura_id) REFERENCES aura_id_registry(aura_id) ON DELETE CASCADE,
    CONSTRAINT fk_callee_aura FOREIGN KEY (callee_aura_id) REFERENCES aura_id_registry(aura_id) ON DELETE CASCADE,
    CONSTRAINT fk_route_id FOREIGN KEY (route_id) REFERENCES mesh_routes(route_id) ON DELETE SET NULL
);

-- Indexes for call queries
CREATE INDEX IF NOT EXISTS idx_cross_app_calls_caller ON cross_app_calls(caller_aura_id, start_time DESC);
CREATE INDEX IF NOT EXISTS idx_cross_app_calls_callee ON cross_app_calls(callee_aura_id, start_time DESC);
CREATE INDEX IF NOT EXISTS idx_cross_app_calls_status ON cross_app_calls(status) WHERE status IN ('ringing', 'answered');
CREATE INDEX IF NOT EXISTS idx_cross_app_calls_apps ON cross_app_calls(caller_app, callee_app);
CREATE INDEX IF NOT EXISTS idx_cross_app_calls_quality ON cross_app_calls(mos_score DESC) WHERE status = 'completed';

-- Unified notification hub with AI recommendations
CREATE TABLE IF NOT EXISTS notification_queue (
    notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_aura_id VARCHAR(255) NOT NULL,
    notification_type VARCHAR(50) NOT NULL CHECK (notification_type IN ('call_invite', 'call_missed', 'call_ended', 'verification', 'system')),
    payload JSONB NOT NULL,
    cross_call_id UUID,
    recommended_app VARCHAR(255),
    delivered_to_app VARCHAR(255),
    priority VARCHAR(20) DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    status VARCHAR(20) NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'sent', 'delivered', 'opened', 'acted', 'failed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    opened_at TIMESTAMP WITH TIME ZONE,
    acted_at TIMESTAMP WITH TIME ZONE,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '24 hours',
    CONSTRAINT fk_recipient_aura FOREIGN KEY (recipient_aura_id) REFERENCES aura_id_registry(aura_id) ON DELETE CASCADE,
    CONSTRAINT fk_cross_call FOREIGN KEY (cross_call_id) REFERENCES cross_app_calls(cross_call_id) ON DELETE SET NULL
);

-- Indexes for notification delivery
CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notification_queue(recipient_aura_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notification_queue(status) WHERE status IN ('queued', 'sent');
CREATE INDEX IF NOT EXISTS idx_notifications_expires ON notification_queue(expires_at) WHERE status NOT IN ('acted', 'failed');
CREATE INDEX IF NOT EXISTS idx_notifications_cross_call ON notification_queue(cross_call_id) WHERE cross_call_id IS NOT NULL;

-- ==============================================================================
-- TRUST AND REPUTATION TABLES
-- ==============================================================================

-- Multi-entity reputation system
CREATE TABLE IF NOT EXISTS trust_scores (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN ('aura_id', 'mesh_node', 'organization')),
    entity_id VARCHAR(255) NOT NULL,
    base_score NUMERIC(5,2) DEFAULT 50.0,
    verification_bonus NUMERIC(5,2) DEFAULT 0.0,
    behavior_score NUMERIC(5,2) DEFAULT 0.0,
    penalty_score NUMERIC(5,2) DEFAULT 0.0,
    total_score NUMERIC(5,2) GENERATED ALWAYS AS (
        GREATEST(0, LEAST(100, base_score + verification_bonus + behavior_score + penalty_score))
    ) STORED,
    trust_level VARCHAR(20) GENERATED ALWAYS AS (
        CASE 
            WHEN GREATEST(0, LEAST(100, base_score + verification_bonus + behavior_score + penalty_score)) >= 80 THEN 'verified'
            WHEN GREATEST(0, LEAST(100, base_score + verification_bonus + behavior_score + penalty_score)) >= 60 THEN 'trusted'
            WHEN GREATEST(0, LEAST(100, base_score + verification_bonus + behavior_score + penalty_score)) >= 40 THEN 'established'
            WHEN GREATEST(0, LEAST(100, base_score + verification_bonus + behavior_score + penalty_score)) >= 20 THEN 'new'
            ELSE 'caution'
        END
    ) STORED,
    calculation_metadata JSONB DEFAULT '{}',
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_entity_trust UNIQUE (entity_type, entity_id)
);

-- Indexes for trust lookups
CREATE INDEX IF NOT EXISTS idx_trust_scores_entity ON trust_scores(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_trust_scores_total ON trust_scores(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_trust_scores_level ON trust_scores(trust_level);

-- ==============================================================================
-- FEDERATION AND COMPLIANCE TABLES
-- ==============================================================================

-- Organization-level federation rules
CREATE TABLE IF NOT EXISTS federation_policy (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    policy_name VARCHAR(255) NOT NULL,
    allowed_domains TEXT[] DEFAULT '{}',
    blocked_domains TEXT[] DEFAULT '{}',
    min_trust_score NUMERIC(5,2) DEFAULT 50.0,
    require_mutual_tls BOOLEAN DEFAULT true,
    require_e2e_encryption BOOLEAN DEFAULT true,
    max_federation_rate_per_min INT DEFAULT 100,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_org_policy UNIQUE (organization_id, policy_name)
);

-- Indexes for federation checks
CREATE INDEX IF NOT EXISTS idx_federation_policy_org ON federation_policy(organization_id) WHERE is_active = true;

-- Multi-device mesh node association
CREATE TABLE IF NOT EXISTS device_registry (
    device_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aura_id VARCHAR(255) NOT NULL,
    device_identifier VARCHAR(255) UNIQUE NOT NULL,
    device_type VARCHAR(50) NOT NULL,
    device_name VARCHAR(255),
    platform VARCHAR(50),
    os_version VARCHAR(50),
    app_version VARCHAR(50),
    push_token TEXT,
    push_provider VARCHAR(50) CHECK (push_provider IN ('fcm', 'apns', 'web_push')),
    is_active BOOLEAN DEFAULT true,
    last_active_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    registered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_aura_id FOREIGN KEY (aura_id) REFERENCES aura_id_registry(aura_id) ON DELETE CASCADE
);

-- Indexes for device lookups
CREATE INDEX IF NOT EXISTS idx_device_registry_aura ON device_registry(aura_id) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_device_registry_push ON device_registry(push_provider, push_token) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_device_registry_last_active ON device_registry(last_active_at DESC) WHERE is_active = true;

-- AI routing training data for ML model feedback loop
CREATE TABLE IF NOT EXISTS ai_routing_training_data (
    training_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    route_id UUID NOT NULL,
    cross_call_id UUID,
    predicted_quality NUMERIC(5,2),
    actual_quality NUMERIC(5,2),
    prediction_error NUMERIC(5,2) GENERATED ALWAYS AS (ABS(predicted_quality - actual_quality)) STORED,
    features JSONB NOT NULL,
    model_version VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_route_id FOREIGN KEY (route_id) REFERENCES mesh_routes(route_id) ON DELETE CASCADE,
    CONSTRAINT fk_cross_call FOREIGN KEY (cross_call_id) REFERENCES cross_app_calls(cross_call_id) ON DELETE SET NULL
);

-- Indexes for training data
CREATE INDEX IF NOT EXISTS idx_training_data_route ON ai_routing_training_data(route_id);
CREATE INDEX IF NOT EXISTS idx_training_data_error ON ai_routing_training_data(prediction_error DESC);
CREATE INDEX IF NOT EXISTS idx_training_data_model ON ai_routing_training_data(model_version, created_at DESC);

-- ==============================================================================
-- TRIGGERS
-- ==============================================================================

-- Auto-update trust scores when call completes
CREATE OR REPLACE FUNCTION update_trust_on_call_completion()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
        -- Update caller trust (small bonus for completing calls)
        UPDATE trust_scores 
        SET behavior_score = behavior_score + 0.1,
            last_updated = NOW()
        WHERE entity_type = 'aura_id' AND entity_id = NEW.caller_aura_id;
        
        -- Update callee trust
        UPDATE trust_scores 
        SET behavior_score = behavior_score + 0.1,
            last_updated = NOW()
        WHERE entity_type = 'aura_id' AND entity_id = NEW.callee_aura_id;
        
        -- If route used relay nodes, update their trust
        IF NEW.route_id IS NOT NULL THEN
            -- This will be expanded to update relay node trust scores
            NULL;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_trust_on_call_end
    AFTER UPDATE ON cross_app_calls
    FOR EACH ROW
    WHEN (NEW.status = 'completed')
    EXECUTE FUNCTION update_trust_on_call_completion();

-- Auto-update federation policy timestamp
CREATE TRIGGER update_federation_policy_updated_at
    BEFORE UPDATE ON federation_policy
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==============================================================================
-- COMMENTS
-- ==============================================================================

COMMENT ON TABLE cross_app_calls IS 'Extended call metadata with app context and quality metrics';
COMMENT ON TABLE notification_queue IS 'Unified notification hub with AI-driven app recommendations';
COMMENT ON TABLE trust_scores IS 'Multi-entity reputation system for AuraIDs, nodes, and organizations';
COMMENT ON TABLE federation_policy IS 'Organization-level federation security rules';
COMMENT ON TABLE device_registry IS 'Multi-device association for push notifications and mesh nodes';
COMMENT ON TABLE ai_routing_training_data IS 'ML model feedback loop for routing optimization';

-- ==============================================================================
-- GRANTS
-- ==============================================================================

-- Grant access to authenticated users
GRANT SELECT ON cross_app_calls TO authenticated;
GRANT SELECT, INSERT, UPDATE ON notification_queue TO authenticated;
GRANT SELECT ON trust_scores TO authenticated;
GRANT SELECT ON federation_policy TO authenticated;
GRANT SELECT, INSERT, UPDATE ON device_registry TO authenticated;
GRANT SELECT ON ai_routing_training_data TO authenticated;

-- Grant full access to service role
GRANT ALL ON cross_app_calls TO service_role;
GRANT ALL ON notification_queue TO service_role;
GRANT ALL ON trust_scores TO service_role;
GRANT ALL ON federation_policy TO service_role;
GRANT ALL ON device_registry TO service_role;
GRANT ALL ON ai_routing_training_data TO service_role;

-- Migration complete
