-- =============================================
-- Trace2PR Database Schema
-- =============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
-- Required by knowledge_base.embedding (VECTOR type) below; without this the
-- CREATE TABLE for knowledge_base fails outright.
CREATE EXTENSION IF NOT EXISTS "vector";

-- =============================================
-- Users table (linked to auth.users via RLS)
-- =============================================
CREATE TABLE public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    provider TEXT, -- 'github', 'google', 'email'
    theme TEXT NOT NULL DEFAULT 'system', -- 'light', 'dark', 'system'
    notifications JSONB NOT NULL DEFAULT '{}', -- per-channel notification prefs
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- Integrations table
-- =============================================
CREATE TABLE public.integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    service TEXT NOT NULL, -- 'datadog', 'sentry', 'github', 'pagerduty', 'grafana', 'cloudwatch'
    category TEXT NOT NULL, -- 'observability', 'incident', 'vcs', 'cloud'
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'connected', 'error', 'disconnected'
    config JSONB DEFAULT '{}', -- non-sensitive config (e.g., org_slug, site, region)
    composio_connection_id TEXT, -- Composio connection ID for this integration
    composio_entity_id TEXT, -- Composio entity ID (user in Composio)
    vault_secret_id UUID, -- Supabase Vault secret ID for direct (non-Composio) API credentials
    verified_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, service)
);

-- =============================================
-- Incidents table
-- =============================================
CREATE TABLE public.incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    service TEXT,
    environment TEXT,
    description TEXT,
    repository TEXT, -- e.g., 'org/repo'
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'investigating', 'fixing', 'resolved', 'closed')),
    source TEXT, -- 'datadog', 'sentry', 'pagerduty', 'grafana', 'cloudwatch', 'manual'
    source_incident_id TEXT, -- External incident ID from monitoring tool
    composio_trigger_id TEXT, -- Composio trigger ID if auto-created
    assigned_agent_id TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- Alerts table
-- =============================================
CREATE TABLE public.alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    incident_id UUID REFERENCES public.incidents(id) ON DELETE SET NULL,
    source TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'acknowledged', 'processing', 'resolved', 'dismissed')),
    title TEXT NOT NULL,
    service TEXT,
    environment TEXT,
    payload JSONB DEFAULT '{}', -- Raw alert payload
    dismiss_reason TEXT,
    fired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- Timeline Events table
-- =============================================
CREATE TABLE public.timeline_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES public.incidents(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL, -- 'incident_created', 'alert_fired', 'analysis_started', 'fix_generated', 'pr_opened', 'incident_resolved'
    title TEXT NOT NULL,
    detail TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- Analysis Jobs & Reports tables
-- =============================================
CREATE TABLE public.analysis_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    incident_id UUID NOT NULL REFERENCES public.incidents(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE public.analysis_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    incident_id UUID NOT NULL REFERENCES public.incidents(id) ON DELETE CASCADE,
    analysis_job_id UUID REFERENCES public.analysis_jobs(id) ON DELETE SET NULL,
    summary TEXT NOT NULL,
    root_cause_hypothesis TEXT NOT NULL DEFAULT '',
    suspected_files JSONB NOT NULL DEFAULT '[]', -- [{path, reason, confidence_score}]
    evidence JSONB NOT NULL DEFAULT '{}', -- {logs: [...], commits: [...], traces: [...]}
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- Fix Jobs & Attempts tables
-- =============================================
CREATE TABLE public.fix_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    incident_id UUID NOT NULL REFERENCES public.incidents(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (
        status IN (
            'queued', 'sandbox_creating', 'cloning', 'analyzing', 'fixing',
            'testing', 'pr_creating', 'completed', 'failed', 'cancelled'
        )
    ),
    instructions TEXT,
    transcript JSONB NOT NULL DEFAULT '[]', -- [{role, content, timestamp, tool_calls}]
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE public.fix_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fix_job_id UUID NOT NULL REFERENCES public.fix_jobs(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    diff JSONB, -- {files: [{file_path, diff, additions, deletions}], total_additions, total_deletions}
    test_results JSONB, -- {passed, failed, skipped, failures: [...]}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (fix_job_id, attempt_number)
);

-- =============================================
-- Pull Requests table
-- =============================================
CREATE TABLE public.pull_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    incident_id UUID REFERENCES public.incidents(id) ON DELETE SET NULL,
    github_pr_id BIGINT,
    repository TEXT NOT NULL, -- 'org/repo'
    title TEXT NOT NULL,
    body TEXT,
    branch_name TEXT NOT NULL,
    base_branch TEXT NOT NULL DEFAULT 'main',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'open', 'review', 'merged', 'closed')),
    html_url TEXT,
    diff_url TEXT,
    files_changed JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    merged_at TIMESTAMPTZ
);

