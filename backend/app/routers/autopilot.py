import asyncio

from fastapi import APIRouter

from app.models.schemas import AutopilotUpdate
from app.services.autopilot_service import get_status, queue_autopilot_posts, save_settings

router = APIRouter(prefix="/api/autopilot", tags=["autopilot"])


@router.get("")
def read_autopilot():
    return get_status()


@router.put("")
async def update_autopilot(body: AutopilotUpdate):
    settings = save_settings(
        enabled=body.enabled,
        auto_publish=body.auto_publish,
        posts_per_day=body.posts_per_day,
        timezone_name=body.timezone,
        slots=body.slots,
    )
    if settings["enabled"]:
        asyncio.create_task(queue_autopilot_posts())
    return get_status()


@router.post("/queue")
async def queue_now(limit: int = 1):
    asyncio.create_task(queue_autopilot_posts(force=True, max_generate=max(1, min(5, limit))))
    await asyncio.sleep(0)
    return {
        "ok": True,
        "message": "Autopilot is drafting the next post. This usually takes about a minute.",
    }
