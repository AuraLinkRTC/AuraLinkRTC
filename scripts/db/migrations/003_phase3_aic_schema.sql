-- ================================================================
-- Phase 3: AuraLink AIC Protocol Database Schema
-- ================================================================
-- Purpose: Support AI-driven compression, metrics, and configuration
-- Dependencies: 002_phase2_schema.sql
-- Author: AuraLinkRTC Engineering
-- Date: 2025-10-15
-- ================================================================

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- ================================================================
-- AIC Configuration Table
-- ================================================================
-- Stores per-user/organization AIC Protocol settings

CREATE TABLE IF NOT EXISTS aic_configs (
    config_id VARCHAR(50) PRIMARY KEY DEFAULT ('aic_' || uuid_generate_v4()::TEXT),
    user_id VARCHAR(255) NOT NULL,
    organization_id VARCHAR(255),
    
    -- AIC Protocol Settings
    enabled BOOLEAN DEFAULT FALSE,
    mode VARCHAR(20) DEFAULT 'adaptive' CHECK (mode IN ('adaptive', 'aggressive', 'conservative', 'off')),
    target_compression_ratio DECIMAL(4,2) DEFAULT 0.80, -- 80% reduction
    max_latency_ms INTEGER DEFAULT 20, -- Max AI inference latency
    
    -- Model Configuration
    model_type VARCHAR(50) DEFAULT 'encodec' CHECK (model_type IN ('encodec', 'lyra', 'maxine', 'hybrid')),
    model_version VARCHAR(20) DEFAULT 'v1.0',
    use_gpu BOOLEAN DEFAULT TRUE,
    
    -- Quality Settings
    min_quality_score DECIMAL(3,2) DEFAULT 0.85, -- Minimum acceptable quality (0-1)
    fallback_on_quality_loss BOOLEAN DEFAULT TRUE,
    
    -- Feature Flags
    enable_predictive_compression BOOLEAN DEFAULT TRUE,
    enable_perceptual_optimization BOOLEAN DEFAULT TRUE,
    enable_bandwidth_prediction BOOLEAN DEFAULT TRUE,
    
    -- Privacy & Compliance
    opt_out BOOLEAN DEFAULT FALSE,
    data_retention_hours INTEGER DEFAULT 0, -- 0 = no retention
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_user_aic_config UNIQUE(user_id)
);

-- Indexes for AIC configs
CREATE INDEX idx_aic_configs_user ON aic_configs(user_id);
CREATE INDEX idx_aic_configs_org ON aic_configs(organization_id);
CREATE INDEX idx_aic_configs_enabled ON aic_configs(enabled) WHERE enabled = TRUE;

-- ================================================================
-- AIC Compression Metrics Table
-- ================================================================
-- Real-time metrics for AIC Protocol performance

CREATE TABLE IF NOT EXISTS aic_metrics (
    metric_id VARCHAR(50) PRIMARY KEY DEFAULT ('metric_' || uuid_generate_v4()::TEXT),
    call_id VARCHAR(50) REFERENCES calls(call_id) ON DELETE CASCADE,
    participant_id VARCHAR(50) REFERENCES call_participants(participant_id) ON DELETE CASCADE,
    
    -- Compression Performance
    original_bandwidth_kbps INTEGER NOT NULL,
    compressed_bandwidth_kbps INTEGER NOT NULL,
    compression_ratio DECIMAL(5,4) NOT NULL, -- 0.8000 = 80% reduction
    bandwidth_savings_percent DECIMAL(5,2) GENERATED ALWAYS AS ((1 - (compressed_bandwidth_kbps::DECIMAL / NULLIF(original_bandwidth_kbps, 0))) * 100) STORED,
    
    -- AI Inference Metrics
    inference_latency_ms DECIMAL(6,2), -- AI processing time
    model_used VARCHAR(50),
    model_confidence DECIMAL(4,3), -- 0-1 confidence score
    
    -- Quality Metrics
    quality_score DECIMAL(3,2), -- 0-1 quality after compression
    psnr_db DECIMAL(5,2), -- Peak Signal-to-Noise Ratio
    ssim DECIMAL(4,3), -- Structural Similarity Index
    
    -- Network Conditions
    available_bandwidth_kbps INTEGER,
    rtt_ms INTEGER, -- Round-trip time
    packet_loss_percent DECIMAL(5,2),
    
    -- Frame Details
    frame_type VARCHAR(20), -- video, audio, screen
    resolution VARCHAR(20), -- 720p, 1080p, 4K
    fps INTEGER,
    codec VARCHAR(20), -- H264, VP9, etc.
    
    -- Fallback Information
    fallback_triggered BOOLEAN DEFAULT FALSE,
    fallback_reason TEXT,
    
    -- Timestamps
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CHECK (compression_ratio >= 0 AND compression_ratio <= 1),
    CHECK (quality_score >= 0 AND quality_score <= 1),
    CHECK (original_bandwidth_kbps > 0)
);