-- =============================================
-- Knowledge Base table
-- =============================================
CREATE TABLE public.knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_type TEXT NOT NULL, -- 'pr', 'incident', 'manual', 'doc'
    source_id UUID, -- Reference to PR or incident
    tags TEXT[] DEFAULT '{}',
    embedding VECTOR(1536), -- For vector search (requires pgvector)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- Knowledge Base Feedback table
-- =============================================
CREATE TABLE public.knowledge_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    item_id UUID NOT NULL,
    item_type TEXT NOT NULL, -- 'incidents' | 'fixes'
    helpful BOOLEAN NOT NULL,
    comments TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- Sandbox Executions table
-- =============================================
CREATE TABLE public.sandbox_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    incident_id UUID REFERENCES public.incidents(id) ON DELETE SET NULL,
    pr_id UUID REFERENCES public.pull_requests(id) ON DELETE SET NULL,
    e2b_sandbox_id TEXT,
    command TEXT NOT NULL,
    stdout TEXT,
    stderr TEXT,
    exit_code INTEGER,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- =============================================
-- Webhook Logs table (for debugging)
-- =============================================
CREATE TABLE public.webhook_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    integration_id UUID REFERENCES public.integrations(id) ON DELETE SET NULL,
    source TEXT NOT NULL,
    event_type TEXT,
    payload JSONB NOT NULL,
    headers JSONB,
    processed BOOLEAN DEFAULT FALSE,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- Row Level Security (RLS) Policies
-- =============================================

-- Enable RLS on all tables
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.integrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.timeline_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pull_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_base ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sandbox_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.webhook_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fix_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fix_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_feedback ENABLE ROW LEVEL SECURITY;

-- Users: users can only see/update their own profile
CREATE POLICY "Users can view own profile" ON public.users
    FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON public.users
    FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "Users can insert own profile" ON public.users
    FOR INSERT WITH CHECK (auth.uid() = id);

-- Integrations: users can only access their own integrations
CREATE POLICY "Users can view own integrations" ON public.integrations
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own integrations" ON public.integrations
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own integrations" ON public.integrations
    FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own integrations" ON public.integrations
    FOR DELETE USING (auth.uid() = user_id);

-- Incidents: users can only access their own incidents
CREATE POLICY "Users can view own incidents" ON public.incidents
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own incidents" ON public.incidents
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own incidents" ON public.incidents
    FOR UPDATE USING (auth.uid() = user_id);

-- Alerts: users can only access their own alerts
CREATE POLICY "Users can view own alerts" ON public.alerts
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own alerts" ON public.alerts
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Timeline Events: users can only access events for their incidents
CREATE POLICY "Users can view timeline for own incidents" ON public.timeline_events
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM public.incidents WHERE id = incident_id AND user_id = auth.uid())
    );
CREATE POLICY "Users can insert timeline for own incidents" ON public.timeline_events
    FOR INSERT WITH CHECK (
        EXISTS (SELECT 1 FROM public.incidents WHERE id = incident_id AND user_id = auth.uid())
    );

-- Pull Requests: users can only access their own PRs
CREATE POLICY "Users can view own PRs" ON public.pull_requests
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own PRs" ON public.pull_requests
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own PRs" ON public.pull_requests
    FOR UPDATE USING (auth.uid() = user_id);

-- Knowledge Base: users can only access their own entries
CREATE POLICY "Users can view own knowledge" ON public.knowledge_base
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own knowledge" ON public.knowledge_base
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own knowledge" ON public.knowledge_base
    FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own knowledge" ON public.knowledge_base
    FOR DELETE USING (auth.uid() = user_id);

-- Sandbox Executions: users can only access their own executions
CREATE POLICY "Users can view own executions" ON public.sandbox_executions
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own executions" ON public.sandbox_executions
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own executions" ON public.sandbox_executions
    FOR UPDATE USING (auth.uid() = user_id);

-- Webhook Logs: users can only view logs for their integrations
CREATE POLICY "Users can view own webhook logs" ON public.webhook_logs
    FOR SELECT USING (auth.uid() = user_id);

-- Analysis Jobs & Reports: users can only access their own
CREATE POLICY "Users can manage own analysis jobs" ON public.analysis_jobs
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can manage own analysis reports" ON public.analysis_reports
    FOR ALL USING (auth.uid() = user_id);

-- Fix Jobs: users can only access their own; attempts inherit via parent job
CREATE POLICY "Users can manage own fix jobs" ON public.fix_jobs
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can manage attempts of own fix jobs" ON public.fix_attempts
    FOR ALL USING (
        EXISTS (SELECT 1 FROM public.fix_jobs WHERE id = fix_job_id AND user_id = auth.uid())
    );

