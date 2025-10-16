-- AuraLink Database Schema - Phase 4: AI Core & Memory System
-- Migration: 004_phase4_ai_core_schema
-- Description: Memory system, AI providers, speech processing, translation, and workflows
-- Author: AuraLink Engineering
-- Date: 2025-10-16
-- Phase: 4

-- ============================================================================
-- AI AGENTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS ai_agents (
    agent_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Basic Info
    name VARCHAR(255) NOT NULL,
    description TEXT,
    avatar_url TEXT,
    
    -- Configuration
    model VARCHAR(100) NOT NULL DEFAULT 'gpt-4',
    provider VARCHAR(50) NOT NULL DEFAULT 'openai',
    temperature DECIMAL(3,2) DEFAULT 0.7 CHECK (temperature >= 0 AND temperature <= 2),
    max_tokens INT DEFAULT 2000 CHECK (max_tokens > 0),
    
    -- Prompts
    system_prompt TEXT,
    greeting_message TEXT,
    
    -- Features
    memory_enabled BOOLEAN DEFAULT TRUE,
    auto_join_rooms BOOLEAN DEFAULT FALSE,
    voice_enabled BOOLEAN DEFAULT TRUE,
    translation_enabled BOOLEAN DEFAULT FALSE,
    
    -- Voice Settings
    tts_provider VARCHAR(50) DEFAULT 'elevenlabs',
    tts_voice_id VARCHAR(100),
    tts_speed DECIMAL(3,2) DEFAULT 1.0 CHECK (tts_speed >= 0.5 AND tts_speed <= 2.0),
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    config JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    
    -- Indexes inline
    CONSTRAINT ai_agents_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_ai_agents_user_id ON ai_agents(user_id);
CREATE INDEX idx_ai_agents_created_at ON ai_agents(created_at DESC);
CREATE INDEX idx_ai_agents_is_active ON ai_agents(is_active) WHERE is_active = TRUE;

-- RLS
ALTER TABLE ai_agents ENABLE ROW LEVEL SECURITY;

CREATE POLICY ai_agents_select_own ON ai_agents
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id')::UUID);

CREATE POLICY ai_agents_insert_own ON ai_agents
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id')::UUID);

CREATE POLICY ai_agents_update_own ON ai_agents
    FOR UPDATE
    USING (user_id = current_setting('app.current_user_id')::UUID)
    WITH CHECK (user_id = current_setting('app.current_user_id')::UUID);

CREATE POLICY ai_agents_delete_own ON ai_agents
    FOR DELETE
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- ============================================================================
-- MEMORY SYSTEM TABLES (SuperMemory.ai Architecture)
-- ============================================================================

-- Memory Chunks (Vector Storage)
CREATE TABLE IF NOT EXISTS memory_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    agent_id UUID REFERENCES ai_agents(agent_id) ON DELETE SET NULL,
    
    -- Content
    content TEXT NOT NULL,
    content_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA-256 hash for deduplication
    
    -- Embeddings (pgvector extension)
    -- Note: Install pgvector extension separately
    -- embedding vector(1536), -- OpenAI ada-002 dimension
    embedding_metadata JSONB DEFAULT '{}', -- Store embedding info
    
    -- Source
    source_type VARCHAR(50) NOT NULL, -- 'call', 'chat', 'file', 'external'
    source_id VARCHAR(255),
    
    -- Context
    context JSONB DEFAULT '{}',
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    accessed_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ, -- For memory expiration
    
    CONSTRAINT memory_chunks_source_type_check CHECK (
        source_type IN ('call', 'chat', 'file', 'external', 'system')
    )
);

CREATE INDEX idx_memory_chunks_user_id ON memory_chunks(user_id);
CREATE INDEX idx_memory_chunks_agent_id ON memory_chunks(agent_id) WHERE agent_id IS NOT NULL;
CREATE INDEX idx_memory_chunks_content_hash ON memory_chunks(content_hash);
CREATE INDEX idx_memory_chunks_created_at ON memory_chunks(created_at DESC);
CREATE INDEX idx_memory_chunks_tags ON memory_chunks USING gin(tags);
CREATE INDEX idx_memory_chunks_source ON memory_chunks(source_type, source_id);

