import hashlib
import io
import random
import textwrap
import uuid
from pathlib import Path
from urllib.parse import quote
import httpx
from PIL import Image, ImageDraw, ImageFont
from app.config import UPLOADS_DIR
from app.core.ai_provider import generate_text


VISUAL_CONCEPTS: list[tuple[tuple[str, ...], str]] = [
    (
        ("retriev", "rerank", "chunk", "vector", "embed", "recall"),
        "abstract data retrieval pipeline: layered translucent documents, vector clusters and a glowing "
        "reranking gate, premium 3D render",
    ),
    (
        ("agent", "tool-call", "tool call", "stop condition", "loop"),
        "abstract autonomous agent loop: interconnected nodes joined by one clear termination gate, "
        "dark slate and electric blue, premium 3D render",
    ),
    (
        ("evaluat", "benchmark", "golden", "leakage", "score", "holdout"),
        "abstract evaluation landscape: precision-recall surfaces and separated holdout partitions, "
        "clean 3D render",
    ),
    (
        ("schema", "structured", "validat", "json", "parsing"),
        "abstract schema lattice: geometric blocks passing through validation gates, clean 3D render",
    ),
    (
        ("cost", "latency", "cache", "retry", "throughput"),
        "abstract latency and cost flow: parallel light streams through narrowing channels, "
        "premium 3D render",
    ),
    (
        ("stale", "reindex", "freshness", "refresh", "drift"),
        "abstract data pipeline with one fresh illuminated layer and one dimmed stale layer, "
        "premium 3D render",
    ),
    (
        ("fine-tun", "fine tun", "training", "dataset", "model size"),
        "abstract neural training stack: layered data partitions feeding a compact model core, "
        "premium 3D render",
    ),
    (
        ("career", "portfolio", "interview", "hiring", "resume"),
        "minimal editorial workspace: notebook, laptop edge, soft window light, no people, "
        "muted blue palette, editorial photograph",
    ),
    (
        ("rag", "context", "prompt", "context window"),
        "abstract context window: stacked translucent documents feeding a glowing core, "
        "premium 3D render",
    ),
]

DEFAULT_CONCEPT = (
    "abstract AI engineering system: modular blocks connected by clear data-flow lines, "
    "muted blue and slate palette, premium 3D render"
)


def _concept_for(post_content: str) -> str:
    text = post_content.lower()
    for keywords, scene in VISUAL_CONCEPTS:
        if any(keyword in text for keyword in keywords):
            return scene
    return DEFAULT_CONCEPT


STOCK_QUERIES: list[tuple[tuple[str, ...], str]] = [
    (("retriev", "rerank", "embed", "vector"), "abstract data network technology"),
    (("agent", "tool-call", "loop"), "network connections technology"),
    (("evaluat", "benchmark", "score", "holdout"), "data analytics charts"),
    (("schema", "structured", "validat", "json"), "geometric architecture abstract"),
    (("cost", "latency", "cache", "throughput"), "light trails motion abstract"),
    (("stale", "reindex", "freshness", "drift"), "server room data storage"),
    (("fine-tun", "training", "dataset", "model"), "neural network abstract"),
    (("career", "portfolio", "interview", "hiring"), "notebook laptop desk workspace"),
    (("rag", "context", "prompt"), "documents archive library"),
]


def _stock_query(post_content: str) -> str:
    text = post_content.lower()
    for keywords, query in STOCK_QUERIES:
        if any(keyword in text for keyword in keywords):
            return query
    return "technology abstract"


async def _openverse_photo(post_content: str, out_path: Path) -> bool:
    """Licensed real-photo fallback (CC0 / public domain, no API key)."""
    query = _stock_query(post_content)
    existing_hashes = set()
    for existing in UPLOADS_DIR.glob("post_*.jpg"):
        try:
            existing_hashes.add(hashlib.md5(existing.read_bytes()).hexdigest())
        except OSError:
            continue
    try:
        async with httpx.AsyncClient(timeout=25.0, headers={"User-Agent": "CareerOS/1.0"}) as client:
            resp = await client.get(
                "https://api.openverse.org/v1/images/",
                params={
                    "q": query,
                    "license": "cc0,pdm",
                    "page_size": 8,
                    "mature": "false",
                },
            )
            if resp.status_code != 200:
                return False
            candidates = [
                item
                for item in resp.json().get("results", [])
                if item.get("url") and (item.get("width") or 0) >= 1000 and (item.get("height") or 0) >= 500
            ]
            candidates.sort(key=lambda item: abs((item.get("width", 1) / max(1, item.get("height", 1))) - 1.91))
            if not candidates:
                return False
            start = int(hashlib.sha1(post_content.encode("utf-8")).hexdigest(), 16) % len(candidates)
            ordered = candidates[start:] + candidates[:start]
            for item in ordered[:5]:
                try:
                    image_resp = await client.get(item["url"], follow_redirects=True)
                    if image_resp.status_code != 200 or len(image_resp.content) < 20_000:
                        continue
                    if hashlib.md5(image_resp.content).hexdigest() in existing_hashes:
                        continue
                    _save_cover_jpeg(image_resp.content, out_path)
                    existing_hashes.add(hashlib.md5(image_resp.content).hexdigest())
                    return True
                except Exception:
                    continue
    except Exception:
        return False
    return False


