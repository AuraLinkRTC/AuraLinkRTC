-- Migration 009: PostgreSQL Functions for Trust and Routing
-- Description: Implements core business logic functions for trust scores and route caching
-- Author: AuraLink Team
-- Date: 2025-10-16

-- ==============================================================================
-- TRUST SCORE CALCULATION FUNCTIONS
-- ==============================================================================

-- Calculate trust score for AuraIDs and mesh nodes
CREATE OR REPLACE FUNCTION calculate_trust_score(
    p_entity_type VARCHAR(50),
    p_entity_id VARCHAR(255)
)
RETURNS NUMERIC(5,2)
LANGUAGE plpgsql
AS $$
DECLARE
    v_base_score NUMERIC(5,2) := 50.0;
    v_verification_bonus NUMERIC(5,2) := 0.0;
    v_behavior_score NUMERIC(5,2) := 0.0;
    v_penalty_score NUMERIC(5,2) := 0.0;
    v_total_score NUMERIC(5,2);
    v_verification_count INT;
    v_uptime_pct NUMERIC(5,2);
    v_reputation NUMERIC(5,2);
    v_abuse_count INT;
BEGIN
    -- Calculate based on entity type
    IF p_entity_type = 'aura_id' THEN
        -- Get verification bonuses
        SELECT 
            SUM(
                CASE verification_method
                    WHEN 'email' THEN 10.0
                    WHEN 'phone' THEN 15.0
                    WHEN 'document' THEN 25.0
                    WHEN 'social' THEN 5.0
                    WHEN 'biometric' THEN 20.0
                    ELSE 0
                END
            )
        INTO v_verification_bonus
        FROM aura_id_verifications
        WHERE aura_id = p_entity_id AND status = 'verified';
        
        -- Set to 0 if NULL
        v_verification_bonus := COALESCE(v_verification_bonus, 0.0);
        
        -- Get abuse reports count
        SELECT COALESCE(abuse_reports_count, 0)
        INTO v_abuse_count
        FROM aura_id_registry
        WHERE aura_id = p_entity_id;
        
        -- Calculate penalty (-20 per report)
        v_penalty_score := -(v_abuse_count * 20.0);
        
        -- Behavior score reserved for future use
        v_behavior_score := 0.0;
        
    ELSIF p_entity_type = 'mesh_node' THEN
        -- Get node metrics
        SELECT 
            COALESCE(uptime_percentage, 0.0),
            COALESCE(reputation_score, 0.0),
            COALESCE(abuse_reports_count, 0)
        INTO v_uptime_pct, v_reputation, v_abuse_count
        FROM mesh_nodes
        WHERE node_id::TEXT = p_entity_id;
        
        -- Calculate behavior score based on uptime and reputation
        v_behavior_score := (v_uptime_pct / 5.0) + (v_reputation / 5.0);
        
        -- Calculate penalty
        v_penalty_score := -(v_abuse_count * 20.0);
        
        -- No verification bonus for nodes
        v_verification_bonus := 0.0;
        
    ELSE
        RAISE EXCEPTION 'Invalid entity_type: %', p_entity_type;
    END IF;
    
    -- Calculate total score (clamped to 0-100)
    v_total_score := v_base_score + v_verification_bonus + v_behavior_score + v_penalty_score;
    v_total_score := GREATEST(0.0, LEAST(100.0, v_total_score));
    
    -- Upsert into trust_scores table
    INSERT INTO trust_scores (
        entity_type,
        entity_id,
        base_score,
        verification_bonus,
        behavior_score,
        penalty_score,
        calculation_metadata,
        last_updated
    ) VALUES (
        p_entity_type,
        p_entity_id,
        v_base_score,
        v_verification_bonus,
        v_behavior_score,
        v_penalty_score,
        jsonb_build_object(
            'calculated_at', NOW(),
            'abuse_count', v_abuse_count
        ),
        NOW()
    )
    ON CONFLICT (entity_type, entity_id) DO UPDATE SET
        base_score = EXCLUDED.base_score,
        verification_bonus = EXCLUDED.verification_bonus,
        behavior_score = EXCLUDED.behavior_score,
        penalty_score = EXCLUDED.penalty_score,
        calculation_metadata = EXCLUDED.calculation_metadata,
        last_updated = NOW();
    
    RETURN v_total_score;
END;
$$;

COMMENT ON FUNCTION calculate_trust_score IS 'Calculates and updates trust score for AuraIDs or mesh nodes';

-- ==============================================================================
-- MESH ROUTING FUNCTIONS
-- ==============================================================================

