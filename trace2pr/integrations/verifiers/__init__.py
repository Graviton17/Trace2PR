"""Integration verifiers package."""
from .base import BaseVerifier, VerifyResult
from .cloudwatch import CloudWatchVerifier
from .datadog import DatadogVerifier
from .github import GitHubVerifier
from .grafana import GrafanaVerifier
from .pagerduty import PagerDutyVerifier
from .sentry import SentryVerifier

__all__ = [
    "BaseVerifier",
    "VerifyResult",
    "GitHubVerifier",
    "DatadogVerifier",
    "SentryVerifier",
    "PagerDutyVerifier",
    "GrafanaVerifier",
    "CloudWatchVerifier",
    "get_verifier",
]

# Registry of verifiers
_VERIFIERS = {
    "github": GitHubVerifier(),
    "datadog": DatadogVerifier(),
    "sentry": SentryVerifier(),
    "pagerduty": PagerDutyVerifier(),
    "grafana": GrafanaVerifier(),
    "cloudwatch": CloudWatchVerifier(),
}


def get_verifier(service: str) -> BaseVerifier:
    """Get verifier for a service."""
    service = service.lower()
    if service not in _VERIFIERS:
        raise ValueError(f"No verifier for service: {service}")
    return _VERIFIERS[service]