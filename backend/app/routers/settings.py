from fastapi import APIRouter
from app.core.ai_provider import check_ollama_status, get_ai_config, save_ai_config
from app.models.schemas import AISettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def read_settings():
    cfg = get_ai_config()
    ollama = await check_ollama_status()
    return {
        "ai_provider": cfg["ai_provider"],
        "ollama_base_url": cfg["ollama_base_url"],
        "ollama_model": cfg["ollama_model"],
        "external_ai_base_url": cfg["external_ai_base_url"],
        "external_ai_model": cfg["external_ai_model"],
        "has_external_api_key": bool(cfg["external_ai_api_key"]),
        "has_hf_token": bool(cfg["hf_token"]),
        "is_external": cfg["is_external"],
        "ollama_status": ollama,
    }


@router.put("")
async def update_settings(body: AISettingsUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    save_ai_config(updates)
    return await read_settings()
