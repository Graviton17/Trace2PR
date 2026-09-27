-- Seed data for local development.
--
-- Fixed vs. the original:
--  * `integrations` was inserted with `(user_id, category, name, config)` —
--    `name` isn't a column on that table and the NOT NULL `service` column
--    was omitted, so this insert would fail outright.
--  * `test_user_id` never actually existed in `auth.users`, so every insert
--    referencing it would fail its foreign key constraint. We now create a
--    minimal auth user first (public.users.handle_new_user() trigger from
--    migrations/001 then populates public.users automatically).

DO $$
DECLARE
    test_user_id UUID := '00000000-0000-0000-0000-000000000001';
    integration_id UUID;
    incident_1 UUID;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = test_user_id) THEN
        INSERT INTO auth.users (
            instance_id, id, aud, role, email, encrypted_password,
            email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
            created_at, updated_at
        ) VALUES (
            '00000000-0000-0000-0000-000000000000', test_user_id, 'authenticated', 'authenticated',
            'dev@trace2pr.local', crypt('local-dev-only', gen_salt('bf')),
            NOW(), '{"provider": "email", "providers": ["email"]}', '{"full_name": "Dev User"}',
            NOW(), NOW()
        );
    END IF;

    INSERT INTO integrations (user_id, service, category, status, config)
    VALUES (test_user_id, 'sentry', 'observability', 'connected', '{"endpoint": "https://sentry.io"}')
    ON CONFLICT (user_id, service) DO NOTHING
    RETURNING id INTO integration_id;

    INSERT INTO incidents (user_id, title, severity, service, environment, description, repository)
    VALUES (
        test_user_id, 'Database Connection Timeout', 'critical', 'api-service', 'production',
        'Frequent connection timeouts to the main database.', 'org/api-service'
    )
    RETURNING id INTO incident_1;

    INSERT INTO alerts (user_id, incident_id, source, severity, title, service, environment, fired_at)
    VALUES (test_user_id, incident_1, 'sentry', 'critical', 'DBTimeoutException', 'api-service', 'production', NOW());

    INSERT INTO timeline_events (incident_id, event_type, title, detail)
    VALUES (incident_1, 'incident_created', 'Incident Opened', 'Incident was automatically opened by an alert.');
END $$;
