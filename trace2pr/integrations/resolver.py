import os

from supabase import AsyncClient

from .credential_store import SupabaseCredentialStore


class IntegrationResolver:
    """Resolves credentials for a (service, user) pair: Vault first, then
    environment-variable fallback, else None if not configured."""

    async def resolve(self, service: str, user_id: str, sb: AsyncClient) -> dict | None:
        # NOTE: credentials live on the `integrations` table (see
        # migrations/001 + migrations/006 for the vault_secret_id column),
        # not a separate `user_integrations` table.
        result = (
            await sb.table("integrations")
            .select("vault_secret_id")
            .eq("user_id", user_id)
            .eq("service", service)
            .maybe_single()
            .execute()
        )

        if result.data and result.data.get("vault_secret_id"):
            store = SupabaseCredentialStore(sb)
            creds = await store.get_secret(result.data["vault_secret_id"])
            if creds:
                return creds

        return self._load_from_env(service)

    def _load_from_env(self, service: str) -> dict | None:
        def _env_or_none(mapping: dict[str, str]) -> dict | None:
            creds = {}
            for k, v in mapping.items():
                val = os.getenv(v)
                if not val:
                    return None
                creds[k] = val
            return creds

        # NOTE: these env var names must match config/settings.py and
        # .env.example — they previously referenced variables that were
        # never defined anywhere (e.g. SENTRY_TOKEN instead of
        # SENTRY_AUTH_TOKEN), so env-based fallback silently always failed.
        if service == "datadog":
            return _env_or_none({"api_key": "DD_API_KEY", "app_key": "DD_APP_KEY", "site": "DD_SITE"})
        elif service == "sentry":
            return _env_or_none({"auth_token": "SENTRY_AUTH_TOKEN", "org_slug": "SENTRY_ORG_SLUG"})
        elif service == "cloudwatch":
            return _env_or_none(
                {
                    "aws_access_key_id": "AWS_ACCESS_KEY_ID",
                    "aws_secret_access_key": "AWS_SECRET_ACCESS_KEY",
                    "aws_region": "AWS_DEFAULT_REGION",
                }
            )
        elif service == "grafana":
            return _env_or_none({"read_token": "GRAFANA_READ_TOKEN", "instance_url": "GRAFANA_INSTANCE_URL"})
        elif service == "pagerduty":
            return _env_or_none({"api_key": "PAGERDUTY_API_KEY"})
        elif service == "github":
            return _env_or_none({"token": "GITHUB_TOKEN"})
        return None
