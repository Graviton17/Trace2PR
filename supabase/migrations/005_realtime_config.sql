-- Enable Realtime on tables
--
-- NOTE: migrations/001 already creates the `supabase_realtime` publication
-- and adds incidents, alerts, timeline_events, pull_requests, and
-- integrations to it. Re-adding a table that's already a publication
-- member raises "relation already member of publication" and aborts the
-- whole migration — this previously blocked every migration after it from
-- ever running. We only add the tables that are genuinely new here
-- (fix_jobs, fix_attempts), and guard each with a existence check so this
-- migration is safe to re-run.

BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
    CREATE PUBLICATION supabase_realtime;
  END IF;
END
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'fix_jobs'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE fix_jobs;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'fix_attempts'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE fix_attempts;
  END IF;
END
$$;

COMMIT;
