-- Vault wrappers (assuming pgsodium/vault schema is available)
-- These use SECURITY DEFINER so they can execute vault operations

CREATE OR REPLACE FUNCTION vault_create_secret(secret_value TEXT, secret_name TEXT, secret_description TEXT)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  new_secret_id UUID;
BEGIN
  -- We assume standard Supabase Vault usage
  SELECT id INTO new_secret_id FROM vault.create_secret(secret_value, secret_name, secret_description);
  RETURN new_secret_id;
END;
$$;

CREATE OR REPLACE FUNCTION vault_read_secret(secret_id UUID)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  secret_val TEXT;
BEGIN
  SELECT decrypted_secret INTO secret_val FROM vault.decrypted_secrets WHERE id = secret_id;
  RETURN secret_val;
END;
$$;

CREATE OR REPLACE FUNCTION vault_update_secret(secret_id UUID, new_secret TEXT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  PERFORM vault.update_secret(secret_id, new_secret);
END;
$$;

CREATE OR REPLACE FUNCTION vault_delete_secret(secret_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  DELETE FROM vault.secrets WHERE id = secret_id;
END;
$$;
