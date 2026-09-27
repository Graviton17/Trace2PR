from dataclasses import dataclass
from typing import Protocol


@dataclass
class VerifyResult:
    success: bool
    message: str

class BaseVerifier(Protocol):
    async def verify(self, credentials: dict[str, str]) -> VerifyResult:
        ...
