import json
import re
from typing import Any
import httpx
from app.config import settings
from app.database import db_session


def get_ai_config() -> dict[str, Any]:
    with db_session() as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    saved = {r["key"]: r["value"] for r in rows}
    provider = saved.get("ai_provider", settings.ai_provider)
    return {
        "ai_provider": provider,
        "ollama_base_url": saved.get("ollama_base_url", settings.ollama_base_url),
        "ollama_model": saved.get("ollama_model", settings.ollama_model),
        "external_ai_base_url": saved.get("external_ai_base_url", settings.external_ai_base_url),
        "external_ai_model": saved.get("external_ai_model", settings.external_ai_model),
        "external_ai_api_key": saved.get("external_ai_api_key", settings.external_ai_api_key),
        "hf_token": saved.get("hf_token", settings.hf_token),
        "is_external": provider != "ollama",
    }


def save_ai_config(updates: dict[str, str]) -> dict[str, Any]:
    allowed = {
        "ai_provider",
        "ollama_base_url",
        "ollama_model",
        "external_ai_base_url",
        "external_ai_model",
        "external_ai_api_key",
        "hf_token",
    }
    with db_session() as conn:
        for key, value in updates.items():
            if key in allowed and value is not None:
                conn.execute(
                    """
                    INSERT INTO app_settings (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, str(value)),
                )
    return get_ai_config()


async def check_ollama_status() -> dict[str, Any]:
    cfg = get_ai_config()
    url = cfg["ollama_base_url"].rstrip("/") + "/api/tags"
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            return {"running": True, "models": models, "selected_model": cfg["ollama_model"]}
    except Exception as exc:
        return {"running": False, "models": [], "selected_model": cfg["ollama_model"], "error": str(exc)}


async def generate_text(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
) -> tuple[str, str, bool]:
    """
    Returns (response_text, provider_label, is_external).
    """
    cfg = get_ai_config()
    provider = cfg["ai_provider"]

    if provider == "ollama":
        url = cfg["ollama_base_url"].rstrip("/") + "/api/chat"
        payload = {
            "model": cfg["ollama_model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": 1024},
        }
        try:
            # Local 7B models can take several minutes on CPU/partial GPU offload.
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                text = data.get("message", {}).get("content", "").strip()
                return text, f"ollama:{cfg['ollama_model']}", False
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot connect to local Ollama at {cfg['ollama_base_url']}. "
                f"Start Ollama and make sure model '{cfg['ollama_model']}' is pulled (`ollama pull {cfg['ollama_model']}`)."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc

    # Optional external OpenAI-compatible provider
    api_key = cfg.get("external_ai_api_key", "").strip()
    if not api_key:
        raise RuntimeError("External AI provider selected, but no API key is configured.")

    url = cfg["external_ai_base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": cfg["external_ai_model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        return text, f"external:{cfg['external_ai_model']}", True


def extract_json_block(raw_text: str) -> dict[str, Any]:
    """Safely extract a JSON object from an LLM response."""
    cleaned = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    else:
        brace_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if brace_match:
            cleaned = brace_match.group(1)
    return json.loads(cleaned)
