-- AuraLink Database Schema - Phase 2: Call Management & File Sharing
-- Migration: 002_phase2_schema
-- Description: Tables for calls, participants, files, links, and quality monitoring
-- Author: AuraLink Engineering
-- Date: 2025-10-15

-- ============================================================================
-- CALLS TABLE (Phase 2)
-- ============================================================================
CREATE TABLE IF NOT EXISTS calls (
    call_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    room_id VARCHAR(100) NOT NULL UNIQUE, -- LiveKit room ID
    room_name VARCHAR(255) NOT NULL,
    
    -- Creator
    created_by UUID NOT NULL,
    organization_id UUID,
    
    -- Call type: one_to_one, group, conference, broadcast
    call_type VARCHAR(20) NOT NULL DEFAULT 'group',
    
    -- Status: waiting, active, ended, failed
    status VARCHAR(20) NOT NULL DEFAULT 'waiting',
    
    -- Timing
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_seconds INT,
    
    -- Participants
    max_participants INT DEFAULT 50,
    participant_count INT DEFAULT 0,
    
    -- Features
    recording_enabled BOOLEAN DEFAULT FALSE,
    recording_url TEXT,
    screen_sharing_enabled BOOLEAN DEFAULT TRUE,
    file_sharing_enabled BOOLEAN DEFAULT TRUE,
    
    -- Quality metrics
    avg_quality_score DECIMAL(3, 2), -- 0.00 to 5.00
    total_data_transferred_mb DECIMAL(10, 2),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT calls_type_check CHECK (call_type IN ('one_to_one', 'group', 'conference', 'broadcast')),
    CONSTRAINT calls_status_check CHECK (status IN ('waiting', 'active', 'ended', 'failed')),
    
    -- Foreign keys
    CONSTRAINT calls_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT calls_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES organizations(organization_id) ON DELETE SET NULL
);

-- Indexes for calls
CREATE INDEX idx_calls_room_id ON calls(room_id);
CREATE INDEX idx_calls_created_by ON calls(created_by);
CREATE INDEX idx_calls_organization_id ON calls(organization_id);
CREATE INDEX idx_calls_status ON calls(status);
CREATE INDEX idx_calls_started_at ON calls(started_at DESC);
CREATE INDEX idx_calls_created_at ON calls(created_at DESC);
CREATE INDEX idx_calls_type ON calls(call_type);

-- RLS for calls
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;

CREATE POLICY calls_select_participant ON calls
    FOR SELECT
    USING (
        created_by = current_setting('app.current_user_id')::UUID
        OR EXISTS (
            SELECT 1 FROM call_participants 
            WHERE call_participants.call_id = calls.call_id 
            AND call_participants.user_id = current_setting('app.current_user_id')::UUID
        )
    );

