"""Stores third-party integration credentials in Supabase Vault, keyed by
a per-integration vault_secret_id (see migrations/006 for the column and
migrations/003 for the vault_* RPC wrappers)."""
import json

from supabase import AsyncClient


class SupabaseCredentialStore:
    def __init__(self, sb: AsyncClient):
        self.sb = sb

    async def store_secret(self, service: str, user_id: str, credentials: dict) -> str:
        """Store credentials in Supabase Vault. Returns vault secret ID."""
        secret_name = f"{service}_creds_{user_id}"
        secret_value = json.dumps(credentials)
        # NOTE: parameter names must match the vault_create_secret(secret_value,
        # secret_name, secret_description) signature defined in
        # migrations/003_vault_functions.sql exactly, since PostgREST RPC calls
        # bind by parameter name.
        result = await self.sb.rpc(
            "vault_create_secret",
            {
                "secret_value": secret_value,
                "secret_name": secret_name,
                "secret_description": f"Credentials for {service} - User: {user_id}",
            },
        ).execute()
        return result.data

    async def get_secret(self, vault_secret_id: str) -> dict | None:
        """Retrieve and decrypt credentials from Vault."""
        result = await self.sb.rpc("vault_read_secret", {"secret_id": vault_secret_id}).execute()
        if not result.data:
            return None
        return json.loads(result.data)

    async def update_secret(self, vault_secret_id: str, credentials: dict) -> None:
        secret_value = json.dumps(credentials)
        await self.sb.rpc(
            "vault_update_secret", {"secret_id": vault_secret_id, "new_secret": secret_value}
        ).execute()

    async def delete_secret(self, vault_secret_id: str) -> None:
        await self.sb.rpc("vault_delete_secret", {"secret_id": vault_secret_id}).execute()