-- Full-text search
CREATE INDEX idx_memory_chunks_content_search ON memory_chunks USING gin(to_tsvector('english', content));

-- RLS
ALTER TABLE memory_chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY memory_chunks_select_own ON memory_chunks
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id')::UUID);

CREATE POLICY memory_chunks_insert_own ON memory_chunks
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id')::UUID);

CREATE POLICY memory_chunks_delete_own ON memory_chunks
    FOR DELETE
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- Memory Relationships (Graph Storage)
CREATE TABLE IF NOT EXISTS memory_relationships (
    relationship_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Nodes
    source_chunk_id UUID NOT NULL REFERENCES memory_chunks(chunk_id) ON DELETE CASCADE,
    target_chunk_id UUID NOT NULL REFERENCES memory_chunks(chunk_id) ON DELETE CASCADE,
    
    -- Relationship
    relationship_type VARCHAR(50) NOT NULL, -- 'relates_to', 'derived_from', 'contradicts', 'supports'
    strength DECIMAL(3,2) DEFAULT 0.5 CHECK (strength >= 0 AND strength <= 1),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT memory_relationships_different_chunks CHECK (source_chunk_id != target_chunk_id),
    CONSTRAINT memory_relationships_unique UNIQUE (source_chunk_id, target_chunk_id, relationship_type)
);

CREATE INDEX idx_memory_relationships_user_id ON memory_relationships(user_id);
CREATE INDEX idx_memory_relationships_source ON memory_relationships(source_chunk_id);
CREATE INDEX idx_memory_relationships_target ON memory_relationships(target_chunk_id);
CREATE INDEX idx_memory_relationships_type ON memory_relationships(relationship_type);

-- RLS
ALTER TABLE memory_relationships ENABLE ROW LEVEL SECURITY;

CREATE POLICY memory_relationships_select_own ON memory_relationships
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- Memory Sessions (Track recall sessions)
CREATE TABLE IF NOT EXISTS memory_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    agent_id UUID REFERENCES ai_agents(agent_id) ON DELETE SET NULL,
    
    -- Session details
    query TEXT NOT NULL,
    results_count INT DEFAULT 0,
    avg_relevance_score DECIMAL(4,3),
    
    -- Performance
    recall_time_ms INT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_memory_sessions_user_id ON memory_sessions(user_id);
CREATE INDEX idx_memory_sessions_agent_id ON memory_sessions(agent_id);
CREATE INDEX idx_memory_sessions_created_at ON memory_sessions(created_at DESC);

-- ============================================================================
-- AI PROVIDER CONFIGURATIONS (BYOK Support)
-- ============================================================================
CREATE TABLE IF NOT EXISTS ai_provider_configs (
    config_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(organization_id) ON DELETE CASCADE,
    
    -- Provider details
    provider_name VARCHAR(50) NOT NULL, -- 'openai', 'anthropic', 'elevenlabs', 'whisper', etc.
    provider_type VARCHAR(50) NOT NULL, -- 'llm', 'tts', 'stt', 'translation'
    
    -- API Configuration (encrypted)
    api_key_encrypted TEXT, -- Should be encrypted at application level
    api_endpoint TEXT,
    
    -- Settings
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Usage limits
    rate_limit_per_minute INT,
    monthly_budget_usd DECIMAL(10,2),
    
    -- Configuration
    config JSONB DEFAULT '{}',
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT ai_provider_configs_provider_type_check CHECK (
        provider_type IN ('llm', 'tts', 'stt', 'translation', 'moderation', 'embeddings')
    )
);

