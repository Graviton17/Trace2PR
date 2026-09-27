"""Sentry integration verifier."""
import logging

import httpx

from .base import BaseVerifier, VerifyResult

logger = logging.getLogger(__name__)


class SentryVerifier(BaseVerifier):
    async def verify(self, credentials: dict[str, str]) -> VerifyResult:
        auth_token = credentials.get("auth_token")
        org_slug = credentials.get("org_slug")

        if not auth_token:
            return VerifyResult(False, "Missing Auth Token")

        url = "https://sentry.io/api/0/user/"
        if org_slug:
            url = f"https://sentry.io/api/0/organizations/{org_slug}/"

        headers = {
            "Authorization": f"Bearer {auth_token}",
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                name = data.get("name") or data.get("slug") or "organization"
                return VerifyResult(True, f"Sentry verification successful: {name}")
            return VerifyResult(False, f"Sentry verification failed: {response.status_code} {response.text}")
        except httpx.RequestError as e:
            logger.error(f"Sentry network error: {e}")
            return VerifyResult(False, f"Network error during Sentry verification: {str(e)}")