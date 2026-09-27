import logging

import httpx

from .base import BaseVerifier, VerifyResult

logger = logging.getLogger(__name__)

class GitHubVerifier(BaseVerifier):
    async def verify(self, credentials: dict[str, str]) -> VerifyResult:
        token = credentials.get("token")
        
        if not token:
            return VerifyResult(False, "Missing token")
            
        url = "https://api.github.com/user"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=headers)
                
            if response.status_code == 200:
                scopes = response.headers.get("X-OAuth-Scopes", "")
                return VerifyResult(True, f"GitHub verification successful. Scopes: {scopes}")
            return VerifyResult(False, f"GitHub verification failed: {response.status_code} {response.text}")
        except httpx.RequestError as e:
            logger.error(f"GitHub network error: {e}")
            return VerifyResult(False, f"Network error during GitHub verification: {str(e)}")