-- Indexes for AIC metrics (optimized for time-series queries)
CREATE INDEX idx_aic_metrics_call ON aic_metrics(call_id, timestamp DESC);
CREATE INDEX idx_aic_metrics_participant ON aic_metrics(participant_id, timestamp DESC);
CREATE INDEX idx_aic_metrics_timestamp ON aic_metrics(timestamp DESC);
CREATE INDEX idx_aic_metrics_fallback ON aic_metrics(fallback_triggered) WHERE fallback_triggered = TRUE;

-- Partitioning by time for scalability (optional, comment out if not needed)
-- CREATE TABLE aic_metrics_2025_10 PARTITION OF aic_metrics
--     FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');

-- ================================================================
-- AIC Session State Table
-- ================================================================
-- Tracks AIC state per call session

CREATE TABLE IF NOT EXISTS aic_sessions (
    session_id VARCHAR(50) PRIMARY KEY DEFAULT ('sess_' || uuid_generate_v4()::TEXT),
    call_id VARCHAR(50) NOT NULL REFERENCES calls(call_id) ON DELETE CASCADE,
    participant_id VARCHAR(50) NOT NULL REFERENCES call_participants(participant_id) ON DELETE CASCADE,
    
    -- Session State
    aic_enabled BOOLEAN DEFAULT TRUE,
    current_mode VARCHAR(20) DEFAULT 'adaptive',
    
    -- Real-time Stats
    total_frames_processed BIGINT DEFAULT 0,
    frames_compressed BIGINT DEFAULT 0,
    frames_fallback BIGINT DEFAULT 0,
    
    -- Cumulative Metrics
    avg_compression_ratio DECIMAL(5,4),
    avg_inference_latency_ms DECIMAL(6,2),
    avg_quality_score DECIMAL(3,2),
    total_bandwidth_saved_mb DECIMAL(12,2),
    
    -- Performance Tracking
    peak_compression_ratio DECIMAL(5,4),
    min_quality_score DECIMAL(3,2),
    max_inference_latency_ms DECIMAL(6,2),
    
    -- Adaptation History
    mode_changes INTEGER DEFAULT 0,
    fallback_count INTEGER DEFAULT 0,
    last_mode_change_at TIMESTAMPTZ,
    
    -- Session Lifecycle
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    
    CONSTRAINT unique_aic_session UNIQUE(call_id, participant_id)
);

-- Indexes for AIC sessions
CREATE INDEX idx_aic_sessions_call ON aic_sessions(call_id);
CREATE INDEX idx_aic_sessions_participant ON aic_sessions(participant_id);
CREATE INDEX idx_aic_sessions_active ON aic_sessions(ended_at) WHERE ended_at IS NULL;

-- ================================================================
-- AIC Model Performance Table
-- ================================================================
-- Tracks performance of different AI models

CREATE TABLE IF NOT EXISTS aic_model_performance (
    perf_id VARCHAR(50) PRIMARY KEY DEFAULT ('perf_' || uuid_generate_v4()::TEXT),
    model_type VARCHAR(50) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    
    -- Performance Metrics
    avg_inference_ms DECIMAL(6,2),
    p50_inference_ms DECIMAL(6,2),
    p95_inference_ms DECIMAL(6,2),
    p99_inference_ms DECIMAL(6,2),
    
    -- Quality Metrics
    avg_compression_ratio DECIMAL(5,4),
    avg_quality_score DECIMAL(3,2),
    
    -- Usage Stats
    total_inferences BIGINT DEFAULT 0,
    success_count BIGINT DEFAULT 0,
    failure_count BIGINT DEFAULT 0,
    fallback_count BIGINT DEFAULT 0,
    
    -- Resource Usage
    avg_gpu_utilization DECIMAL(5,2), -- Percentage
    avg_memory_mb INTEGER,
    
    -- Time Window
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_model_window UNIQUE(model_type, model_version, window_start)
);

-- Indexes for model performance
CREATE INDEX idx_aic_model_perf_type ON aic_model_performance(model_type, model_version);
CREATE INDEX idx_aic_model_perf_window ON aic_model_performance(window_start DESC);

