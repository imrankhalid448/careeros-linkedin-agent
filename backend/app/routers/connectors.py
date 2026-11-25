import secrets
from dataclasses import asdict
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from app.config import settings
from app.connectors.registry import registry

router = APIRouter(prefix="/api/connectors", tags=["connectors"])

_OAUTH_STATES: set[str] = set()


@router.get("")
def list_connectors():
    return [
        {
            **asdict(c.get_auth_status()),
            "description": c.description,
        }
        for c in registry.list_all()
    ]


@router.get("/{platform_id}/connect")
def start_oauth(platform_id: str):
    try:
        connector = registry.get(platform_id)
        state = secrets.token_urlsafe(24)
        _OAUTH_STATES.add(state)
        url = connector.get_oauth_url(state)
        return {"auth_url": url}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{platform_id}/callback")
async def oauth_callback(platform_id: str, code: str = "", state: str = "", error: str = ""):
    if error:
        return RedirectResponse(f"{settings.frontend_url}?oauth_error={error}")
    if state not in _OAUTH_STATES:
        raise HTTPException(status_code=400, detail="Invalid OAuth state.")
    _OAUTH_STATES.discard(state)

    connector = registry.get(platform_id)
    await connector.handle_oauth_callback(code)
    return RedirectResponse(f"{settings.frontend_url}?connected={platform_id}")


@router.post("/{platform_id}/disconnect")
def disconnect_platform(platform_id: str):
    connector = registry.get(platform_id)
    connector.disconnect()
    return {"disconnected": True, "platform": platform_id}