-- Update mesh route cache with quality score
CREATE OR REPLACE FUNCTION update_mesh_route_cache(
    p_route_id UUID,
    p_quality_score NUMERIC(5,2)
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_source_aura VARCHAR(255);
    v_dest_aura VARCHAR(255);
    v_cache_key VARCHAR(512);
    v_route_data JSONB;
BEGIN
    -- Get route information
    SELECT 
        source_aura_id,
        dest_aura_id,
        jsonb_build_object(
            'route_id', route_id,
            'path_type', path_type,
            'relay_nodes', relay_nodes,
            'quality_score', p_quality_score,
            'predicted_latency_ms', predicted_latency_ms,
            'cached_at', NOW()
        )
    INTO v_source_aura, v_dest_aura, v_route_data
    FROM mesh_routes
    WHERE route_id = p_route_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Route not found: %', p_route_id;
    END IF;
    
    -- Build cache key
    v_cache_key := 'route:cache:' || v_source_aura || ':' || v_dest_aura;
    
    -- Upsert into cache table (5-minute TTL)
    INSERT INTO mesh_route_cache (
        cache_key,
        route_id,
        route_data,
        hit_count,
        created_at,
        expires_at
    ) VALUES (
        v_cache_key,
        p_route_id,
        v_route_data,
        1,
        NOW(),
        NOW() + INTERVAL '5 minutes'
    )
    ON CONFLICT (cache_key) DO UPDATE SET
        route_id = EXCLUDED.route_id,
        route_data = EXCLUDED.route_data,
        hit_count = mesh_route_cache.hit_count + 1,
        created_at = NOW(),
        expires_at = NOW() + INTERVAL '5 minutes';
    
    -- Update quality score in mesh_routes
    UPDATE mesh_routes
    SET 
        quality_score = p_quality_score,
        last_used_at = NOW()
    WHERE route_id = p_route_id;
    
END;
$$;

COMMENT ON FUNCTION update_mesh_route_cache IS 'Updates route cache with quality score and 5-minute TTL';

-- ==============================================================================
-- CLEANUP AND MAINTENANCE FUNCTIONS
-- ==============================================================================

-- Cleanup expired verifications
CREATE OR REPLACE FUNCTION cleanup_expired_verifications()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    DELETE FROM aura_id_verifications
    WHERE status = 'pending'
      AND expires_at < NOW();
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    
    RETURN v_deleted_count;
END;
$$;

COMMENT ON FUNCTION cleanup_expired_verifications IS 'Deletes expired pending verifications, returns count deleted';

-- Cleanup expired route cache entries
CREATE OR REPLACE FUNCTION cleanup_expired_route_cache()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    DELETE FROM mesh_route_cache
    WHERE expires_at < NOW();
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    
    RETURN v_deleted_count;
END;
$$;

COMMENT ON FUNCTION cleanup_expired_route_cache IS 'Deletes expired route cache entries, returns count deleted';

-- Cleanup expired notifications
CREATE OR REPLACE FUNCTION cleanup_expired_notifications()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    DELETE FROM notification_queue
    WHERE expires_at < NOW()
      AND status NOT IN ('acted', 'opened');
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    
    RETURN v_deleted_count;
END;
$$;

COMMENT ON FUNCTION cleanup_expired_notifications IS 'Deletes expired unacted notifications, returns count deleted';

-- Mark offline mesh nodes
CREATE OR REPLACE FUNCTION mark_offline_mesh_nodes()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_updated_count INTEGER;
BEGIN
    UPDATE mesh_nodes
    SET status = 'offline'
    WHERE status = 'active'
      AND last_seen_at < NOW() - INTERVAL '2 minutes';
    
    GET DIAGNOSTICS v_updated_count = ROW_COUNT;
    
    RETURN v_updated_count;
END;
$$;

COMMENT ON FUNCTION mark_offline_mesh_nodes IS 'Marks nodes offline if no heartbeat in 2 minutes, returns count updated';

-- ==============================================================================
-- HELPER FUNCTIONS
-- ==============================================================================

-- Get trust level from score
CREATE OR REPLACE FUNCTION get_trust_level(p_score NUMERIC(5,2))
RETURNS VARCHAR(20)
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    RETURN CASE
        WHEN p_score >= 80 THEN 'verified'
        WHEN p_score >= 60 THEN 'trusted'
        WHEN p_score >= 40 THEN 'established'
        WHEN p_score >= 20 THEN 'new'
        ELSE 'caution'
    END;
END;
$$;

COMMENT ON FUNCTION get_trust_level IS 'Converts numeric trust score to trust level label';

-- Check if AuraID can be discovered based on privacy
CREATE OR REPLACE FUNCTION can_discover_auraid(
    p_aura_id VARCHAR(255),
    p_requester_aura_id VARCHAR(255)
)
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_privacy_level VARCHAR(20);
    v_is_friend BOOLEAN;
BEGIN
    -- Get privacy level
    SELECT privacy_level
    INTO v_privacy_level
    FROM aura_id_registry
    WHERE aura_id = p_aura_id AND is_active = true;
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    -- Public AuraIDs are always discoverable
    IF v_privacy_level = 'public' THEN
        RETURN TRUE;
    END IF;
    
    -- Private AuraIDs not discoverable
    IF v_privacy_level = 'private' THEN
        RETURN p_aura_id = p_requester_aura_id;
    END IF;
    
    -- Friends-only: check if requester is a contact
    IF v_privacy_level = 'friends' THEN
        -- Check mutual contact
        SELECT EXISTS (
            SELECT 1 FROM contacts
            WHERE (user_id = (SELECT user_id FROM aura_id_registry WHERE aura_id = p_aura_id)
                   AND contact_aura_id = p_requester_aura_id)
               OR (user_id = (SELECT user_id FROM aura_id_registry WHERE aura_id = p_requester_aura_id)
                   AND contact_aura_id = p_aura_id)
        ) INTO v_is_friend;
        
        RETURN v_is_friend;
    END IF;
    
    RETURN FALSE;
END;
$$;

COMMENT ON FUNCTION can_discover_auraid IS 'Checks if requester can discover AuraID based on privacy settings';

-- ==============================================================================
-- SCHEDULED JOB WRAPPER FUNCTION
-- ==============================================================================

-- Run all cleanup tasks (call from pg_cron or external scheduler)
CREATE OR REPLACE FUNCTION run_scheduled_cleanup()
RETURNS TABLE (
    task VARCHAR(50),
    items_processed INTEGER,
    execution_time_ms INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_start_time TIMESTAMP;
    v_end_time TIMESTAMP;
    v_count INTEGER;
BEGIN
    -- Cleanup expired verifications
    v_start_time := clock_timestamp();
    v_count := cleanup_expired_verifications();
    v_end_time := clock_timestamp();
    task := 'verifications';
    items_processed := v_count;
    execution_time_ms := EXTRACT(MILLISECONDS FROM v_end_time - v_start_time)::INTEGER;
    RETURN NEXT;
    
    -- Cleanup expired route cache
    v_start_time := clock_timestamp();
    v_count := cleanup_expired_route_cache();
    v_end_time := clock_timestamp();
    task := 'route_cache';
    items_processed := v_count;
    execution_time_ms := EXTRACT(MILLISECONDS FROM v_end_time - v_start_time)::INTEGER;
    RETURN NEXT;
    
    -- Cleanup expired notifications
    v_start_time := clock_timestamp();
    v_count := cleanup_expired_notifications();
    v_end_time := clock_timestamp();
    task := 'notifications';
    items_processed := v_count;
    execution_time_ms := EXTRACT(MILLISECONDS FROM v_end_time - v_start_time)::INTEGER;
    RETURN NEXT;
    
    -- Mark offline nodes
    v_start_time := clock_timestamp();
    v_count := mark_offline_mesh_nodes();
    v_end_time := clock_timestamp();
    task := 'offline_nodes';
    items_processed := v_count;
    execution_time_ms := EXTRACT(MILLISECONDS FROM v_end_time - v_start_time)::INTEGER;
    RETURN NEXT;
    
END;
$$;

COMMENT ON FUNCTION run_scheduled_cleanup IS 'Runs all cleanup tasks, returns execution summary';

-- ==============================================================================
-- GRANTS
-- ==============================================================================

-- Grant execute to service role
GRANT EXECUTE ON FUNCTION calculate_trust_score TO service_role;
GRANT EXECUTE ON FUNCTION update_mesh_route_cache TO service_role;
GRANT EXECUTE ON FUNCTION cleanup_expired_verifications TO service_role;
GRANT EXECUTE ON FUNCTION cleanup_expired_route_cache TO service_role;
GRANT EXECUTE ON FUNCTION cleanup_expired_notifications TO service_role;
GRANT EXECUTE ON FUNCTION mark_offline_mesh_nodes TO service_role;
GRANT EXECUTE ON FUNCTION get_trust_level TO service_role;
GRANT EXECUTE ON FUNCTION can_discover_auraid TO service_role;
GRANT EXECUTE ON FUNCTION run_scheduled_cleanup TO service_role;

-- Grant read-only functions to authenticated users
GRANT EXECUTE ON FUNCTION get_trust_level TO authenticated;
GRANT EXECUTE ON FUNCTION can_discover_auraid TO authenticated;

-- Migration complete
