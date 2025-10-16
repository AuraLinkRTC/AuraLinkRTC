-- AuraLink Database Schema - Phase 7: Enterprise Features & Finalization
-- Migration: 007_phase7_enterprise_schema
-- Description: Enterprise security, compliance, analytics, and administration tables
-- Author: AuraLink Engineering
-- Date: 2025-10-16
-- Phase: 7 - Enterprise Features & Finalization

-- ============================================================================
-- SECTION 1: ENTERPRISE SECURITY & COMPLIANCE
-- ============================================================================

-- SSO Configurations Table (SAML/OAuth)
CREATE TABLE IF NOT EXISTS sso_configs (
    config_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    
    -- SSO Provider
    provider_type VARCHAR(20) NOT NULL,
    provider_name VARCHAR(100) NOT NULL,
    
    -- Configuration
    config_data JSONB NOT NULL,
    
    -- SAML Specific
    saml_entity_id TEXT,
    saml_sso_url TEXT,
    saml_certificate TEXT,
    
    -- OAuth/OIDC Specific
    client_id VARCHAR(255),
    client_secret_encrypted TEXT,
    authorization_endpoint TEXT,
    token_endpoint TEXT,
    userinfo_endpoint TEXT,
    
    -- Settings
    is_active BOOLEAN DEFAULT TRUE,
    auto_provision_users BOOLEAN DEFAULT TRUE,
    default_role VARCHAR(20) DEFAULT 'user',
    
    -- Attributes Mapping
    attribute_mapping JSONB DEFAULT '{}',
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    
    CONSTRAINT sso_provider_type_check CHECK (provider_type IN ('saml', 'oauth', 'oidc'))
);

CREATE INDEX idx_sso_configs_organization_id ON sso_configs(organization_id);
CREATE INDEX idx_sso_configs_provider_type ON sso_configs(provider_type);
CREATE INDEX idx_sso_configs_is_active ON sso_configs(is_active);

-- Audit Logs Table (Comprehensive activity tracking)
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(organization_id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    
    -- Action Details
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    
    -- Context
    description TEXT,
    severity VARCHAR(20) DEFAULT 'info',
    
    -- Request Details
    ip_address VARCHAR(45),
    user_agent TEXT,
    request_method VARCHAR(10),
    request_path TEXT,
    request_body JSONB,
    response_status INT,
    
    -- Changes (for UPDATE operations)
    old_values JSONB,
    new_values JSONB,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT audit_severity_check CHECK (severity IN ('info', 'warning', 'error', 'critical'))
);

