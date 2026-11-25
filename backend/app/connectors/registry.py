from app.connectors.base import PlatformConnector
from app.connectors.linkedin import LinkedInConnector


class ConnectorRegistry:
    """Central registry for platform connectors. Add new platforms here."""

    def __init__(self) -> None:
        self._connectors: dict[str, PlatformConnector] = {}

    def register(self, connector: PlatformConnector) -> None:
        self._connectors[connector.platform_id] = connector

    def get(self, platform_id: str) -> PlatformConnector:
        if platform_id not in self._connectors:
            raise KeyError(f"Unknown platform connector: {platform_id}")
        return self._connectors[platform_id]

    def list_all(self) -> list[PlatformConnector]:
        return list(self._connectors.values())


registry = ConnectorRegistry()
registry.register(LinkedInConnector())