async def craft_image_prompt(post_content: str, custom_prompt: str = "") -> str:
    if custom_prompt.strip():
        return custom_prompt.strip()
    try:
        prompt_text, _, _ = await generate_text(
            "You are an art director for a senior AI/ML engineer's LinkedIn post. "
            "Write a vivid, photorealistic, topic-specific 1-sentence scene description for an editorial photograph "
            "(include real people/engineers working, realistic environments, natural lighting, or real hardware/whiteboards "
            "relevant to the post topic—NOT abstract floating blocks or fake text). "
            "Return ONLY the 1-sentence visual scene description.",
            f"Post content:\n{post_content[:1500]}",
            temperature=0.5,
        )
        cleaned = prompt_text.strip().strip('"')
        if cleaned:
            return cleaned
    except Exception:
        pass
    return _concept_for(post_content)


def _render_local_card(title_text: str, subtitle_text: str, out_path: Path) -> None:
    """Offline fallback: renders a clean 1200x628 dark-slate LinkedIn visual card."""
    w, h = 1200, 628
    img = Image.new("RGB", (w, h), color=(11, 16, 32))
    draw = ImageDraw.Draw(img)

    # Subtle accent bar & border
    draw.rectangle([(40, 40), (w - 40, h - 40)], outline=(59, 130, 246), width=2)
    draw.rectangle([(40, 40), (54, h - 40)], fill=(59, 130, 246))

    font_lg = ImageFont.load_default(size=38)
    font_sm = ImageFont.load_default(size=24)

    wrapped_title = textwrap.fill(title_text[:110], width=42)
    wrapped_sub = textwrap.fill(subtitle_text[:220], width=62)

    draw.text((90, 110), wrapped_title, fill=(241, 245, 249), font=font_lg)
    draw.text((90, 270), wrapped_sub, fill=(148, 163, 184), font=font_sm)
    draw.text((90, h - 95), "Generated locally by CareerOS Agent", fill=(96, 165, 250), font=font_sm)

    img.save(out_path, format="PNG")


STYLE_SUFFIX = (
    " Photorealistic editorial photography, natural lighting, 35mm lens, shallow depth of field, "
    "authentic real-world setting, crisp detail, no text overlays, no watermarks, no logos."
)


def _save_cover_jpeg(
    raw: bytes, out_path: Path, width: int = 1200, height: int = 628, remove_bottom: int = 0
) -> None:
    """Normalise any generated image to a LinkedIn-friendly 1.91:1 JPEG."""
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    if remove_bottom:
        image = image.crop((0, 0, image.width, max(1, image.height - remove_bottom)))
    target_ratio = width / height
    source_ratio = image.width / image.height
    if source_ratio > target_ratio:
        new_width = int(image.height * target_ratio)
        left = (image.width - new_width) // 2
        image = image.crop((left, 0, left + new_width, image.height))
    elif source_ratio < target_ratio:
        new_height = int(image.width / target_ratio)
        top = (image.height - new_height) // 2
        image = image.crop((0, top, image.width, top + new_height))
    image = image.resize((width, height), Image.LANCZOS)
    image.save(out_path, format="JPEG", quality=88, optimize=True)


async def generate_post_image(
    post_content: str,
    custom_prompt: str = "",
    hf_token: str = "",
    allow_card_fallback: bool = True,
) -> tuple[str, str, str]:
    """
    Generates an image for a post and saves it in data/uploads/.
    Returns (filename, prompt_used, provider_used).
    """
    base_prompt = await craft_image_prompt(post_content, custom_prompt)
    prompt = (base_prompt.rstrip(". ") + "." + STYLE_SUFFIX).strip()
    filename = f"post_{uuid.uuid4().hex[:12]}.jpg"
    out_path = UPLOADS_DIR / filename

    # 1. Optional free-tier Hugging Face Inference API (FLUX.1-schnell)
    if hf_token.strip():
        hf_endpoints = [
            "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell",
            "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
        ]
        for hf_url in hf_endpoints:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        hf_url,
                        headers={"Authorization": f"Bearer {hf_token.strip()}"},
                        json={"inputs": prompt},
                    )
                    if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
                        _save_cover_jpeg(resp.content, out_path)
                        return filename, prompt, "huggingface:FLUX.1-schnell"
            except Exception:
                continue

    # 2. Free Pollinations AI image endpoint (FLUX, no API key needed)
    for _ in range(2):
        try:
            seed = random.randint(1, 2_000_000_000)
            url = (
                f"https://image.pollinations.ai/prompt/{quote(prompt)}"
                f"?width=1200&height=628&model=flux&nologo=true&enhance=true&seed={seed}"
            )
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                resp = await client.get(url)
            if resp.status_code == 200 and len(resp.content) > 5000:
                _save_cover_jpeg(resp.content, out_path, remove_bottom=58)
                return filename, prompt, "pollinations:flux"
        except Exception:
            continue

    # 3. Licensed real-photo fallback (Openverse, CC0/public domain)
    if await _openverse_photo(post_content, out_path):
        return filename, prompt, "openverse:cc0"

    if not allow_card_fallback:
        return "", prompt, "none"

    # 4. Optional local Pillow visual card fallback
    lines = [ln.strip() for ln in post_content.splitlines() if ln.strip()]
    headline = lines[0] if lines else "AI Engineering Update"
    body = " ".join(lines[1:]) if len(lines) > 1 else prompt
    _render_local_card(headline, body, out_path)
    return filename, prompt, "local:pillow-card"