CREATE INDEX idx_audit_logs_organization_id ON audit_logs(organization_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_resource_type ON audit_logs(resource_type);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_logs_severity ON audit_logs(severity);
CREATE INDEX idx_audit_logs_search ON audit_logs USING gin(to_tsvector('english', description));

-- RLS for audit logs
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_logs_org_admin ON audit_logs
    FOR SELECT
    USING (
        organization_id IN (
            SELECT o.organization_id FROM organizations o
            JOIN users u ON o.owner_id = u.user_id
            WHERE u.user_id = current_setting('app.current_user_id')::UUID
            OR u.role = 'admin'
        )
    );

-- Data Retention Policies Table
CREATE TABLE IF NOT EXISTS data_retention_policies (
    policy_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    
    -- Policy Configuration
    policy_name VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    
    -- Retention Period
    retention_days INT NOT NULL DEFAULT 90,
    auto_delete BOOLEAN DEFAULT FALSE,
    archive_before_delete BOOLEAN DEFAULT TRUE,
    archive_location TEXT,
    
    -- Compliance
    compliance_standard VARCHAR(50),
    legal_hold BOOLEAN DEFAULT FALSE,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_executed_at TIMESTAMPTZ,
    next_execution_at TIMESTAMPTZ,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_retention_policies_organization_id ON data_retention_policies(organization_id);
CREATE INDEX idx_retention_policies_resource_type ON data_retention_policies(resource_type);
CREATE INDEX idx_retention_policies_next_execution ON data_retention_policies(next_execution_at);

-- GDPR/HIPAA Compliance Table
CREATE TABLE IF NOT EXISTS compliance_requests (
    request_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(organization_id) ON DELETE SET NULL,
    
    -- Request Type
    request_type VARCHAR(50) NOT NULL,
    compliance_standard VARCHAR(50),
    
    -- Status
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    
    -- Data Export (for GDPR Article 20)
    export_url TEXT,
    export_format VARCHAR(20),
    export_expires_at TIMESTAMPTZ,
    
    -- Data Deletion (for GDPR Article 17)
    deletion_scope TEXT[],
    deletion_completed_at TIMESTAMPTZ,
    
    -- Processing Details
    processed_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    processing_notes TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    requested_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    
    CONSTRAINT compliance_request_type_check CHECK (
        request_type IN ('data_export', 'data_deletion', 'data_access', 'consent_update', 'rectification')
    ),
    CONSTRAINT compliance_status_check CHECK (
        status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')
    )
);

CREATE INDEX idx_compliance_requests_user_id ON compliance_requests(user_id);
CREATE INDEX idx_compliance_requests_status ON compliance_requests(status);
CREATE INDEX idx_compliance_requests_created_at ON compliance_requests(requested_at DESC);

-- Security Events Table
CREATE TABLE IF NOT EXISTS security_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(organization_id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    
    -- Event Details
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'medium',
    
    -- Context
    description TEXT NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    
    -- Detection
    detection_method VARCHAR(50),
    risk_score INT,
    
    -- Response
    action_taken VARCHAR(100),
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    resolution_notes TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamp
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT security_event_severity_check CHECK (severity IN ('low', 'medium', 'high', 'critical'))
);

CREATE INDEX idx_security_events_organization_id ON security_events(organization_id);
CREATE INDEX idx_security_events_user_id ON security_events(user_id);
CREATE INDEX idx_security_events_severity ON security_events(severity);
CREATE INDEX idx_security_events_resolved ON security_events(resolved);
CREATE INDEX idx_security_events_detected_at ON security_events(detected_at DESC);

-- ============================================================================
-- SECTION 2: ADVANCED ANALYTICS
-- ============================================================================

-- AI Usage Analytics Table (Extended from Phase 4)
CREATE TABLE IF NOT EXISTS ai_usage_analytics (
    usage_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(organization_id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    
    -- AI Feature
    feature_type VARCHAR(50) NOT NULL,
    provider VARCHAR(50),
    model VARCHAR(100),
    
    -- Usage Metrics
    tokens_used INT,
    audio_seconds INT,
    characters_processed INT,
    api_calls INT DEFAULT 1,
    
    -- Cost
    cost_usd DECIMAL(10,6),
    
    -- Performance
    latency_ms INT,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    
    -- Context
    call_id VARCHAR(50) REFERENCES calls(call_id) ON DELETE SET NULL,
    agent_id VARCHAR(100),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamp
    used_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ai_usage_analytics_organization_id ON ai_usage_analytics(organization_id);
CREATE INDEX idx_ai_usage_analytics_user_id ON ai_usage_analytics(user_id);
CREATE INDEX idx_ai_usage_analytics_feature_type ON ai_usage_analytics(feature_type);
CREATE INDEX idx_ai_usage_analytics_used_at ON ai_usage_analytics(used_at DESC);

-- Cost Optimization Insights Table
CREATE TABLE IF NOT EXISTS cost_optimization_insights (
    insight_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    
    -- Insight Details
    insight_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'medium',
    
    -- Cost Impact
    current_cost_monthly_usd DECIMAL(10,2),
    potential_savings_monthly_usd DECIMAL(10,2),
    savings_percentage DECIMAL(5,2),
    
    -- Recommendations
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    recommendations TEXT[],
    
    -- Status
    status VARCHAR(30) DEFAULT 'active',
    acknowledged_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    acknowledged_at TIMESTAMPTZ,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    identified_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    
    CONSTRAINT cost_insight_severity_check CHECK (severity IN ('low', 'medium', 'high')),
    CONSTRAINT cost_insight_status_check CHECK (status IN ('active', 'acknowledged', 'implemented', 'dismissed'))
);

CREATE INDEX idx_cost_optimization_insights_organization_id ON cost_optimization_insights(organization_id);
CREATE INDEX idx_cost_optimization_insights_status ON cost_optimization_insights(status);
CREATE INDEX idx_cost_optimization_insights_severity ON cost_optimization_insights(severity);

-- Custom Reports Table
CREATE TABLE IF NOT EXISTS custom_reports (
    report_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Report Configuration
    report_name VARCHAR(255) NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    
    -- Query Configuration
    query_config JSONB NOT NULL,
    
    -- Schedule
    is_scheduled BOOLEAN DEFAULT FALSE,
    schedule_cron VARCHAR(100),
    
    -- Output
    output_format VARCHAR(20) DEFAULT 'json',
    recipients TEXT[],
    
    -- Last Execution
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    last_result_url TEXT,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_custom_reports_organization_id ON custom_reports(organization_id);
CREATE INDEX idx_custom_reports_created_by ON custom_reports(created_by);
CREATE INDEX idx_custom_reports_next_run_at ON custom_reports(next_run_at);

-- ============================================================================
-- SECTION 3: RBAC & ADMINISTRATION
-- ============================================================================

-- Roles Table (Casbin integration)
CREATE TABLE IF NOT EXISTS rbac_roles (
    role_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(organization_id) ON DELETE CASCADE,
    
    -- Role Details
    role_name VARCHAR(100) NOT NULL,
    role_key VARCHAR(50) NOT NULL,
    description TEXT,
    
    -- Scope
    is_system_role BOOLEAN DEFAULT FALSE,
    is_default BOOLEAN DEFAULT FALSE,
    
    -- Permissions (Casbin policies)
    permissions JSONB NOT NULL DEFAULT '[]',
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT rbac_roles_unique_key UNIQUE (organization_id, role_key)
);

CREATE INDEX idx_rbac_roles_organization_id ON rbac_roles(organization_id);
CREATE INDEX idx_rbac_roles_role_key ON rbac_roles(role_key);
CREATE INDEX idx_rbac_roles_is_system_role ON rbac_roles(is_system_role);

-- User Role Assignments Table
CREATE TABLE IF NOT EXISTS user_role_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES rbac_roles(role_id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(organization_id) ON DELETE CASCADE,
    
    -- Assignment Details
    assigned_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    
    -- Expiration (optional)
    expires_at TIMESTAMPTZ,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT user_role_unique UNIQUE (user_id, role_id, organization_id)
);

CREATE INDEX idx_user_role_assignments_user_id ON user_role_assignments(user_id);
CREATE INDEX idx_user_role_assignments_role_id ON user_role_assignments(role_id);
CREATE INDEX idx_user_role_assignments_organization_id ON user_role_assignments(organization_id);

-- Casbin Policy Rules Table (for Casbin adapter)
CREATE TABLE IF NOT EXISTS casbin_rule (
    id SERIAL PRIMARY KEY,
    ptype VARCHAR(100),
    v0 VARCHAR(100),
    v1 VARCHAR(100),
    v2 VARCHAR(100),
    v3 VARCHAR(100),
    v4 VARCHAR(100),
    v5 VARCHAR(100),
    
    CONSTRAINT casbin_rule_unique UNIQUE (ptype, v0, v1, v2, v3, v4, v5)
);

CREATE INDEX idx_casbin_rule_ptype ON casbin_rule(ptype);
CREATE INDEX idx_casbin_rule_v0 ON casbin_rule(v0);
CREATE INDEX idx_casbin_rule_v1 ON casbin_rule(v1);

-- Organization Members Table
CREATE TABLE IF NOT EXISTS organization_members (
    member_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Role in organization
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    
    -- Permissions
    can_manage_members BOOLEAN DEFAULT FALSE,
    can_manage_billing BOOLEAN DEFAULT FALSE,
    can_manage_settings BOOLEAN DEFAULT FALSE,
    can_view_analytics BOOLEAN DEFAULT FALSE,
    
    -- Status
    status VARCHAR(30) DEFAULT 'active',
    invited_by UUID REFERENCES users(user_id) ON DELETE SET NULL,
    invitation_token VARCHAR(255),
    invitation_expires_at TIMESTAMPTZ,
    
    -- Timestamps
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT org_member_unique UNIQUE (organization_id, user_id),
    CONSTRAINT org_member_role_check CHECK (role IN ('owner', 'admin', 'member', 'guest')),
    CONSTRAINT org_member_status_check CHECK (status IN ('active', 'invited', 'suspended'))
);

CREATE INDEX idx_organization_members_organization_id ON organization_members(organization_id);
CREATE INDEX idx_organization_members_user_id ON organization_members(user_id);
CREATE INDEX idx_organization_members_role ON organization_members(role);
CREATE INDEX idx_organization_members_status ON organization_members(status);

-- Billing & Subscriptions Table
CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    
    -- Subscription Details
    plan_name VARCHAR(50) NOT NULL,
    plan_interval VARCHAR(20) DEFAULT 'monthly',
    
    -- Pricing
    amount_usd DECIMAL(10,2) NOT NULL DEFAULT 0,
    currency VARCHAR(3) DEFAULT 'USD',
    
    -- Status
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    
    -- Billing Provider (Stripe)
    stripe_subscription_id VARCHAR(255),
    stripe_customer_id VARCHAR(255),
    stripe_price_id VARCHAR(255),
    
    -- Usage-Based Billing
    included_minutes INT DEFAULT 0,
    additional_minute_price_usd DECIMAL(10,6),
    included_ai_calls INT DEFAULT 0,
    additional_ai_call_price_usd DECIMAL(10,6),
    
    -- Trial
    trial_ends_at TIMESTAMPTZ,
    
    -- Dates
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    cancelled_at TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT subscription_plan_check CHECK (plan_name IN ('free', 'pro', 'enterprise', 'custom')),
    CONSTRAINT subscription_interval_check CHECK (plan_interval IN ('monthly', 'yearly')),
    CONSTRAINT subscription_status_check CHECK (status IN ('active', 'cancelled', 'past_due', 'trialing', 'incomplete'))
);

CREATE INDEX idx_subscriptions_organization_id ON subscriptions(organization_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_stripe_subscription_id ON subscriptions(stripe_subscription_id);

-- Invoices Table
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(subscription_id) ON DELETE SET NULL,
    
    -- Invoice Details
    invoice_number VARCHAR(100) UNIQUE NOT NULL,
    
    -- Amounts
    subtotal_usd DECIMAL(10,2) NOT NULL,
    tax_usd DECIMAL(10,2) DEFAULT 0,
    total_usd DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    
    -- Status
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    
    -- Stripe Integration
    stripe_invoice_id VARCHAR(255),
    stripe_payment_intent_id VARCHAR(255),
    
    -- Line Items
    line_items JSONB DEFAULT '[]',
    
    -- Dates
    invoice_date DATE NOT NULL,
    due_date DATE,
    paid_at TIMESTAMPTZ,
    
    -- Payment Method
    payment_method VARCHAR(50),
    
    -- PDF
    pdf_url TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT invoice_status_check CHECK (status IN ('draft', 'open', 'paid', 'void', 'uncollectible'))
);

CREATE INDEX idx_invoices_organization_id ON invoices(organization_id);
CREATE INDEX idx_invoices_subscription_id ON invoices(subscription_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_invoice_date ON invoices(invoice_date DESC);

-- Usage Tracking Table (for billing)
CREATE TABLE IF NOT EXISTS usage_records (
    record_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(organization_id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(subscription_id) ON DELETE SET NULL,
    
    -- Usage Type
    usage_type VARCHAR(50) NOT NULL,
    
    -- Quantities
    quantity INT NOT NULL,
    unit_price_usd DECIMAL(10,6),
    total_cost_usd DECIMAL(10,2),
    
    -- Context
    resource_id VARCHAR(255),
    
    -- Billing Period
    billing_period_start DATE NOT NULL,
    billing_period_end DATE NOT NULL,
    
    -- Status
    billed BOOLEAN DEFAULT FALSE,
    invoice_id UUID REFERENCES invoices(invoice_id) ON DELETE SET NULL,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Timestamp
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_usage_records_organization_id ON usage_records(organization_id);
CREATE INDEX idx_usage_records_subscription_id ON usage_records(subscription_id);
CREATE INDEX idx_usage_records_usage_type ON usage_records(usage_type);
CREATE INDEX idx_usage_records_billing_period ON usage_records(billing_period_start, billing_period_end);
CREATE INDEX idx_usage_records_billed ON usage_records(billed);

-- ============================================================================
-- SECTION 4: BATCH PROCESSING & WORKFLOWS
-- ============================================================================

-- Apache Airflow DAG Runs Table
CREATE TABLE IF NOT EXISTS airflow_dag_runs (
    dag_run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(organization_id) ON DELETE SET NULL,
    
    -- DAG Details
    dag_id VARCHAR(255) NOT NULL,
    dag_name VARCHAR(255) NOT NULL,
    execution_date TIMESTAMPTZ NOT NULL,
    
    -- Status
    state VARCHAR(30) NOT NULL,
    
    -- Configuration
    conf JSONB DEFAULT '{}',
    
    -- Timing
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    duration_seconds INT,
    
    -- Metadata
    external_trigger BOOLEAN DEFAULT FALSE,
    run_type VARCHAR(50),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT airflow_dag_state_check CHECK (state IN ('running', 'success', 'failed', 'skipped', 'queued'))
);

CREATE INDEX idx_airflow_dag_runs_organization_id ON airflow_dag_runs(organization_id);
CREATE INDEX idx_airflow_dag_runs_dag_id ON airflow_dag_runs(dag_id);
CREATE INDEX idx_airflow_dag_runs_execution_date ON airflow_dag_runs(execution_date DESC);
CREATE INDEX idx_airflow_dag_runs_state ON airflow_dag_runs(state);

-- Argo Workflows Table
CREATE TABLE IF NOT EXISTS argo_workflows (
    workflow_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(organization_id) ON DELETE SET NULL,
    
    -- Workflow Details
    workflow_name VARCHAR(255) NOT NULL,
    workflow_namespace VARCHAR(100) DEFAULT 'default',
    workflow_uid VARCHAR(255),
    
    -- Status
    phase VARCHAR(30) NOT NULL,
    
    -- Timing
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    duration_seconds INT,
    
    -- Configuration
    parameters JSONB DEFAULT '{}',
    
    -- Results
    outputs JSONB,
    nodes_status JSONB,
    
    -- Resource Usage
    cpu_usage VARCHAR(50),
    memory_usage VARCHAR(50),
    
    -- Metadata
    labels JSONB DEFAULT '{}',
    annotations JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT argo_workflow_phase_check CHECK (phase IN ('Pending', 'Running', 'Succeeded', 'Failed', 'Error'))
);

CREATE INDEX idx_argo_workflows_organization_id ON argo_workflows(organization_id);
CREATE INDEX idx_argo_workflows_workflow_name ON argo_workflows(workflow_name);
CREATE INDEX idx_argo_workflows_phase ON argo_workflows(phase);
CREATE INDEX idx_argo_workflows_started_at ON argo_workflows(started_at DESC);

-- ============================================================================
-- SECTION 5: MATERIALIZED VIEWS FOR ANALYTICS
-- ============================================================================

-- Organization Analytics Summary
CREATE MATERIALIZED VIEW IF NOT EXISTS organization_analytics_summary AS
SELECT 
    o.organization_id,
    o.name AS organization_name,
    COUNT(DISTINCT om.user_id) AS total_members,
    COUNT(DISTINCT c.call_id) AS total_calls,
    COALESCE(SUM(c.duration_seconds), 0) AS total_call_minutes,
    COUNT(DISTINCT aa.agent_id) AS total_agents,
    COALESCE(SUM(aua.cost_usd), 0) AS total_ai_cost_usd,
    o.plan,
    s.status AS subscription_status,
    s.current_period_end AS subscription_period_end
FROM organizations o
LEFT JOIN organization_members om ON o.organization_id = om.organization_id
LEFT JOIN calls c ON c.user_id = om.user_id
LEFT JOIN ai_agents aa ON aa.user_id = om.user_id
LEFT JOIN ai_usage_analytics aua ON aua.organization_id = o.organization_id
LEFT JOIN subscriptions s ON s.organization_id = o.organization_id
GROUP BY o.organization_id, o.name, o.plan, s.status, s.current_period_end;

CREATE UNIQUE INDEX idx_org_analytics_summary_org_id ON organization_analytics_summary(organization_id);

-- Daily Usage Summary
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_usage_summary AS
SELECT
    DATE(c.started_at) AS usage_date,
    c.user_id,
    u.organization_id,
    COUNT(DISTINCT c.call_id) AS calls_count,
    SUM(c.duration_seconds) / 60 AS call_minutes,
    COUNT(DISTINCT cp.identity) AS unique_participants,
    COUNT(DISTINCT CASE WHEN aua.feature_type IS NOT NULL THEN c.call_id END) AS ai_enhanced_calls,
    COALESCE(SUM(aua.cost_usd), 0) AS ai_cost_usd
FROM calls c
JOIN users u ON c.user_id = u.user_id
LEFT JOIN call_participants cp ON c.call_id = cp.call_id
LEFT JOIN ai_usage_analytics aua ON c.call_id = aua.call_id
GROUP BY DATE(c.started_at), c.user_id, u.organization_id;

CREATE INDEX idx_daily_usage_summary_date ON daily_usage_summary(usage_date DESC);
CREATE INDEX idx_daily_usage_summary_org_id ON daily_usage_summary(organization_id);

-- ============================================================================
-- SECTION 6: FUNCTIONS & TRIGGERS
-- ============================================================================

-- Function to refresh materialized views
CREATE OR REPLACE FUNCTION refresh_analytics_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY organization_analytics_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY daily_usage_summary;
END;
$$ LANGUAGE plpgsql;

-- Function to archive old audit logs
CREATE OR REPLACE FUNCTION archive_old_audit_logs(retention_days INT DEFAULT 90)
RETURNS INT AS $$
DECLARE
    deleted_count INT;
BEGIN
    DELETE FROM audit_logs
    WHERE created_at < NOW() - INTERVAL '1 day' * retention_days
    AND severity NOT IN ('error', 'critical');
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate monthly costs
CREATE OR REPLACE FUNCTION calculate_monthly_costs(
    org_id UUID,
    start_date DATE,
    end_date DATE
)
RETURNS TABLE (
    total_cost_usd DECIMAL(10,2),
    call_cost_usd DECIMAL(10,2),
    ai_cost_usd DECIMAL(10,2),
    storage_cost_usd DECIMAL(10,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COALESCE(SUM(ur.total_cost_usd), 0) AS total_cost,
        COALESCE(SUM(CASE WHEN ur.usage_type = 'call_minutes' THEN ur.total_cost_usd ELSE 0 END), 0) AS call_cost,
        COALESCE(SUM(CASE WHEN ur.usage_type LIKE 'ai_%' THEN ur.total_cost_usd ELSE 0 END), 0) AS ai_cost,
        COALESCE(SUM(CASE WHEN ur.usage_type = 'storage_gb' THEN ur.total_cost_usd ELSE 0 END), 0) AS storage_cost
    FROM usage_records ur
    WHERE ur.organization_id = org_id
    AND ur.billing_period_start >= start_date
    AND ur.billing_period_end <= end_date;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update trigger to relevant tables
CREATE TRIGGER update_sso_configs_updated_at BEFORE UPDATE ON sso_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_data_retention_policies_updated_at BEFORE UPDATE ON data_retention_policies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_rbac_roles_updated_at BEFORE UPDATE ON rbac_roles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_organization_members_updated_at BEFORE UPDATE ON organization_members
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_subscriptions_updated_at BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_invoices_updated_at BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_custom_reports_updated_at BEFORE UPDATE ON custom_reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SECTION 7: DEFAULT DATA & SEEDING
-- ============================================================================

-- Insert default RBAC roles
INSERT INTO rbac_roles (role_name, role_key, description, is_system_role, is_default, permissions) VALUES
('Organization Owner', 'org_owner', 'Full control over organization', TRUE, FALSE, '[{"resource": "*", "action": "*"}]'),
('Organization Admin', 'org_admin', 'Administrative access to organization', TRUE, FALSE, '[{"resource": "users", "action": "*"}, {"resource": "settings", "action": "*"}, {"resource": "billing", "action": "read"}]'),
('Billing Manager', 'billing_manager', 'Manage billing and subscriptions', TRUE, FALSE, '[{"resource": "billing", "action": "*"}, {"resource": "usage", "action": "read"}]'),
('Member', 'member', 'Standard organization member', TRUE, TRUE, '[{"resource": "calls", "action": "*"}, {"resource": "agents", "action": "*"}]'),
('Guest', 'guest', 'Limited access guest', TRUE, FALSE, '[{"resource": "calls", "action": "read"}]')
ON CONFLICT DO NOTHING;

-- Migration complete
COMMENT ON TABLE sso_configs IS 'Phase 7: SSO configurations for SAML/OAuth authentication';
COMMENT ON TABLE audit_logs IS 'Phase 7: Comprehensive audit logging for compliance';
COMMENT ON TABLE compliance_requests IS 'Phase 7: GDPR/HIPAA compliance request tracking';
COMMENT ON TABLE rbac_roles IS 'Phase 7: Role-based access control with Casbin';
COMMENT ON TABLE subscriptions IS 'Phase 7: Billing and subscription management';
COMMENT ON TABLE airflow_dag_runs IS 'Phase 7: Apache Airflow DAG execution tracking';
COMMENT ON TABLE argo_workflows IS 'Phase 7: Argo Workflows for K8s batch processing';

-- End of Phase 7 schema migration