CREATE INDEX idx_ai_provider_configs_user_id ON ai_provider_configs(user_id);
CREATE INDEX idx_ai_provider_configs_org_id ON ai_provider_configs(organization_id);
CREATE INDEX idx_ai_provider_configs_provider ON ai_provider_configs(provider_name, provider_type);
CREATE INDEX idx_ai_provider_configs_active ON ai_provider_configs(is_active) WHERE is_active = TRUE;

-- RLS
ALTER TABLE ai_provider_configs ENABLE ROW LEVEL SECURITY;

CREATE POLICY ai_provider_configs_select_own ON ai_provider_configs
    FOR SELECT
    USING (
        user_id = current_setting('app.current_user_id')::UUID OR
        organization_id IN (
            SELECT organization_id FROM users WHERE user_id = current_setting('app.current_user_id')::UUID
        )
    );

-- ============================================================================
-- SPEECH PROCESSING TABLES
-- ============================================================================

-- Transcriptions (STT)
CREATE TABLE IF NOT EXISTS transcriptions (
    transcription_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    call_id VARCHAR(255), -- Link to WebRTC call
    
    -- Audio source
    audio_url TEXT,
    audio_duration_seconds DECIMAL(10,2),
    
    -- Transcription
    text TEXT NOT NULL,
    language VARCHAR(10) NOT NULL,
    confidence DECIMAL(4,3),
    
    -- Provider
    provider VARCHAR(50) NOT NULL DEFAULT 'whisper',
    model VARCHAR(100),
    
    -- Processing
    processing_time_ms INT,
    word_count INT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    segments JSONB, -- Word-level timestamps
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_transcriptions_user_id ON transcriptions(user_id);
CREATE INDEX idx_transcriptions_call_id ON transcriptions(call_id);
CREATE INDEX idx_transcriptions_language ON transcriptions(language);
CREATE INDEX idx_transcriptions_created_at ON transcriptions(created_at DESC);
CREATE INDEX idx_transcriptions_text_search ON transcriptions USING gin(to_tsvector('english', text));

-- RLS
ALTER TABLE transcriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY transcriptions_select_own ON transcriptions
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- TTS Generations
CREATE TABLE IF NOT EXISTS tts_generations (
    generation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    agent_id UUID REFERENCES ai_agents(agent_id) ON DELETE SET NULL,
    
    -- Input
    text TEXT NOT NULL,
    text_length INT NOT NULL,
    
    -- Voice
    provider VARCHAR(50) NOT NULL DEFAULT 'elevenlabs',
    voice_id VARCHAR(100),
    voice_settings JSONB DEFAULT '{}',
    
    -- Output
    audio_url TEXT,
    audio_duration_seconds DECIMAL(10,2),
    
    -- Processing
    processing_time_ms INT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tts_generations_user_id ON tts_generations(user_id);
CREATE INDEX idx_tts_generations_agent_id ON tts_generations(agent_id);
CREATE INDEX idx_tts_generations_created_at ON tts_generations(created_at DESC);

-- RLS
ALTER TABLE tts_generations ENABLE ROW LEVEL SECURITY;

CREATE POLICY tts_generations_select_own ON tts_generations
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- ============================================================================
-- TRANSLATION TABLES
-- ============================================================================
CREATE TABLE IF NOT EXISTS translations (
    translation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    call_id VARCHAR(255), -- Link to WebRTC call
    
    -- Source
    source_text TEXT NOT NULL,
    source_language VARCHAR(10) NOT NULL,
    
    -- Target
    translated_text TEXT NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    
    -- Quality
    confidence DECIMAL(4,3),
    
    -- Provider
    provider VARCHAR(50) NOT NULL DEFAULT 'openai',
    model VARCHAR(100),
    
    -- Processing
    processing_time_ms INT,
    
    -- Context
    context TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_translations_user_id ON translations(user_id);
CREATE INDEX idx_translations_call_id ON translations(call_id);
CREATE INDEX idx_translations_languages ON translations(source_language, target_language);
CREATE INDEX idx_translations_created_at ON translations(created_at DESC);

-- RLS
ALTER TABLE translations ENABLE ROW LEVEL SECURITY;

CREATE POLICY translations_select_own ON translations
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- ============================================================================
-- WORKFLOW EXECUTIONS (Temporal Integration)
-- ============================================================================
CREATE TABLE IF NOT EXISTS workflow_executions (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Temporal workflow ID
    workflow_id VARCHAR(255) NOT NULL,
    workflow_type VARCHAR(100) NOT NULL, -- 'ai_summarization', 'translation_pipeline', etc.
    run_id VARCHAR(255),
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'running', -- 'running', 'completed', 'failed', 'cancelled'
    
    -- Input/Output
    input JSONB,
    output JSONB,
    error_message TEXT,
    
    -- Timing
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INT,
    
    -- Retry
    attempt_count INT DEFAULT 1,
    max_attempts INT DEFAULT 3,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    CONSTRAINT workflow_executions_status_check CHECK (
        status IN ('running', 'completed', 'failed', 'cancelled', 'timeout')
    )
);

CREATE INDEX idx_workflow_executions_user_id ON workflow_executions(user_id);
CREATE INDEX idx_workflow_executions_workflow_id ON workflow_executions(workflow_id);
CREATE INDEX idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX idx_workflow_executions_type ON workflow_executions(workflow_type);
CREATE INDEX idx_workflow_executions_started_at ON workflow_executions(started_at DESC);

-- RLS
ALTER TABLE workflow_executions ENABLE ROW LEVEL SECURITY;

CREATE POLICY workflow_executions_select_own ON workflow_executions
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- ============================================================================
-- AI USAGE TRACKING
-- ============================================================================
CREATE TABLE IF NOT EXISTS ai_usage_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(organization_id) ON DELETE SET NULL,
    
    -- Service details
    service_type VARCHAR(50) NOT NULL, -- 'llm', 'tts', 'stt', 'translation', 'memory'
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100),
    
    -- Usage
    tokens_used INT,
    input_tokens INT,
    output_tokens INT,
    characters_processed INT,
    audio_seconds DECIMAL(10,2),
    
    -- Cost
    estimated_cost_usd DECIMAL(10,6),
    
    -- Context
    agent_id UUID REFERENCES ai_agents(agent_id) ON DELETE SET NULL,
    call_id VARCHAR(255),
    
    -- Performance
    latency_ms INT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT ai_usage_logs_service_type_check CHECK (
        service_type IN ('llm', 'tts', 'stt', 'translation', 'memory', 'moderation', 'embeddings')
    )
);

CREATE INDEX idx_ai_usage_logs_user_id ON ai_usage_logs(user_id);
CREATE INDEX idx_ai_usage_logs_org_id ON ai_usage_logs(organization_id);
CREATE INDEX idx_ai_usage_logs_service ON ai_usage_logs(service_type, provider);
CREATE INDEX idx_ai_usage_logs_created_at ON ai_usage_logs(created_at DESC);
CREATE INDEX idx_ai_usage_logs_call_id ON ai_usage_logs(call_id) WHERE call_id IS NOT NULL;

-- Partitioning for performance (optional, for high volume)
-- Partition by month for efficient querying

-- ============================================================================
-- MATERIALIZED VIEWS FOR ANALYTICS
-- ============================================================================

-- Daily AI usage summary
CREATE MATERIALIZED VIEW ai_usage_daily_summary AS
SELECT 
    user_id,
    organization_id,
    service_type,
    provider,
    DATE(created_at) as usage_date,
    COUNT(*) as request_count,
    SUM(tokens_used) as total_tokens,
    SUM(estimated_cost_usd) as total_cost_usd,
    AVG(latency_ms) as avg_latency_ms,
    MAX(created_at) as last_updated
FROM ai_usage_logs
GROUP BY user_id, organization_id, service_type, provider, DATE(created_at);

CREATE UNIQUE INDEX idx_ai_usage_daily_summary_unique ON ai_usage_daily_summary(
    user_id, COALESCE(organization_id, '00000000-0000-0000-0000-000000000000'::UUID), 
    service_type, provider, usage_date
);

-- Memory statistics
CREATE MATERIALIZED VIEW memory_stats_summary AS
SELECT 
    user_id,
    agent_id,
    COUNT(*) as total_chunks,
    COUNT(DISTINCT source_type) as source_types_count,
    AVG(LENGTH(content)) as avg_chunk_length,
    COUNT(*) FILTER (WHERE expires_at IS NULL OR expires_at > NOW()) as active_chunks,
    MAX(created_at) as last_memory_created,
    MAX(accessed_at) as last_memory_accessed
FROM memory_chunks
GROUP BY user_id, agent_id;

CREATE UNIQUE INDEX idx_memory_stats_summary_unique ON memory_stats_summary(
    user_id, COALESCE(agent_id, '00000000-0000-0000-0000-000000000000'::UUID)
);

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to update accessed_at timestamp
CREATE OR REPLACE FUNCTION update_memory_accessed_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.accessed_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for memory access tracking
CREATE TRIGGER trigger_memory_accessed
    BEFORE UPDATE ON memory_chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_memory_accessed_at();

-- Function to auto-expire old memories
CREATE OR REPLACE FUNCTION cleanup_expired_memories()
RETURNS INT AS $$
DECLARE
    deleted_count INT;
BEGIN
    DELETE FROM memory_chunks
    WHERE expires_at IS NOT NULL AND expires_at < NOW();
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate memory relationships automatically
CREATE OR REPLACE FUNCTION calculate_memory_similarity(
    chunk1_id UUID,
    chunk2_id UUID
) RETURNS DECIMAL AS $$
DECLARE
    similarity_score DECIMAL;
BEGIN
    -- Placeholder: In real implementation, this would use vector similarity
    -- For now, return a simple score based on common words
    SELECT 
        CASE 
            WHEN COUNT(*) > 0 THEN LEAST(COUNT(*) / 10.0, 1.0)
            ELSE 0
        END INTO similarity_score
    FROM (
        SELECT unnest(string_to_array(lower(content), ' ')) as word
        FROM memory_chunks WHERE chunk_id = chunk1_id
        INTERSECT
        SELECT unnest(string_to_array(lower(content), ' ')) as word
        FROM memory_chunks WHERE chunk_id = chunk2_id
    ) common_words;
    
    RETURN COALESCE(similarity_score, 0);
END;
$$ LANGUAGE plpgsql;

-- Function to refresh materialized views (call periodically)
CREATE OR REPLACE FUNCTION refresh_ai_analytics()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY ai_usage_daily_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY memory_stats_summary;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE ai_agents IS 'AI agents created by users for various tasks';
COMMENT ON TABLE memory_chunks IS 'Vector storage for AI memory chunks (SuperMemory.ai architecture)';
COMMENT ON TABLE memory_relationships IS 'Graph relationships between memory chunks';
COMMENT ON TABLE ai_provider_configs IS 'BYOK configurations for AI providers';
COMMENT ON TABLE transcriptions IS 'Speech-to-text transcriptions';
COMMENT ON TABLE tts_generations IS 'Text-to-speech audio generations';
COMMENT ON TABLE translations IS 'Text translations between languages';
COMMENT ON TABLE workflow_executions IS 'Temporal workflow execution tracking';
COMMENT ON TABLE ai_usage_logs IS 'AI service usage tracking and billing';

-- ============================================================================
-- PHASE 4 SCHEMA COMPLETE
-- ============================================================================

-- Migration metadata
INSERT INTO schema_migrations (version, description, applied_at) 
VALUES ('004', 'Phase 4: AI Core & Memory System', NOW())
ON CONFLICT (version) DO NOTHING;
