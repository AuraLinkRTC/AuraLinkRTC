-- ============================================================================
-- Phase 5: MCP Integration & AI Agents Schema
-- AuraLinkRTC Database Migration
-- ============================================================================
-- Description: Database schema for Phase 5 features including:
--   - MCP server configurations and connections
--   - Advanced agent workflows with LangGraph/CrewAI/AutoGen
--   - Multi-LLM selection and performance tracking
--   - Prefect workflow orchestration metadata
--   - Agent team configurations
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- MCP SERVER CONFIGURATIONS
-- ============================================================================

-- MCP Server Registry
CREATE TABLE IF NOT EXISTS mcp_servers (
    server_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    server_type VARCHAR(50) NOT NULL, -- 'deepwiki', 'memory', 'sequential-thinking', 'supabase', 'custom'
    description TEXT,
    endpoint_url TEXT,
    version VARCHAR(20),
    is_enabled BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}',
    capabilities JSONB DEFAULT '[]', -- List of capabilities this server provides
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mcp_servers_type ON mcp_servers(server_type);
CREATE INDEX idx_mcp_servers_enabled ON mcp_servers(is_enabled);

-- User MCP Connections
CREATE TABLE IF NOT EXISTS user_mcp_connections (
    connection_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    server_id UUID NOT NULL REFERENCES mcp_servers(server_id) ON DELETE CASCADE,
    connection_name VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    credentials JSONB DEFAULT '{}', -- Encrypted API keys, tokens
    connection_config JSONB DEFAULT '{}', -- User-specific configuration
    last_used_at TIMESTAMPTZ,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, server_id)
);

CREATE INDEX idx_user_mcp_user ON user_mcp_connections(user_id);
CREATE INDEX idx_user_mcp_server ON user_mcp_connections(server_id);
CREATE INDEX idx_user_mcp_active ON user_mcp_connections(is_active);

-- Enable RLS for user_mcp_connections
ALTER TABLE user_mcp_connections ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_mcp_connections_policy ON user_mcp_connections
    FOR ALL
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- MCP Operation Logs
CREATE TABLE IF NOT EXISTS mcp_operation_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES user_mcp_connections(connection_id) ON DELETE CASCADE,
    operation_type VARCHAR(100) NOT NULL, -- 'query', 'write', 'search', 'reasoning'
    operation_name VARCHAR(255),
    input_data JSONB,
    output_data JSONB,
    latency_ms INTEGER,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    tokens_used INTEGER,
    cost_usd DECIMAL(10, 6),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mcp_logs_connection ON mcp_operation_logs(connection_id);
CREATE INDEX idx_mcp_logs_created ON mcp_operation_logs(created_at DESC);
CREATE INDEX idx_mcp_logs_success ON mcp_operation_logs(success);

-- ============================================================================
-- ADVANCED AGENT WORKFLOWS
-- ============================================================================

