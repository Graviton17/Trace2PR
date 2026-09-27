"""Composio integration service for OAuth and webhook management."""
import logging
from dataclasses import dataclass
from typing import Any

from trace2pr.config.settings import settings

logger = logging.getLogger(__name__)


# Mapping of our service names to Composio app names
COMPOSIO_APP_MAP = {
    "datadog": "DATADOG",
    "sentry": "SENTRY",
    "github": "GITHUB",
    "pagerduty": "PAGERDUTY",
    "grafana": "GRAFANA",
    "cloudwatch": "AWS_CLOUDWATCH",
    "slack": "SLACK",
    "linear": "LINEAR",
    "jira": "JIRA",
}


@dataclass
class ComposioConnectionResult:
    success: bool
    connection_id: str | None = None
    entity_id: str | None = None
    redirect_url: str | None = None
    error: str | None = None


class ComposioService:
    """Service for managing Composio integrations."""

    def __init__(self):
        self.api_key = settings.COMPOSIO_API_KEY
        self.base_url = settings.COMPOSIO_BASE_URL
        self._client = None

    def _get_client(self):
        """Lazy-load Composio client."""
        if self._client is None:
            try:
                from composio import Composio
                self._client = Composio(api_key=self.api_key)
            except ImportError:
                logger.warning("composio-core not installed, using mock mode")
                self._client = None
        return self._client

    async def init_entity(self, user_id: str) -> str:
        """Get or create a Composio entity for the user."""
        client = self._get_client()
        if not client:
            # Mock mode for development
            return f"entity_{user_id}"

        try:
            client.get_entity(id=user_id)
            return user_id
        except Exception as e:
            logger.error(f"Failed to get entity: {e}")
            return user_id

    async def initiate_connection(
        self,
        user_id: str,
        service: str,
        redirect_url: str | None = None,
    ) -> ComposioConnectionResult:
        """Initiate OAuth connection for a service via Composio."""
        client = self._get_client()
        app_name = COMPOSIO_APP_MAP.get(service.lower())

        if not app_name:
            return ComposioConnectionResult(
                success=False,
                error=f"Unsupported service: {service}"
            )

        if not client:
            # Mock mode - return a fake redirect URL for testing
            mock_redirect = f"{settings.FRONTEND_URL}/dashboard/integrations?mock_oauth={service}&user_id={user_id}"
            return ComposioConnectionResult(
                success=True,
                connection_id=f"mock_conn_{service}_{user_id}",
                entity_id=f"entity_{user_id}",
                redirect_url=mock_redirect,
            )

        try:
            entity_id = await self.init_entity(user_id)
            entity = client.get_entity(id=entity_id)

            # Initiate connection - this returns a redirect URL for OAuth
            connection = entity.initiate_connection(
                app_name=app_name,
                redirect_url=redirect_url or f"{settings.FRONTEND_URL}/dashboard/integrations/callback",
            )

            return ComposioConnectionResult(
                success=True,
                connection_id=getattr(connection, 'connectedAccountId', None),
                entity_id=entity_id,
                redirect_url=getattr(connection, 'redirectUrl', None),
            )
        except Exception as e:
            logger.error(f"Failed to initiate Composio connection for {service}: {e}")
            return ComposioConnectionResult(
                success=False,
                error=str(e)
            )

    async def get_connection_status(
        self,
        entity_id: str,
        service: str,
    ) -> dict[str, Any]:
        """Get connection status for a service."""
        client = self._get_client()
        app_name = COMPOSIO_APP_MAP.get(service.lower())

        if not client or not app_name:
            return {"connected": False, "error": "Not configured"}

        try:
            entity = client.get_entity(id=entity_id)
            try:
                conn = entity.get_connection(app_name=app_name)
                return {
                    "connected": conn.status == "ACTIVE",
                    "connection_id": conn.id,
                    "status": conn.status,
                    "auth_config": getattr(conn, 'auth_config', None),
                }
            except Exception:
                return {"connected": False}
        except Exception as e:
            logger.error(f"Failed to get connection status for {service}: {e}")
            return {"connected": False, "error": str(e)}

    async def disconnect(self, entity_id: str, service: str) -> bool:
        """Disconnect a service."""
        client = self._get_client()
        app_name = COMPOSIO_APP_MAP.get(service.lower())

        if not client or not app_name:
            return False

        try:
            entity = client.get_entity(id=entity_id)
            try:
                conn = entity.get_connection(app_name=app_name)
                # Call HTTP client directly if missing from Entity
                client.http_client.delete(f"{client.base_url}/v1/connectedAccounts/{conn.id}")
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"Failed to disconnect {service}: {e}")
            return False

    async def execute_action(
        self,
        entity_id: str,
        service: str,
        action: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an action on a connected service."""
        client = self._get_client()
        app_name = COMPOSIO_APP_MAP.get(service.lower())

        if not client or not app_name:
            return {"success": False, "error": "Not configured"}

        try:
            entity = client.get_entity(id=entity_id)
            conn = entity.get_connection(app_name=app_name)
            result = conn.execute_action(
                action_name=action,
                params=params,
            )
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Failed to execute {action} on {service}: {e}")
            return {"success": False, "error": str(e)}

    async def setup_webhook_triggers(
        self,
        entity_id: str,
        service: str,
        webhook_url: str,
        events: list[str],
    ) -> dict[str, Any]:
        """Set up webhook triggers for a service via Composio."""
        client = self._get_client()
        app_name = COMPOSIO_APP_MAP.get(service.lower())

        if not client or not app_name:
            return {"success": False, "error": "Not configured"}

        try:
            entity = client.get_entity(id=entity_id)
            conn = entity.get_connection(app_name=app_name)
            
            # Composio handles webhook registration via client.enable_trigger
            trigger = client.enable_trigger(
                trigger_name="webhook",
                connected_account_id=conn.id,
                user_inputs={
                    "webhook_url": webhook_url,
                    "events": events,
                }
            )
            return {"success": True, "trigger_id": getattr(trigger, 'id', None)}
        except Exception as e:
            logger.error(f"Failed to setup webhook for {service}: {e}")
            return {"success": False, "error": str(e)}


# Singleton instance
composio_service = ComposioService()