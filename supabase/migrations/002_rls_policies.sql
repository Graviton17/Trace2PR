-- NOTE: as of migrations/001, RLS is already enabled with per-operation
-- policies for every table below. This migration's `ENABLE ROW LEVEL
-- SECURITY` calls are idempotent no-ops, and its FOR ALL policies simply
-- add broader (but non-conflicting) permissive policies alongside 001's.
-- It previously referenced `analysis_reports`/`fix_jobs`/`fix_attempts`
-- before those tables existed anywhere (added in 001 now) and a typo'd
-- `knowledge_entries` instead of `knowledge_base` — both fixed here, which
-- is what let this migration run at all.
-- Enable RLS
ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE fix_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE fix_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE pull_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_base ENABLE ROW LEVEL SECURITY;
ALTER TABLE timeline_events ENABLE ROW LEVEL SECURITY;

-- Policies

-- integrations
CREATE POLICY "Users can manage their own integrations" 
ON integrations FOR ALL USING (auth.uid() = user_id);

-- incidents
CREATE POLICY "Users can manage their own incidents" 
ON incidents FOR ALL USING (auth.uid() = user_id);

-- alerts
CREATE POLICY "Users can manage their own alerts" 
ON alerts FOR ALL USING (auth.uid() = user_id);

-- analysis_reports
CREATE POLICY "Users can manage their own reports" 
ON analysis_reports FOR ALL USING (auth.uid() = user_id);

-- fix_jobs
CREATE POLICY "Users can manage their own fix jobs" 
ON fix_jobs FOR ALL USING (auth.uid() = user_id);

-- fix_attempts (accessible via parent fix_job)
CREATE POLICY "Users can manage attempts of their fix jobs" 
ON fix_attempts FOR ALL USING (
    EXISTS (
        SELECT 1 FROM fix_jobs 
        WHERE fix_jobs.id = fix_attempts.fix_job_id 
        AND fix_jobs.user_id = auth.uid()
    )
);

-- pull_requests
CREATE POLICY "Users can manage their own PRs" 
ON pull_requests FOR ALL USING (auth.uid() = user_id);

-- knowledge_base
CREATE POLICY "Users can manage their own knowledge entries" 
ON knowledge_base FOR ALL USING (auth.uid() = user_id);

-- timeline_events (accessible via parent incident)
CREATE POLICY "Users can manage events of their incidents" 
ON timeline_events FOR ALL USING (
    EXISTS (
        SELECT 1 FROM incidents 
        WHERE incidents.id = timeline_events.incident_id 
        AND incidents.user_id = auth.uid()
    )
);