-- Knowledge Feedback: users can only manage their own feedback
CREATE POLICY "Users can manage own knowledge feedback" ON public.knowledge_feedback
    FOR ALL USING (auth.uid() = user_id);

-- =============================================
-- Triggers for updated_at
-- =============================================
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER users_updated_at BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION handle_updated_at();
CREATE TRIGGER integrations_updated_at BEFORE UPDATE ON public.integrations
    FOR EACH ROW EXECUTE FUNCTION handle_updated_at();
CREATE TRIGGER incidents_updated_at BEFORE UPDATE ON public.incidents
    FOR EACH ROW EXECUTE FUNCTION handle_updated_at();
CREATE TRIGGER pull_requests_updated_at BEFORE UPDATE ON public.pull_requests
    FOR EACH ROW EXECUTE FUNCTION handle_updated_at();
CREATE TRIGGER knowledge_base_updated_at BEFORE UPDATE ON public.knowledge_base
    FOR EACH ROW EXECUTE FUNCTION handle_updated_at();
CREATE TRIGGER analysis_jobs_updated_at BEFORE UPDATE ON public.analysis_jobs
    FOR EACH ROW EXECUTE FUNCTION handle_updated_at();
CREATE TRIGGER fix_jobs_updated_at BEFORE UPDATE ON public.fix_jobs
    FOR EACH ROW EXECUTE FUNCTION handle_updated_at();

-- =============================================
-- Function to handle new user signup
-- =============================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    INSERT INTO public.users (id, email, full_name, avatar_url, provider)
    VALUES (
        NEW.id,
        NEW.email,
        NEW.raw_user_meta_data->>'full_name',
        NEW.raw_user_meta_data->>'avatar_url',
        COALESCE(NEW.raw_app_meta_data->>'provider', 'email')
    );
    RETURN NEW;
EXCEPTION WHEN unique_violation THEN
    -- User profile might already exist, update it
    UPDATE public.users
    SET email = NEW.email,
        full_name = COALESCE(NEW.raw_user_meta_data->>'full_name', public.users.full_name),
        avatar_url = COALESCE(NEW.raw_user_meta_data->>'avatar_url', public.users.avatar_url),
        updated_at = NOW()
    WHERE id = NEW.id;
    RETURN NEW;
END;
$$;

-- Trigger on auth.users insert
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- =============================================
-- Indexes for performance
-- =============================================
CREATE INDEX idx_integrations_user_id ON public.integrations(user_id);
CREATE INDEX idx_integrations_service ON public.integrations(service);
CREATE INDEX idx_incidents_user_id ON public.incidents(user_id);
CREATE INDEX idx_incidents_status ON public.incidents(status);
CREATE INDEX idx_incidents_source_incident_id ON public.incidents(source_incident_id);
CREATE INDEX idx_alerts_user_id ON public.alerts(user_id);
CREATE INDEX idx_alerts_incident_id ON public.alerts(incident_id);
CREATE INDEX idx_alerts_fired_at ON public.alerts(fired_at DESC);
CREATE INDEX idx_timeline_events_incident_id ON public.timeline_events(incident_id);
CREATE INDEX idx_pull_requests_user_id ON public.pull_requests(user_id);
CREATE INDEX idx_pull_requests_incident_id ON public.pull_requests(incident_id);
CREATE INDEX idx_knowledge_base_user_id ON public.knowledge_base(user_id);
CREATE INDEX idx_sandbox_executions_user_id ON public.sandbox_executions(user_id);
CREATE INDEX idx_webhook_logs_user_id ON public.webhook_logs(user_id);
CREATE INDEX idx_webhook_logs_integration_id ON public.webhook_logs(integration_id);
CREATE INDEX idx_webhook_logs_created_at ON public.webhook_logs(created_at DESC);
CREATE INDEX idx_analysis_jobs_incident_id ON public.analysis_jobs(incident_id);
CREATE INDEX idx_analysis_reports_incident_id ON public.analysis_reports(incident_id);
CREATE INDEX idx_fix_jobs_user_id ON public.fix_jobs(user_id);
CREATE INDEX idx_fix_jobs_incident_id ON public.fix_jobs(incident_id);
CREATE INDEX idx_fix_attempts_fix_job_id ON public.fix_attempts(fix_job_id);

-- =============================================
-- Enable Realtime for specific tables
-- =============================================
ALTER PUBLICATION supabase_realtime ADD TABLE public.incidents;
ALTER PUBLICATION supabase_realtime ADD TABLE public.alerts;
ALTER PUBLICATION supabase_realtime ADD TABLE public.timeline_events;
ALTER PUBLICATION supabase_realtime ADD TABLE public.pull_requests;
ALTER PUBLICATION supabase_realtime ADD TABLE public.integrations;