-- ================================================================
-- AIC Alerts Table
-- ================================================================
-- Alerts for AIC issues requiring attention

CREATE TABLE IF NOT EXISTS aic_alerts (
    alert_id VARCHAR(50) PRIMARY KEY DEFAULT ('alert_' || uuid_generate_v4()::TEXT),
    alert_type VARCHAR(50) NOT NULL CHECK (alert_type IN (
        'high_latency', 'quality_degradation', 'model_failure', 
        'excessive_fallback', 'bandwidth_anomaly', 'gpu_overload'
    )),
    severity VARCHAR(20) DEFAULT 'warning' CHECK (severity IN ('info', 'warning', 'critical')),
    
    -- Context
    call_id VARCHAR(50) REFERENCES calls(call_id) ON DELETE SET NULL,
    participant_id VARCHAR(50),
    model_type VARCHAR(50),
    
    -- Alert Details
    message TEXT NOT NULL,
    details JSONB,
    
    -- Metrics at Alert Time
    metric_value DECIMAL(10,2),
    threshold_value DECIMAL(10,2),
    
    -- Resolution
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Prevent duplicate alerts
    CONSTRAINT unique_active_alert UNIQUE(alert_type, call_id, participant_id) 
        WHERE resolved = FALSE
);

-- Indexes for AIC alerts
CREATE INDEX idx_aic_alerts_type ON aic_alerts(alert_type);
CREATE INDEX idx_aic_alerts_severity ON aic_alerts(severity);
CREATE INDEX idx_aic_alerts_unresolved ON aic_alerts(resolved) WHERE resolved = FALSE;
CREATE INDEX idx_aic_alerts_created ON aic_alerts(created_at DESC);

-- ================================================================
-- Update Trigger for aic_configs
-- ================================================================

CREATE OR REPLACE FUNCTION update_aic_config_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_aic_config_update
    BEFORE UPDATE ON aic_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_aic_config_timestamp();

-- ================================================================
-- Function: Calculate AIC Session Stats
-- ================================================================

CREATE OR REPLACE FUNCTION update_aic_session_stats(p_session_id VARCHAR)
RETURNS VOID AS $$
DECLARE
    v_metrics RECORD;
BEGIN
    -- Aggregate metrics for session
    SELECT 
        AVG(compression_ratio) as avg_comp,
        AVG(inference_latency_ms) as avg_latency,
        AVG(quality_score) as avg_quality,
        MAX(compression_ratio) as max_comp,
        MIN(quality_score) as min_quality,
        MAX(inference_latency_ms) as max_latency,
        SUM((original_bandwidth_kbps - compressed_bandwidth_kbps) * 1.0 / 8192) as total_saved_mb,
        COUNT(*) as total_frames,
        SUM(CASE WHEN fallback_triggered THEN 1 ELSE 0 END) as fallback_frames
    INTO v_metrics
    FROM aic_metrics m
    JOIN aic_sessions s ON m.call_id = s.call_id AND m.participant_id = s.participant_id
    WHERE s.session_id = p_session_id;
    
    -- Update session
    UPDATE aic_sessions
    SET
        total_frames_processed = v_metrics.total_frames,
        frames_compressed = v_metrics.total_frames - v_metrics.fallback_frames,
        frames_fallback = v_metrics.fallback_frames,
        avg_compression_ratio = v_metrics.avg_comp,
        avg_inference_latency_ms = v_metrics.avg_latency,
        avg_quality_score = v_metrics.avg_quality,
        total_bandwidth_saved_mb = v_metrics.total_saved_mb,
        peak_compression_ratio = v_metrics.max_comp,
        min_quality_score = v_metrics.min_quality,
        max_inference_latency_ms = v_metrics.max_latency
    WHERE session_id = p_session_id;
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- Function: Create AIC Alert
-- ================================================================

CREATE OR REPLACE FUNCTION create_aic_alert(
    p_alert_type VARCHAR,
    p_severity VARCHAR,
    p_message TEXT,
    p_call_id VARCHAR DEFAULT NULL,
    p_participant_id VARCHAR DEFAULT NULL,
    p_metric_value DECIMAL DEFAULT NULL,
    p_threshold_value DECIMAL DEFAULT NULL,
    p_details JSONB DEFAULT NULL
)
RETURNS VARCHAR AS $$
DECLARE
    v_alert_id VARCHAR;
