-- Storage buckets

INSERT INTO storage.buckets (id, name, public) VALUES 
('reports', 'reports', false),
('sandbox-logs', 'sandbox-logs', false),
('pr-evidence', 'pr-evidence', false),
('transcripts', 'transcripts', false)
ON CONFLICT (id) DO NOTHING;

-- Optionally, add RLS policies for storage.objects if desired
