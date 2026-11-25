import mimetypes
import re
import time
from pathlib import Path
from urllib.parse import urlencode
import httpx
from app.config import UPLOADS_DIR, settings
from app.connectors.base import (
    AuthStatus,
    ConnectorCapabilities,
    PlatformConnector,
    PublishResult,
)
from app.core.security import (
    delete_platform_credentials,
    load_platform_credentials,
    save_platform_credentials,
)


def extract_linkedin_post_urn(url_or_urn: str) -> str:
    text = (url_or_urn or "").strip()
    if text.startswith("urn:li:"):
        return text
    activity_match = re.search(r"(urn:li:(?:activity|ugcPost|share):\d+)", text)
    if activity_match:
        return activity_match.group(1)
    digits_match = re.search(r"activity-(\d+)", text)
    if digits_match:
        return f"urn:li:activity:{digits_match.group(1)}"
    return ""


def _normalize_scopes(value: object) -> list[str]:
    """LinkedIn returns scopes either space- or comma-separated, sometimes as one string."""
    if not value:
        return []
    items = [value] if isinstance(value, str) else list(value)
    scopes: list[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        for part in re.split(r"[\s,]+", item):
            if part and part not in scopes:
                scopes.append(part)
    return scopes


class LinkedInConnector(PlatformConnector):
    platform_id = "linkedin"
    display_name = "LinkedIn"
    description = "Official LinkedIn OAuth 2.0 + REST API (Share on LinkedIn & OpenID Connect)."

    SCOPES = ["openid", "profile", "email", "w_member_social"]

    def capabilities(self) -> ConnectorCapabilities:
        creds = load_platform_credentials(self.platform_id)
        scopes = _normalize_scopes(creds.get("scopes")) if creds else []
        has_social = "w_member_social" in scopes
        has_feed = "w_member_social_feed" in scopes
        return ConnectorCapabilities(
            can_publish_post=has_social,
            can_comment=has_feed,
            can_read_profile=False,
            can_search_jobs=False,
            notes=(
                "Official self-serve API supports publishing posts (w_member_social) and OpenID identity. "
                "Reading comments, replying to comments and job search require LinkedIn partner access "
                "(Community Management API / r_member_social_feed); LinkedIn returns 403 without it."
            ),
        )

    def is_configured(self) -> bool:
        return bool(settings.linkedin_client_id.strip() and settings.linkedin_client_secret.strip())

    def get_auth_status(self) -> AuthStatus:
        creds = load_platform_credentials(self.platform_id)
        connected = bool(creds and creds["payload"].get("access_token"))
        return AuthStatus(
            platform=self.platform_id,
            display_name=self.display_name,
            connected=connected,
            configured=self.is_configured(),
            account_label=creds["account_label"] if creds else "",
            external_user_id=creds["external_user_id"] if creds else "",
            scopes=_normalize_scopes(creds["scopes"]) if creds else [],
            capabilities=self.capabilities(),
        )

    def get_oauth_url(self, state: str) -> str:
        if not self.is_configured():
            raise RuntimeError(
                "LinkedIn Client ID / Secret not configured in .env. Add LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET."
            )
        params = {
            "response_type": "code",
            "client_id": settings.linkedin_client_id,
            "redirect_uri": settings.linkedin_redirect_uri,
            "state": state,
            "scope": " ".join(self.SCOPES),
        }
        return f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"

    async def handle_oauth_callback(self, code: str) -> AuthStatus:
        if not self.is_configured():
            raise RuntimeError("LinkedIn Client ID / Secret not configured.")

        async with httpx.AsyncClient(timeout=20.0) as client:
            token_resp = await client.post(
                "https://www.linkedin.com/oauth/v2/accessToken",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.linkedin_redirect_uri,
                    "client_id": settings.linkedin_client_id,
                    "client_secret": settings.linkedin_client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
            access_token = token_data["access_token"]
            expires_in = int(token_data.get("expires_in", 5184000))
            granted_scopes = _normalize_scopes(token_data.get("scope") or self.SCOPES)

            userinfo_resp = await client.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_resp.raise_for_status()
            userinfo = userinfo_resp.json()

        person_id = userinfo.get("sub", "")
        person_urn = f"urn:li:person:{person_id}" if person_id else ""
        account_label = userinfo.get("name") or userinfo.get("email") or person_urn

        save_platform_credentials(
            platform=self.platform_id,
            payload={
                "access_token": access_token,
                "expires_at": int(time.time()) + expires_in,
                "person_urn": person_urn,
            },
            account_label=account_label,
            external_user_id=person_urn,
            scopes=granted_scopes,
        )
        return self.get_auth_status()

    def disconnect(self) -> None:
        delete_platform_credentials(self.platform_id)

    def _get_active_token_and_urn(self) -> tuple[str, str, list[str]]:
        creds = load_platform_credentials(self.platform_id)
        if not creds:
            raise RuntimeError("LinkedIn is not connected. Connect your account in Connectors first.")
        payload = creds["payload"]
        access_token = payload.get("access_token", "")
        person_urn = payload.get("person_urn", "")
        expires_at = int(payload.get("expires_at", 0))
        if not access_token or not person_urn:
            raise RuntimeError("Stored LinkedIn credentials are incomplete. Reconnect your account.")
        if expires_at and time.time() > expires_at:
            raise RuntimeError("LinkedIn OAuth token has expired. Please reconnect in Connectors.")
        return access_token, person_urn, _normalize_scopes(creds.get("scopes"))

    async def fetch_identity(self) -> dict[str, str]:
        """Fetch the connected member's verified OpenID identity.

        LinkedIn only exposes name, email and picture through the self-serve
        OpenID Connect scopes; headline/about/skills are not available to apps.
        """
        access_token, person_urn, _ = self._get_active_token_and_urn()
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            userinfo = resp.json()

            profile_url = ""
            try:
                me = await client.get(
                    "https://api.linkedin.com/v2/me",
                    headers=self._rest_headers(access_token),
                )
                if me.status_code == 200:
                    vanity = (me.json() or {}).get("vanityName", "")
                    if vanity:
                        profile_url = f"https://www.linkedin.com/in/{vanity}"
            except Exception:
                profile_url = ""

        return {
            "name": userinfo.get("name", ""),
            "given_name": userinfo.get("given_name", ""),
            "family_name": userinfo.get("family_name", ""),
            "email": userinfo.get("email", ""),
            "picture": userinfo.get("picture", ""),
            "locale": userinfo.get("locale", ""),
            "subject": userinfo.get("sub", ""),
            "person_urn": person_urn,
            "profile_url": profile_url,
        }

    def _rest_headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Linkedin-Version": settings.linkedin_api_version,
            "X-Restli-Protocol-Version": "2.0.0",
        }

    async def _upload_image(self, access_token: str, person_urn: str, file_path: Path) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            init_resp = await client.post(
                "https://api.linkedin.com/rest/images?action=initializeUpload",
                headers=self._rest_headers(access_token),
                json={"initializeUploadRequest": {"owner": person_urn}},
            )
            init_resp.raise_for_status()
            val = init_resp.json()["value"]
            upload_url = val["uploadUrl"]
            image_urn = val["image"]

            mime_type = mimetypes.guess_type(str(file_path))[0] or "image/png"
            put_resp = await client.put(
                upload_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": mime_type,
                },
                content=file_path.read_bytes(),
            )
            put_resp.raise_for_status()
            return image_urn

    async def publish_post(self, content: str, idempotency_key: str, image_path: str = "") -> PublishResult:
        try:
            access_token, person_urn, scopes = self._get_active_token_and_urn()
        except RuntimeError as exc:
            return PublishResult(success=False, manual_required=True, message=str(exc))

        if "w_member_social" not in scopes:
            return PublishResult(
                success=False,
                manual_required=True,
                message="Connected LinkedIn token lacks 'w_member_social' scope. Enable 'Share on LinkedIn' in your Developer App and reconnect.",
            )

        media_urn = ""
        if image_path:
            full_path = UPLOADS_DIR / image_path
            if full_path.exists():
                try:
                    media_urn = await self._upload_image(access_token, person_urn, full_path)
                except Exception as exc:
                    return PublishResult(
                        success=False,
                        manual_required=False,
                        message=f"LinkedIn image upload failed: {exc}",
                    )

        body = {
            "author": person_urn,
            "commentary": content,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if media_urn:
            body["content"] = {"media": {"id": media_urn}}

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.linkedin.com/rest/posts",
                headers=self._rest_headers(access_token),
                json=body,
            )

        if resp.status_code in (200, 201):
            post_urn = resp.headers.get("x-restli-id", "") or resp.headers.get("X-RestLi-Id", "")
            post_url = f"https://www.linkedin.com/feed/update/{post_urn}/" if post_urn else ""
            return PublishResult(
                success=True,
                external_id=post_urn,
                external_url=post_url,
                message="Published to LinkedIn.",
            )

        return PublishResult(
            success=False,
            manual_required=False,
            message=f"LinkedIn API error ({resp.status_code}): {resp.text}",
        )

    async def post_comment(
        self,
        target_url: str,
        target_urn: str,
        content: str,
        idempotency_key: str,
    ) -> PublishResult:
        resolved_urn = target_urn.strip() or extract_linkedin_post_urn(target_url)
        if not resolved_urn:
            return PublishResult(
                success=False,
                manual_required=True,
                external_url=target_url,
                message="Could not determine LinkedIn post URN from the link. Copy your reply and post it directly on LinkedIn.",
            )

        try:
            access_token, person_urn, scopes = self._get_active_token_and_urn()
        except RuntimeError as exc:
            return PublishResult(success=False, manual_required=True, external_url=target_url, message=str(exc))

        if "w_member_social" not in scopes:
            return PublishResult(
                success=False,
                manual_required=True,
                external_url=target_url,
                message="Connected account lacks w_member_social permission. Copy the reply and open the LinkedIn post.",
            )

        body = {
            "actor": person_urn,
            "message": {"text": content},
        }
        encoded_urn = resolved_urn.replace(":", "%3A")
        url = f"https://api.linkedin.com/rest/socialActions/{encoded_urn}/comments"

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=self._rest_headers(access_token), json=body)

        if resp.status_code in (200, 201):
            comment_id = resp.headers.get("x-restli-id", "")
            return PublishResult(
                success=True,
                external_id=comment_id,
                external_url=target_url,
                message="Comment published to LinkedIn.",
            )

        return PublishResult(
            success=False,
            manual_required=True,
            external_url=target_url,
            message=(
                f"LinkedIn restricted live commenting for this post ({resp.status_code}). "
                "Your final reply is ready—copy it and open the link to comment."
            ),
        )