-- ============================================================================
-- CALL PARTICIPANTS TABLE (Phase 2)
-- ============================================================================
CREATE TABLE IF NOT EXISTS call_participants (
    participant_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL,
    user_id UUID,
    
    -- Identity
    identity VARCHAR(255) NOT NULL, -- LiveKit participant identity
    display_name VARCHAR(100),
    
    -- Role: host, moderator, participant, viewer
    role VARCHAR(20) NOT NULL DEFAULT 'participant',
    
    -- Status: waiting, connected, disconnected, left
    status VARCHAR(20) NOT NULL DEFAULT 'waiting',
    
    -- Timing
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    left_at TIMESTAMPTZ,
    duration_seconds INT,
    
    -- Media state
    audio_enabled BOOLEAN DEFAULT TRUE,
    video_enabled BOOLEAN DEFAULT TRUE,
    screen_sharing BOOLEAN DEFAULT FALSE,
    
    -- Quality metrics
    avg_quality_score DECIMAL(3, 2),
    packet_loss_percent DECIMAL(5, 2),
    avg_latency_ms INT,
    
    -- Connection info
    ip_address INET,
    user_agent TEXT,
    connection_type VARCHAR(20), -- udp, tcp, relay
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT call_participants_role_check CHECK (role IN ('host', 'moderator', 'participant', 'viewer')),
    CONSTRAINT call_participants_status_check CHECK (status IN ('waiting', 'connected', 'disconnected', 'left')),
    
    -- Foreign keys
    CONSTRAINT call_participants_call_id_fkey FOREIGN KEY (call_id) REFERENCES calls(call_id) ON DELETE CASCADE,
    CONSTRAINT call_participants_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

-- Indexes for call_participants
CREATE INDEX idx_call_participants_call_id ON call_participants(call_id);
CREATE INDEX idx_call_participants_user_id ON call_participants(user_id);
CREATE INDEX idx_call_participants_identity ON call_participants(identity);
CREATE INDEX idx_call_participants_status ON call_participants(status);
CREATE INDEX idx_call_participants_joined_at ON call_participants(joined_at DESC);

-- RLS for call_participants
ALTER TABLE call_participants ENABLE ROW LEVEL SECURITY;

CREATE POLICY call_participants_select_own ON call_participants
    FOR SELECT
    USING (
        user_id = current_setting('app.current_user_id')::UUID
        OR EXISTS (
            SELECT 1 FROM calls 
            WHERE calls.call_id = call_participants.call_id 
            AND calls.created_by = current_setting('app.current_user_id')::UUID
        )
    );

-- ============================================================================
-- FILES TABLE (Phase 2 - File Sharing)
-- ============================================================================
CREATE TABLE IF NOT EXISTS files (
    file_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID,
    room_name VARCHAR(255) NOT NULL,
    
    -- Uploader
    uploader_id UUID NOT NULL,
    uploader_identity VARCHAR(255) NOT NULL,
    
    -- File info
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(100), -- MIME type
    file_size BIGINT NOT NULL, -- bytes
    
    -- Storage
    storage_path TEXT NOT NULL, -- S3/Supabase storage path
    storage_bucket VARCHAR(100) DEFAULT 'auralink-files',
    download_url TEXT,
    
    -- Security
    access_level VARCHAR(20) DEFAULT 'call_participants', -- public, call_participants, private
    virus_scanned BOOLEAN DEFAULT FALSE,
    scan_status VARCHAR(20) DEFAULT 'pending', -- pending, clean, infected, failed
    
    -- Expiration
    expires_at TIMESTAMPTZ,
    
    -- Metadata
    thumbnail_url TEXT,
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT files_access_level_check CHECK (access_level IN ('public', 'call_participants', 'private')),
    CONSTRAINT files_scan_status_check CHECK (scan_status IN ('pending', 'clean', 'infected', 'failed')),
    
    -- Foreign keys
    CONSTRAINT files_call_id_fkey FOREIGN KEY (call_id) REFERENCES calls(call_id) ON DELETE SET NULL,
    CONSTRAINT files_uploader_id_fkey FOREIGN KEY (uploader_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Indexes for files
CREATE INDEX idx_files_call_id ON files(call_id);
CREATE INDEX idx_files_uploader_id ON files(uploader_id);
CREATE INDEX idx_files_room_name ON files(room_name);
CREATE INDEX idx_files_created_at ON files(created_at DESC);
CREATE INDEX idx_files_expires_at ON files(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_files_scan_status ON files(scan_status);

-- RLS for files
ALTER TABLE files ENABLE ROW LEVEL SECURITY;

CREATE POLICY files_select_access ON files
    FOR SELECT
    USING (
        access_level = 'public'
        OR uploader_id = current_setting('app.current_user_id')::UUID
        OR (access_level = 'call_participants' AND EXISTS (
            SELECT 1 FROM call_participants 
            WHERE call_participants.call_id = files.call_id 
            AND call_participants.user_id = current_setting('app.current_user_id')::UUID
        ))
    );

-- ============================================================================
-- SHAREABLE LINKS TABLE (Phase 2)
-- ============================================================================
CREATE TABLE IF NOT EXISTS shareable_links (
    link_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    short_code VARCHAR(20) UNIQUE NOT NULL, -- e.g., "abc123"
    
    -- Target
    room_id VARCHAR(100),
    call_id UUID,
    
    -- Creator
    created_by UUID NOT NULL,
    organization_id UUID,
    
    -- Link properties
    link_type VARCHAR(20) NOT NULL DEFAULT 'room', -- room, call, agent
    title VARCHAR(255),
    description TEXT,
    
    -- Access control
    access_type VARCHAR(20) NOT NULL DEFAULT 'public', -- public, password, restricted
    password_hash VARCHAR(255), -- bcrypt hash
    max_uses INT, -- NULL = unlimited
    current_uses INT DEFAULT 0,
    
    -- Features
    enable_recording BOOLEAN DEFAULT FALSE,
    enable_screen_share BOOLEAN DEFAULT TRUE,
    enable_chat BOOLEAN DEFAULT TRUE,
    
    -- Participant settings
    auto_join BOOLEAN DEFAULT FALSE,
    require_approval BOOLEAN DEFAULT FALSE,
    default_role VARCHAR(20) DEFAULT 'participant',
    
    -- Expiration
    expires_at TIMESTAMPTZ,
    
    -- Analytics
    total_clicks INT DEFAULT 0,
    unique_visitors INT DEFAULT 0,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    
    -- Constraints
    CONSTRAINT shareable_links_type_check CHECK (link_type IN ('room', 'call', 'agent')),
    CONSTRAINT shareable_links_access_check CHECK (access_type IN ('public', 'password', 'restricted')),
    CONSTRAINT shareable_links_role_check CHECK (default_role IN ('host', 'moderator', 'participant', 'viewer')),
    
    -- Foreign keys
    CONSTRAINT shareable_links_call_id_fkey FOREIGN KEY (call_id) REFERENCES calls(call_id) ON DELETE CASCADE,
    CONSTRAINT shareable_links_created_by_fkey FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT shareable_links_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES organizations(organization_id) ON DELETE SET NULL
);

-- Indexes for shareable_links
CREATE INDEX idx_shareable_links_short_code ON shareable_links(short_code);
CREATE INDEX idx_shareable_links_room_id ON shareable_links(room_id);
CREATE INDEX idx_shareable_links_call_id ON shareable_links(call_id);
CREATE INDEX idx_shareable_links_created_by ON shareable_links(created_by);
CREATE INDEX idx_shareable_links_organization_id ON shareable_links(organization_id);
CREATE INDEX idx_shareable_links_is_active ON shareable_links(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_shareable_links_expires_at ON shareable_links(expires_at) WHERE expires_at IS NOT NULL;

-- RLS for shareable_links
ALTER TABLE shareable_links ENABLE ROW LEVEL SECURITY;

CREATE POLICY shareable_links_select_own ON shareable_links
    FOR SELECT
    USING (created_by = current_setting('app.current_user_id')::UUID);

-- ============================================================================
-- QUALITY METRICS TABLE (Phase 2)
-- ============================================================================
CREATE TABLE IF NOT EXISTS quality_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL,
    participant_id UUID NOT NULL,
    
    -- Timestamp
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Network metrics
    packet_loss_percent DECIMAL(5, 2),
    jitter_ms INT,
    latency_ms INT,
    bandwidth_kbps INT,
    
    -- Media quality
    video_resolution VARCHAR(20), -- e.g., "1920x1080"
    video_fps INT,
    audio_bitrate_kbps INT,
    video_bitrate_kbps INT,
    
    -- Connection
    connection_type VARCHAR(20), -- udp, tcp, relay
    ice_state VARCHAR(20), -- checking, connected, failed
    
    -- Quality score (0-5)
    quality_score DECIMAL(3, 2),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Foreign keys
    CONSTRAINT quality_metrics_call_id_fkey FOREIGN KEY (call_id) REFERENCES calls(call_id) ON DELETE CASCADE,
    CONSTRAINT quality_metrics_participant_id_fkey FOREIGN KEY (participant_id) REFERENCES call_participants(participant_id) ON DELETE CASCADE
);

-- Indexes for quality_metrics
CREATE INDEX idx_quality_metrics_call_id ON quality_metrics(call_id);
CREATE INDEX idx_quality_metrics_participant_id ON quality_metrics(participant_id);
CREATE INDEX idx_quality_metrics_recorded_at ON quality_metrics(recorded_at DESC);
CREATE INDEX idx_quality_metrics_quality_score ON quality_metrics(quality_score);

-- ============================================================================
-- CONTACTS TABLE (Phase 2)
-- ============================================================================
CREATE TABLE IF NOT EXISTS contacts (
    contact_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    contact_user_id UUID NOT NULL,
    
    -- Relationship
    relationship_type VARCHAR(20) DEFAULT 'friend', -- friend, colleague, blocked
    
    -- Custom name
    nickname VARCHAR(100),
    
    -- Status
    is_favorite BOOLEAN DEFAULT FALSE,
    is_blocked BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    notes TEXT,
    tags VARCHAR(50)[],
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT contacts_not_self CHECK (user_id != contact_user_id),
    CONSTRAINT contacts_relationship_check CHECK (relationship_type IN ('friend', 'colleague', 'blocked')),
    CONSTRAINT contacts_unique_pair UNIQUE (user_id, contact_user_id),
    
    -- Foreign keys
    CONSTRAINT contacts_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT contacts_contact_user_id_fkey FOREIGN KEY (contact_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Indexes for contacts
CREATE INDEX idx_contacts_user_id ON contacts(user_id);
CREATE INDEX idx_contacts_contact_user_id ON contacts(contact_user_id);
CREATE INDEX idx_contacts_relationship_type ON contacts(relationship_type);
CREATE INDEX idx_contacts_is_favorite ON contacts(is_favorite) WHERE is_favorite = TRUE;

-- RLS for contacts
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;

CREATE POLICY contacts_select_own ON contacts
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- ============================================================================
-- TRIGGERS (Phase 2)
-- ============================================================================

-- Update updated_at timestamp
CREATE TRIGGER update_calls_updated_at BEFORE UPDATE ON calls
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_call_participants_updated_at BEFORE UPDATE ON call_participants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_files_updated_at BEFORE UPDATE ON files
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_shareable_links_updated_at BEFORE UPDATE ON shareable_links
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON contacts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Update call participant count automatically
CREATE OR REPLACE FUNCTION update_call_participant_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
        UPDATE calls
        SET participant_count = (
            SELECT COUNT(*) FROM call_participants 
            WHERE call_id = NEW.call_id AND status IN ('waiting', 'connected')
        )
        WHERE call_id = NEW.call_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE calls
        SET participant_count = (
            SELECT COUNT(*) FROM call_participants 
            WHERE call_id = OLD.call_id AND status IN ('waiting', 'connected')
        )
        WHERE call_id = OLD.call_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_call_participant_count
AFTER INSERT OR UPDATE OF status OR DELETE ON call_participants
FOR EACH ROW EXECUTE FUNCTION update_call_participant_count();

-- Update call duration on end
CREATE OR REPLACE FUNCTION update_call_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'ended' AND OLD.status != 'ended' AND NEW.started_at IS NOT NULL THEN
        NEW.ended_at = NOW();
        NEW.duration_seconds = EXTRACT(EPOCH FROM (NEW.ended_at - NEW.started_at))::INT;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_call_duration
BEFORE UPDATE OF status ON calls
FOR EACH ROW EXECUTE FUNCTION update_call_duration();

-- Update participant duration on leave
CREATE OR REPLACE FUNCTION update_participant_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IN ('disconnected', 'left') AND OLD.status NOT IN ('disconnected', 'left') THEN
        NEW.left_at = NOW();
        NEW.duration_seconds = EXTRACT(EPOCH FROM (NEW.left_at - NEW.joined_at))::INT;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_participant_duration
BEFORE UPDATE OF status ON call_participants
FOR EACH ROW EXECUTE FUNCTION update_participant_duration();

-- ============================================================================
-- FUNCTIONS (Phase 2)
-- ============================================================================

-- Generate unique short code for shareable links
CREATE OR REPLACE FUNCTION generate_short_code(length INT DEFAULT 8)
RETURNS VARCHAR AS $$
DECLARE
    chars VARCHAR := 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    result VARCHAR := '';
    i INT;
BEGIN
    FOR i IN 1..length LOOP
        result := result || substr(chars, floor(random() * length(chars) + 1)::INT, 1);
    END LOOP;
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Get active calls for a user
CREATE OR REPLACE FUNCTION get_active_calls(user_uuid UUID)
RETURNS TABLE (
    call_id UUID,
    room_name VARCHAR,
    status VARCHAR,
    participant_count INT,
    started_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT c.call_id, c.room_name, c.status, c.participant_count, c.started_at
    FROM calls c
    WHERE c.status = 'active'
    AND EXISTS (
        SELECT 1 FROM call_participants cp
        WHERE cp.call_id = c.call_id
        AND cp.user_id = user_uuid
        AND cp.status = 'connected'
    )
    ORDER BY c.started_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Clean expired files
CREATE OR REPLACE FUNCTION clean_expired_files()
RETURNS INT AS $$
DECLARE
    deleted_count INT;
BEGIN
    DELETE FROM files WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Clean expired shareable links
CREATE OR REPLACE FUNCTION clean_expired_links()
RETURNS INT AS $$
DECLARE
    updated_count INT;
BEGIN
    UPDATE shareable_links 
    SET is_active = FALSE 
    WHERE expires_at < NOW() AND is_active = TRUE;
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RETURN updated_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEWS (Phase 2)
-- ============================================================================

-- Active calls view
CREATE OR REPLACE VIEW active_calls_view AS
SELECT 
    c.call_id,
    c.room_id,
    c.room_name,
    c.created_by,
    u.display_name as creator_name,
    c.call_type,
    c.participant_count,
    c.started_at,
    EXTRACT(EPOCH FROM (NOW() - c.started_at))::INT as duration_seconds,
    c.recording_enabled,
    c.metadata
FROM calls c
LEFT JOIN users u ON c.created_by = u.user_id
WHERE c.status = 'active';

-- Call history with stats
CREATE OR REPLACE VIEW call_history_view AS
SELECT 
    c.call_id,
    c.room_name,
    c.call_type,
    c.status,
    c.started_at,
    c.ended_at,
    c.duration_seconds,
    c.participant_count,
    c.avg_quality_score,
    c.recording_url,
    u.display_name as creator_name,
    u.aura_id as creator_aura_id,
    COUNT(DISTINCT f.file_id) as files_shared
FROM calls c
LEFT JOIN users u ON c.created_by = u.user_id
LEFT JOIN files f ON c.call_id = f.call_id
GROUP BY c.call_id, u.display_name, u.aura_id;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE calls IS 'WebRTC call sessions with LiveKit integration';
COMMENT ON TABLE call_participants IS 'Participants in calls with real-time status';
COMMENT ON TABLE files IS 'Files shared during calls with virus scanning';
COMMENT ON TABLE shareable_links IS 'Shareable links for rooms/calls with analytics';
COMMENT ON TABLE quality_metrics IS 'Real-time quality monitoring for calls';
COMMENT ON TABLE contacts IS 'User contact management';

COMMENT ON COLUMN calls.room_id IS 'LiveKit room identifier';
COMMENT ON COLUMN call_participants.identity IS 'LiveKit participant identity';
COMMENT ON COLUMN files.storage_path IS 'Path in Supabase storage or S3';
COMMENT ON COLUMN shareable_links.short_code IS 'URL-safe short code for sharing';

-- ============================================================================
-- MIGRATION COMPLETE - PHASE 2
-- ============================================================================