-- Agent Workflow Definitions
CREATE TABLE IF NOT EXISTS agent_workflows (
    workflow_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES ai_agents(agent_id) ON DELETE CASCADE,
    workflow_name VARCHAR(255) NOT NULL,
    workflow_type VARCHAR(50) NOT NULL, -- 'auto_join', 'summarization', 'moderation', 'qa', 'custom'
    description TEXT,
    trigger_conditions JSONB DEFAULT '[]', -- Conditions that trigger this workflow
    workflow_steps JSONB NOT NULL, -- LangGraph state machine definition
    mcp_integrations JSONB DEFAULT '[]', -- MCP servers used in this workflow
    priority INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_workflows_agent ON agent_workflows(agent_id);
CREATE INDEX idx_agent_workflows_type ON agent_workflows(workflow_type);
CREATE INDEX idx_agent_workflows_active ON agent_workflows(is_active);

-- Workflow Executions
CREATE TABLE IF NOT EXISTS workflow_executions (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id UUID NOT NULL REFERENCES agent_workflows(workflow_id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES ai_agents(agent_id) ON DELETE CASCADE,
    room_id VARCHAR(255),
    call_id UUID,
    execution_status VARCHAR(50) DEFAULT 'running', -- 'running', 'completed', 'failed', 'paused'
    current_step VARCHAR(255),
    state_data JSONB DEFAULT '{}', -- Current state of the workflow
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10, 6) DEFAULT 0
);

CREATE INDEX idx_workflow_exec_workflow ON workflow_executions(workflow_id);
CREATE INDEX idx_workflow_exec_agent ON workflow_executions(agent_id);
CREATE INDEX idx_workflow_exec_status ON workflow_executions(execution_status);
CREATE INDEX idx_workflow_exec_started ON workflow_executions(started_at DESC);

-- ============================================================================
-- MULTI-AGENT COLLABORATION (CrewAI & AutoGen)
-- ============================================================================

-- Agent Teams
CREATE TABLE IF NOT EXISTS agent_teams (
    team_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    team_name VARCHAR(255) NOT NULL,
    description TEXT,
    team_type VARCHAR(50) DEFAULT 'crewai', -- 'crewai', 'autogen', 'custom'
    collaboration_mode VARCHAR(50) DEFAULT 'sequential', -- 'sequential', 'hierarchical', 'consensus'
    config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_teams_user ON agent_teams(user_id);
CREATE INDEX idx_agent_teams_type ON agent_teams(team_type);

-- Enable RLS for agent_teams
ALTER TABLE agent_teams ENABLE ROW LEVEL SECURITY;

CREATE POLICY agent_teams_policy ON agent_teams
    FOR ALL
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- Team Members
CREATE TABLE IF NOT EXISTS team_members (
    member_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES agent_teams(team_id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES ai_agents(agent_id) ON DELETE CASCADE,
    role VARCHAR(100) NOT NULL, -- 'researcher', 'writer', 'reviewer', 'coordinator', etc.
    role_description TEXT,
    execution_order INTEGER DEFAULT 0,
    can_delegate BOOLEAN DEFAULT false,
    tools JSONB DEFAULT '[]', -- Tools available to this agent
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(team_id, agent_id)
);

CREATE INDEX idx_team_members_team ON team_members(team_id);
CREATE INDEX idx_team_members_agent ON team_members(agent_id);

-- Team Conversations
CREATE TABLE IF NOT EXISTS team_conversations (
    conversation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES agent_teams(team_id) ON DELETE CASCADE,
    room_id VARCHAR(255),
    call_id UUID,
    task_description TEXT NOT NULL,
    conversation_status VARCHAR(50) DEFAULT 'active', -- 'active', 'completed', 'failed'
    conversation_log JSONB DEFAULT '[]', -- Full conversation history
    result_data JSONB,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    total_messages INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd DECIMAL(10, 6) DEFAULT 0
);

CREATE INDEX idx_team_conv_team ON team_conversations(team_id);
CREATE INDEX idx_team_conv_status ON team_conversations(conversation_status);
CREATE INDEX idx_team_conv_started ON team_conversations(started_at DESC);

-- ============================================================================
-- MULTIPLE LLM SELECTION & PERFORMANCE
-- ============================================================================

-- LLM Provider Registry
CREATE TABLE IF NOT EXISTS llm_providers (
    provider_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider_name VARCHAR(100) NOT NULL UNIQUE,
    provider_type VARCHAR(50) NOT NULL, -- 'openai', 'anthropic', 'google', 'meta', 'custom'
    api_endpoint TEXT,
    is_enabled BOOLEAN DEFAULT true,
    supports_streaming BOOLEAN DEFAULT true,
    supports_function_calling BOOLEAN DEFAULT false,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- LLM Models
CREATE TABLE IF NOT EXISTS llm_models (
    model_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider_id UUID NOT NULL REFERENCES llm_providers(provider_id) ON DELETE CASCADE,
    model_name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    model_type VARCHAR(50), -- 'chat', 'completion', 'embedding'
    context_window INTEGER,
    max_tokens INTEGER,
    cost_per_1k_input_tokens DECIMAL(10, 6),
    cost_per_1k_output_tokens DECIMAL(10, 6),
    is_available BOOLEAN DEFAULT true,
    capabilities JSONB DEFAULT '[]',
    performance_tier VARCHAR(20) DEFAULT 'standard', -- 'fast', 'standard', 'advanced'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(provider_id, model_name)
);

CREATE INDEX idx_llm_models_provider ON llm_models(provider_id);
CREATE INDEX idx_llm_models_available ON llm_models(is_available);
CREATE INDEX idx_llm_models_tier ON llm_models(performance_tier);

-- User LLM Preferences
CREATE TABLE IF NOT EXISTS user_llm_preferences (
    preference_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    model_id UUID NOT NULL REFERENCES llm_models(model_id) ON DELETE CASCADE,
    is_default BOOLEAN DEFAULT false,
    priority INTEGER DEFAULT 0,
    custom_api_key TEXT, -- Encrypted BYOK
    usage_limit_tokens INTEGER,
    cost_limit_usd DECIMAL(10, 2),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_user_llm_pref_user ON user_llm_preferences(user_id);
CREATE INDEX idx_user_llm_pref_model ON user_llm_preferences(model_id);
CREATE INDEX idx_user_llm_pref_default ON user_llm_preferences(is_default);

-- Enable RLS for user_llm_preferences
ALTER TABLE user_llm_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_llm_preferences_policy ON user_llm_preferences
    FOR ALL
    USING (user_id = current_setting('app.current_user_id')::UUID);

-- LLM Performance Metrics
CREATE TABLE IF NOT EXISTS llm_performance_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_id UUID NOT NULL REFERENCES llm_models(model_id) ON DELETE CASCADE,
    user_id UUID,
    request_type VARCHAR(50), -- 'chat', 'completion', 'function_call'
    latency_ms INTEGER NOT NULL,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    cost_usd DECIMAL(10, 6),
    success BOOLEAN DEFAULT true,
    error_type VARCHAR(100),
    quality_score DECIMAL(3, 2), -- 0.00 - 1.00
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_llm_perf_model ON llm_performance_metrics(model_id);
CREATE INDEX idx_llm_perf_user ON llm_performance_metrics(user_id);
CREATE INDEX idx_llm_perf_created ON llm_performance_metrics(created_at DESC);

-- ============================================================================
-- PREFECT WORKFLOW ORCHESTRATION
-- ============================================================================

-- Prefect Flow Definitions
CREATE TABLE IF NOT EXISTS prefect_flows (
    flow_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    flow_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    flow_type VARCHAR(50), -- 'mcp_processing', 'agent_coordination', 'data_pipeline'
    flow_definition JSONB NOT NULL, -- Prefect flow configuration
    parameters JSONB DEFAULT '{}',
    tags JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_prefect_flows_type ON prefect_flows(flow_type);
CREATE INDEX idx_prefect_flows_active ON prefect_flows(is_active);

-- Prefect Flow Runs
CREATE TABLE IF NOT EXISTS prefect_flow_runs (
    run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    flow_id UUID NOT NULL REFERENCES prefect_flows(flow_id) ON DELETE CASCADE,
    user_id UUID,
    agent_id UUID REFERENCES ai_agents(agent_id) ON DELETE SET NULL,
    run_status VARCHAR(50) DEFAULT 'scheduled', -- 'scheduled', 'running', 'completed', 'failed', 'cancelled'
    input_parameters JSONB,
    output_data JSONB,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER
);

CREATE INDEX idx_prefect_runs_flow ON prefect_flow_runs(flow_id);
CREATE INDEX idx_prefect_runs_status ON prefect_flow_runs(run_status);
CREATE INDEX idx_prefect_runs_user ON prefect_flow_runs(user_id);
CREATE INDEX idx_prefect_runs_started ON prefect_flow_runs(started_at DESC);

-- ============================================================================
-- AGENT INTERACTION LOGS (Enhanced for Phase 5)
-- ============================================================================

-- Agent Interactions with MCP Context
CREATE TABLE IF NOT EXISTS agent_mcp_interactions (
    interaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES ai_agents(agent_id) ON DELETE CASCADE,
    connection_id UUID REFERENCES user_mcp_connections(connection_id) ON DELETE SET NULL,
    interaction_type VARCHAR(100) NOT NULL, -- 'query_docs', 'recall_memory', 'reasoning_step', 'db_query'
    input_context JSONB,
    mcp_response JSONB,
    agent_output TEXT,
    latency_ms INTEGER,
    tokens_used INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_mcp_int_agent ON agent_mcp_interactions(agent_id);
CREATE INDEX idx_agent_mcp_int_connection ON agent_mcp_interactions(connection_id);
CREATE INDEX idx_agent_mcp_int_created ON agent_mcp_interactions(created_at DESC);

-- ============================================================================
-- MATERIALIZED VIEWS FOR ANALYTICS
-- ============================================================================

-- Agent Performance Summary
CREATE MATERIALIZED VIEW agent_performance_summary AS
SELECT 
    a.agent_id,
    a.name AS agent_name,
    COUNT(DISTINCT we.execution_id) AS total_executions,
    AVG(we.duration_ms) AS avg_duration_ms,
    SUM(we.total_tokens) AS total_tokens_used,
    SUM(we.total_cost_usd) AS total_cost_usd,
    COUNT(CASE WHEN we.execution_status = 'completed' THEN 1 END) AS successful_executions,
    COUNT(CASE WHEN we.execution_status = 'failed' THEN 1 END) AS failed_executions
FROM ai_agents a
LEFT JOIN workflow_executions we ON a.agent_id = we.agent_id
GROUP BY a.agent_id, a.name;

CREATE UNIQUE INDEX idx_agent_perf_summary_agent ON agent_performance_summary(agent_id);

-- MCP Usage Summary
CREATE MATERIALIZED VIEW mcp_usage_summary AS
SELECT 
    ms.server_id,
    ms.name AS server_name,
    ms.server_type,
    COUNT(DISTINCT umc.connection_id) AS total_connections,
    COUNT(DISTINCT umc.user_id) AS unique_users,
    SUM(umc.usage_count) AS total_operations,
    AVG(mol.latency_ms) AS avg_latency_ms,
    SUM(mol.tokens_used) AS total_tokens,
    SUM(mol.cost_usd) AS total_cost_usd
FROM mcp_servers ms
LEFT JOIN user_mcp_connections umc ON ms.server_id = umc.server_id
LEFT JOIN mcp_operation_logs mol ON umc.connection_id = mol.connection_id
GROUP BY ms.server_id, ms.name, ms.server_type;

CREATE UNIQUE INDEX idx_mcp_usage_summary_server ON mcp_usage_summary(server_id);

-- LLM Comparison View
CREATE MATERIALIZED VIEW llm_comparison_view AS
SELECT 
    lm.model_id,
    lm.model_name,
    lm.display_name,
    lp.provider_name,
    AVG(lpm.latency_ms) AS avg_latency_ms,
    AVG(lpm.quality_score) AS avg_quality_score,
    AVG(lpm.cost_usd) AS avg_cost_per_request,
    COUNT(lpm.metric_id) AS total_requests,
    COUNT(CASE WHEN lpm.success = true THEN 1 END) AS successful_requests,
    (COUNT(CASE WHEN lpm.success = true THEN 1 END)::FLOAT / NULLIF(COUNT(lpm.metric_id), 0)) AS success_rate
FROM llm_models lm
JOIN llm_providers lp ON lm.provider_id = lp.provider_id
LEFT JOIN llm_performance_metrics lpm ON lm.model_id = lpm.model_id
WHERE lpm.created_at > NOW() - INTERVAL '30 days'
GROUP BY lm.model_id, lm.model_name, lm.display_name, lp.provider_name;

CREATE UNIQUE INDEX idx_llm_comparison_model ON llm_comparison_view(model_id);

-- ============================================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================================

-- Update MCP connection usage
CREATE OR REPLACE FUNCTION update_mcp_usage()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE user_mcp_connections
    SET 
        usage_count = usage_count + 1,
        last_used_at = NOW(),
        updated_at = NOW()
    WHERE connection_id = NEW.connection_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_mcp_usage
AFTER INSERT ON mcp_operation_logs
FOR EACH ROW
EXECUTE FUNCTION update_mcp_usage();

-- Update workflow execution duration
CREATE OR REPLACE FUNCTION update_workflow_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.execution_status IN ('completed', 'failed') AND NEW.completed_at IS NOT NULL THEN
        NEW.duration_ms = EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_workflow_duration
BEFORE UPDATE ON workflow_executions
FOR EACH ROW
EXECUTE FUNCTION update_workflow_duration();

-- Refresh materialized views function
CREATE OR REPLACE FUNCTION refresh_phase5_analytics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY agent_performance_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mcp_usage_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY llm_comparison_view;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SEED DATA FOR PHASE 5
-- ============================================================================

-- Insert default MCP servers
INSERT INTO mcp_servers (name, server_type, description, endpoint_url, capabilities) VALUES
('DeepWiki', 'deepwiki', 'Real-time GitHub repository and documentation access', 'mcp://deepwiki', '["read_wiki", "search_docs", "ask_question"]'),
('Memory Graph', 'memory', 'Graph-based knowledge management and recall', 'mcp://memory', '["create_entities", "create_relations", "search_nodes", "read_graph"]'),
('Sequential Thinking', 'sequential-thinking', 'Step-by-step reasoning for complex problem-solving', 'mcp://sequential-thinking', '["think_sequentially", "revise_thought", "branch_reasoning"]'),
('Supabase Database', 'supabase', 'Live database queries and operations', 'mcp://supabase', '["execute_sql", "list_tables", "search_docs"]')
ON CONFLICT (name) DO NOTHING;

-- Insert default LLM providers
INSERT INTO llm_providers (provider_name, provider_type, api_endpoint, supports_streaming, supports_function_calling) VALUES
('OpenAI', 'openai', 'https://api.openai.com/v1', true, true),
('Anthropic', 'anthropic', 'https://api.anthropic.com/v1', true, true),
('Google', 'google', 'https://generativelanguage.googleapis.com/v1', true, false),
('Meta', 'meta', 'https://api.together.xyz/v1', true, false)
ON CONFLICT (provider_name) DO NOTHING;

-- Insert default LLM models
WITH provider_ids AS (
    SELECT provider_id, provider_name FROM llm_providers
)
INSERT INTO llm_models (provider_id, model_name, display_name, model_type, context_window, max_tokens, cost_per_1k_input_tokens, cost_per_1k_output_tokens, performance_tier, capabilities) 
SELECT 
    p.provider_id,
    m.model_name,
    m.display_name,
    m.model_type,
    m.context_window,
    m.max_tokens,
    m.cost_input,
    m.cost_output,
    m.tier,
    m.capabilities
FROM provider_ids p
CROSS JOIN (VALUES
    ('gpt-4-turbo-preview', 'GPT-4 Turbo', 'chat', 128000, 4096, 0.01, 0.03, 'advanced', '["function_calling", "json_mode", "vision"]'),
    ('gpt-4', 'GPT-4', 'chat', 8192, 4096, 0.03, 0.06, 'advanced', '["function_calling", "json_mode"]'),
    ('gpt-3.5-turbo', 'GPT-3.5 Turbo', 'chat', 16385, 4096, 0.0005, 0.0015, 'fast', '["function_calling", "json_mode"]'),
    ('claude-3-opus-20240229', 'Claude 3 Opus', 'chat', 200000, 4096, 0.015, 0.075, 'advanced', '["function_calling", "vision"]'),
    ('claude-3-sonnet-20240229', 'Claude 3 Sonnet', 'chat', 200000, 4096, 0.003, 0.015, 'standard', '["function_calling", "vision"]'),
    ('claude-3-haiku-20240307', 'Claude 3 Haiku', 'chat', 200000, 4096, 0.00025, 0.00125, 'fast', '["function_calling"]'),
    ('gemini-1.5-pro', 'Gemini 1.5 Pro', 'chat', 1000000, 8192, 0.0035, 0.0105, 'advanced', '["multimodal", "long_context"]'),
    ('llama-3-70b', 'Llama 3 70B', 'chat', 8192, 4096, 0.0007, 0.0009, 'standard', '["open_source"]')
) AS m(model_name, display_name, model_type, context_window, max_tokens, cost_input, cost_output, tier, capabilities)
WHERE 
    (p.provider_name = 'OpenAI' AND m.model_name LIKE 'gpt%')
    OR (p.provider_name = 'Anthropic' AND m.model_name LIKE 'claude%')
    OR (p.provider_name = 'Google' AND m.model_name LIKE 'gemini%')
    OR (p.provider_name = 'Meta' AND m.model_name LIKE 'llama%')
ON CONFLICT (provider_id, model_name) DO NOTHING;

-- ============================================================================
-- GRANTS & PERMISSIONS
-- ============================================================================

-- Grant appropriate permissions (adjust based on your auth setup)
GRANT SELECT ON mcp_servers TO authenticated;
GRANT ALL ON user_mcp_connections TO authenticated;
GRANT INSERT ON mcp_operation_logs TO authenticated;
GRANT ALL ON agent_workflows TO authenticated;
GRANT ALL ON workflow_executions TO authenticated;
GRANT ALL ON agent_teams TO authenticated;
GRANT ALL ON team_members TO authenticated;
GRANT ALL ON team_conversations TO authenticated;
GRANT SELECT ON llm_providers TO authenticated;
GRANT SELECT ON llm_models TO authenticated;
GRANT ALL ON user_llm_preferences TO authenticated;
GRANT INSERT ON llm_performance_metrics TO authenticated;
GRANT SELECT ON prefect_flows TO authenticated;
GRANT ALL ON prefect_flow_runs TO authenticated;
GRANT INSERT ON agent_mcp_interactions TO authenticated;

-- Grant access to materialized views
GRANT SELECT ON agent_performance_summary TO authenticated;
GRANT SELECT ON mcp_usage_summary TO authenticated;
GRANT SELECT ON llm_comparison_view TO authenticated;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE mcp_servers IS 'Registry of available Model Context Protocol servers';
COMMENT ON TABLE user_mcp_connections IS 'User connections to MCP servers with BYOK support';
COMMENT ON TABLE agent_workflows IS 'LangGraph-based agent workflow definitions';
COMMENT ON TABLE agent_teams IS 'CrewAI and AutoGen team configurations';
COMMENT ON TABLE llm_models IS 'Available LLM models with pricing and capabilities';
COMMENT ON TABLE prefect_flows IS 'Prefect workflow orchestration definitions';

-- ============================================================================
-- END OF PHASE 5 SCHEMA
-- ============================================================================
