"""Grafana integration verifier."""
import logging

import httpx

from .base import BaseVerifier, VerifyResult

logger = logging.getLogger(__name__)


class GrafanaVerifier(BaseVerifier):
    async def verify(self, credentials: dict[str, str]) -> VerifyResult:
        instance_url = credentials.get("instance_url")
        read_token = credentials.get("read_token")

        if not instance_url or not read_token:
            return VerifyResult(False, "Missing Instance URL or Read Token")

        # Normalize URL
        instance_url = instance_url.rstrip("/")
        url = f"{instance_url}/api/user"
        headers = {
            "Authorization": f"Bearer {read_token}",
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                name = data.get("name") or data.get("login") or "user"
                return VerifyResult(True, f"Grafana verification successful: {name}")
            return VerifyResult(False, f"Grafana verification failed: {response.status_code} {response.text}")
        except httpx.RequestError as e:
            logger.error(f"Grafana network error: {e}")
            return VerifyResult(False, f"Network error during Grafana verification: {str(e)}")