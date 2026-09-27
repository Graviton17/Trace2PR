"""Datadog integration verifier."""
import logging

import httpx

from .base import BaseVerifier, VerifyResult

logger = logging.getLogger(__name__)


class DatadogVerifier(BaseVerifier):
    async def verify(self, credentials: dict[str, str]) -> VerifyResult:
        api_key = credentials.get("api_key")
        app_key = credentials.get("app_key")
        site = credentials.get("site", "datadoghq.com")

        if not api_key or not app_key:
            return VerifyResult(False, "Missing API Key or Application Key")

        url = f"https://api.{site}/api/v1/validate"
        headers = {
            "DD-API-KEY": api_key,
            "DD-APPLICATION-KEY": app_key,
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                return VerifyResult(True, f"Datadog verification successful: {data.get('valid', 'valid')}")
            return VerifyResult(False, f"Datadog verification failed: {response.status_code} {response.text}")
        except httpx.RequestError as e:
            logger.error(f"Datadog network error: {e}")
            return VerifyResult(False, f"Network error during Datadog verification: {str(e)}")