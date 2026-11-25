from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ConnectorCapabilities:
    can_publish_post: bool = False
    can_comment: bool = False
    can_read_profile: bool = False
    can_search_jobs: bool = False
    notes: str = ""


@dataclass
class PublishResult:
    success: bool
    manual_required: bool = False
    external_id: str = ""
    external_url: str = ""
    message: str = ""


@dataclass
class AuthStatus:
    platform: str
    display_name: str
    connected: bool
    configured: bool
    account_label: str = ""
    external_user_id: str = ""
    scopes: list[str] = field(default_factory=list)
    capabilities: ConnectorCapabilities = field(default_factory=ConnectorCapabilities)


class PlatformConnector(ABC):
    platform_id: str = ""
    display_name: str = ""
    description: str = ""

    @abstractmethod
    def capabilities(self) -> ConnectorCapabilities:
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    def get_auth_status(self) -> AuthStatus:
        ...

    def get_oauth_url(self, state: str) -> str:
        raise NotImplementedError(f"{self.display_name} does not implement OAuth.")

    async def handle_oauth_callback(self, code: str) -> AuthStatus:
        raise NotImplementedError(f"{self.display_name} does not implement OAuth.")

    def disconnect(self) -> None:
        raise NotImplementedError(f"{self.display_name} does not implement disconnect.")

    async def publish_post(self, content: str, idempotency_key: str, image_path: str = "") -> PublishResult:
        return PublishResult(
            success=False,
            manual_required=True,
            message=f"Direct publishing is not supported for {self.display_name}. Copy the text and publish manually.",
        )

    async def post_comment(
        self,
        target_url: str,
        target_urn: str,
        content: str,
        idempotency_key: str,
    ) -> PublishResult:
        return PublishResult(
            success=False,
            manual_required=True,
            external_url=target_url,
            message=f"Direct commenting is not supported for {self.display_name}. Copy the reply and open the link.",
        )
