"""PagerDuty integration verifier."""
import logging

import httpx

from .base import BaseVerifier, VerifyResult

logger = logging.getLogger(__name__)


class PagerDutyVerifier(BaseVerifier):
    async def verify(self, credentials: dict[str, str]) -> VerifyResult:
        api_key = credentials.get("api_key")

        if not api_key:
            return VerifyResult(False, "Missing API Key")

        url = "https://api.pagerduty.com/users/me"
        headers = {
            "Authorization": f"Token token={api_key}",
            "Accept": "application/vnd.pagerduty+json;version=2",
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                user = data.get("user", {})
                name = user.get("name") or user.get("email") or "user"
                return VerifyResult(True, f"PagerDuty verification successful: {name}")
            return VerifyResult(False, f"PagerDuty verification failed: {response.status_code} {response.text}")
        except httpx.RequestError as e:
            logger.error(f"PagerDuty network error: {e}")
            return VerifyResult(False, f"Network error during PagerDuty verification: {str(e)}")