BEGIN
    INSERT INTO aic_alerts (
        alert_type, severity, message, call_id, participant_id,
        metric_value, threshold_value, details
    )
    VALUES (
        p_alert_type, p_severity, p_message, p_call_id, p_participant_id,
        p_metric_value, p_threshold_value, p_details
    )
    ON CONFLICT ON CONSTRAINT unique_active_alert DO UPDATE
    SET 
        message = EXCLUDED.message,
        metric_value = EXCLUDED.metric_value,
        created_at = NOW()
    RETURNING alert_id INTO v_alert_id;
    
    RETURN v_alert_id;
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- Views for Analytics
-- ================================================================

-- Overall AIC performance view
CREATE OR REPLACE VIEW v_aic_performance_summary AS
SELECT
    DATE_TRUNC('hour', timestamp) as hour,
    COUNT(*) as total_frames,
    AVG(compression_ratio) as avg_compression_ratio,
    AVG(bandwidth_savings_percent) as avg_bandwidth_savings,
    AVG(inference_latency_ms) as avg_inference_latency,
    AVG(quality_score) as avg_quality_score,
    SUM(CASE WHEN fallback_triggered THEN 1 ELSE 0 END) as fallback_count,
    (SUM(CASE WHEN fallback_triggered THEN 1 ELSE 0 END)::DECIMAL / COUNT(*) * 100) as fallback_rate_percent
FROM aic_metrics
GROUP BY DATE_TRUNC('hour', timestamp)
ORDER BY hour DESC;

-- Active AIC sessions view
CREATE OR REPLACE VIEW v_active_aic_sessions AS
SELECT
    s.session_id,
    s.call_id,
    c.room_name,
    s.participant_id,
    cp.identity,
    s.aic_enabled,
    s.current_mode,
    s.total_frames_processed,
    s.avg_compression_ratio,
    s.avg_quality_score,
    s.total_bandwidth_saved_mb,
    s.fallback_count,
    EXTRACT(EPOCH FROM (NOW() - s.started_at))::INTEGER as duration_seconds
FROM aic_sessions s
JOIN calls c ON s.call_id = c.call_id
JOIN call_participants cp ON s.participant_id = cp.participant_id
WHERE s.ended_at IS NULL
ORDER BY s.started_at DESC;

-- ================================================================
-- Row Level Security (RLS)
-- ================================================================

ALTER TABLE aic_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE aic_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE aic_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE aic_alerts ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own AIC configs
CREATE POLICY aic_config_isolation ON aic_configs
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true));

-- Policy: Users can only see their own metrics
CREATE POLICY aic_metrics_isolation ON aic_metrics
    FOR ALL
    USING (
        participant_id IN (
            SELECT participant_id FROM call_participants 
            WHERE identity = current_setting('app.current_user_id', true)
        )
    );

-- Policy: Users can only see their own sessions
CREATE POLICY aic_sessions_isolation ON aic_sessions
    FOR ALL
    USING (
        participant_id IN (
            SELECT participant_id FROM call_participants 
            WHERE identity = current_setting('app.current_user_id', true)
        )
    );

-- Policy: Users can see alerts for their calls
CREATE POLICY aic_alerts_isolation ON aic_alerts
    FOR ALL
    USING (
        call_id IN (
            SELECT c.call_id FROM calls c
            JOIN call_participants cp ON c.call_id = cp.call_id
            WHERE cp.identity = current_setting('app.current_user_id', true)
        )
    );

-- ================================================================
-- Sample Data for Testing (Comment out in production)
-- ================================================================

-- Insert default AIC config
-- INSERT INTO aic_configs (user_id, enabled, mode)
-- VALUES ('test_user_1', true, 'adaptive');

-- ================================================================
-- Migration Complete
-- ================================================================

COMMENT ON TABLE aic_configs IS 'Phase 3: AIC Protocol configuration per user';
COMMENT ON TABLE aic_metrics IS 'Phase 3: Real-time AIC compression metrics';
COMMENT ON TABLE aic_sessions IS 'Phase 3: AIC session state tracking';
COMMENT ON TABLE aic_model_performance IS 'Phase 3: AI model performance tracking';
COMMENT ON TABLE aic_alerts IS 'Phase 3: AIC system alerts';

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Phase 3 AIC Protocol schema migration completed successfully!';
    RAISE NOTICE 'Tables created: aic_configs, aic_metrics, aic_sessions, aic_model_performance, aic_alerts';
    RAISE NOTICE 'Views created: v_aic_performance_summary, v_active_aic_sessions';
    RAISE NOTICE 'Functions created: update_aic_session_stats, create_aic_alert';
END $$;
