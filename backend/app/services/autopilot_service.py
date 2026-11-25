"""Daily LinkedIn growth autopilot.

Generates a rotating set of grounded posts, schedules them at proven
professional-audience windows, and lets the existing due-post publisher send
them through the LinkedIn connector.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from app.core.ai_provider import generate_text, get_ai_config
from app.core.image_provider import generate_post_image
from app.database import db_session
from app.services.profile_service import GROUNDING_RULE, get_profile, list_project_notes

DEFAULT_TIMEZONE = "Asia/Karachi"
DEFAULT_SLOTS = ["09:00"]
SLOT_PRESETS = {
    1: ["09:00"],
    2: ["09:00", "17:30"],
    3: ["09:00", "13:00", "19:00"],
    4: ["08:30", "12:30", "17:30", "21:00"],
    5: ["08:00", "11:30", "14:30", "17:30", "21:00"],
}
DEFAULT_POSTS_PER_DAY = 1

PILLARS: list[dict[str, str]] = [
    {
        "key": "production",
        "name": "Production lessons",
        "summary": "One hard-won lesson from shipping AI systems, with the trade-off made explicit.",
        "prompt": (
            "Describe a general failure pattern you have seen in production AI systems, the naive fix, "
            "and the trade-off that actually worked. Do not invent a specific client or deployment."
        ),
    },
    {
        "key": "teardown",
        "name": "Build teardown",
        "summary": "How a component actually works: retrieval, evaluation, serving, data pipelines.",
        "prompt": (
            "Take a position on one design trade-off in a modern AI system: retrieval, evaluation, serving "
            "or data. Use a concrete mechanism, the failure mode it prevents, and when it is the wrong choice. "
            "Write for practitioners, not beginners. Do not write a tutorial or explain basic definitions."
        ),
    },
    {
        "key": "signal",
        "name": "Industry signal",
        "summary": "A grounded take on a fresh AI headline, focused on what builders should do differently.",
        "prompt": (
            "React to a current AI industry story. Summarise the relevant fact in one sentence, then give a "
            "practical engineering perspective. Do not pretend to have read beyond the provided summary."
        ),
    },
    {
        "key": "career",
        "name": "Career & hiring",
        "summary": "Portfolio, interviewing or skill-building advice that respects the reader's time.",
        "prompt": (
            "Give one concrete piece of career advice for AI/ML engineers: portfolio proof, interview prep, "
            "or choosing what to learn next. Be specific and avoid generic motivation."
        ),
    },
    {
        "key": "myth",
        "name": "Myth vs reality",
        "summary": "Correct a common misconception with evidence from real engineering practice.",
        "prompt": (
            "Take one common misconception about LLMs, RAG, computer vision or MLOps and correct it with a "
            "practical example. Be fair to why the misconception exists."
        ),
    },
    {
        "key": "toolbox",
        "name": "Toolbox",
        "summary": "A tool, library or workflow that measurably improved how you build.",
        "prompt": (
            "Recommend one tool, library or workflow for AI engineering. Explain the problem it solves, "
            "when not to use it, and one caveat. No affiliate tone."
        ),
    },
    {
        "key": "question",
        "name": "Reflection & question",
        "summary": "A short reflective post that invites experienced practitioners to compare notes.",
        "prompt": (
            "Write a short reflective post about an open question in AI engineering. State your current "
            "view, acknowledge the uncertainty, and invite readers to share their experience."
        ),
    },
]

PILLAR_ANGLES = {
    "production": [
        "silent retrieval misses",
        "stale indexes after a data refresh",
        "context window overflow",
        "tool-call loops in agents",
        "cost blowups from retry storms",
        "evaluation leakage between train and test sets",
    ],
    "teardown": [
        "chunk boundaries and metadata",
        "hybrid search with exact-term matching",
        "reranking the top candidates",
        "query rewriting before retrieval",
        "golden evaluation sets",
        "grounding checks before generation",
        "prompt caching and batching",
        "structured outputs with schema validation",
    ],
    "signal": [
        "what the headline changes for builders",
        "the cost or latency implication",
        "the evaluation question it raises",
        "who should ignore the announcement",
    ],
    "career": [
        "one portfolio project with real constraints",
        "how to describe trade-offs in interviews",
        "what to learn after RAG basics",
        "how to show evaluation thinking",
    ],
    "myth": [
        "bigger models fix bad retrieval",
        "more agents mean more capability",
        "fine-tuning replaces evaluation",
        "vector search is enough on its own",
        "prompt engineering is the main lever",
    ],
    "toolbox": [
        "an evaluation harness",
        "a tracing tool for LLM calls",
        "a reranker",
        "a schema validator",
        "a small local model for cheap classification",
    ],
    "question": [
        "when to fine-tune versus retrieve",
        "how much evaluation is enough",
        "where agents still fail in production",
        "how to price AI features",
    ],
}

VOICE_RULES = (
    "Voice: short declarative sentences. Open with a claim, never a definition. One idea per paragraph. "
    "Concrete nouns and mechanisms. No hype, no motivational coaching, no textbook explanations. "
    "A reader who ships AI systems should learn one specific thing they can apply this week."
)

ANGLE_NOTES: dict[str, str] = {
    "silent retrieval misses": (
        "Measure retrieval recall@k before tuning generation. Hybrid search (BM25 plus embeddings) "
        "and a cross-encoder reranker usually recover misses. Reranking adds latency and cannot fix "
        "an index that never contained the document."
    ),
    "stale indexes after a data refresh": (
        "Reindex incrementally when sources change, version embeddings, and monitor freshness. Full "
        "rebuilds are simple but expensive; incremental jobs fail silently without checks."
    ),
    "context window overflow": (
        "Budget tokens per section, compress history, and keep system constraints pinned. Truncation "
        "silently drops the instructions or evidence that mattered most."
    ),
    "tool-call loops in agents": (
        "Cap iterations, deduplicate calls by tool plus arguments, and require an explicit stop "
        "condition. Prompt caching lowers the cost of a loop but does not stop it."
    ),
    "cost blowups from retry storms": (
        "Cap retries, add jittered backoff, cache idempotent calls, and route simple requests to a "
        "smaller model. Aggressive caching risks stale or cross-user answers."
    ),
    "evaluation leakage between train and test sets": (
        "Split by document and time rather than random rows. Deduplicate near-identical examples, or "
        "the score mostly reflects memorisation."
    ),
    "chunk boundaries and metadata": (
        "Chunk by section and keep the heading with every chunk; overlap only when a sentence spans "
        "a boundary. Smaller chunks raise recall but lose surrounding context."
    ),
    "hybrid search with exact-term matching": (
        "Combine BM25 for exact names and codes with dense embeddings for paraphrase. Fusion needs "
        "score normalisation and a second index to maintain."
    ),
    "reranking the top candidates": (
        "Retrieve 20 to 50 candidates cheaply, then rerank that group with a cross-encoder. Adds tens "
        "of milliseconds; reranking cannot recover an answer absent from the candidate set."
    ),
    "query rewriting before retrieval": (
        "Rewrite conversational follow-ups into standalone queries before retrieval. It adds a model "
        "call and can drift from user intent, so log the rewrites."
    ),
    "golden evaluation sets": (
        "Hold out queries written by someone who has not tuned the system. Score retrieval recall and "
        "answer groundedness separately, and refresh the set when the domain shifts."
    ),
    "grounding checks before generation": (
        "Verify claims against retrieved spans and abstain when support is missing. This adds latency "
        "and can over-block legitimate answers, so measure refusal rate."
    ),
    "prompt caching and batching": (
        "Cache stable prefixes and repeated retrieval context, and batch offline work. Invalidation is "
        "the hard part; stale cache is worse than no cache."
    ),
    "structured outputs with schema validation": (
        "Constrain decoding to a schema and validate server-side. Schemas reduce parsing errors, not "
        "reasoning errors."
    ),
    "what the headline changes for builders": (
        "Use only the provided headline and summary. Separate the announced fact from your inference, "
        "and do not invent benchmarks or adoption numbers."
    ),
    "the cost or latency implication": (
        "Use only the provided summary. Reason about cost and latency qualitatively; do not invent "
        "pricing or benchmark figures."
    ),
    "the evaluation question it raises": (
        "Use only the provided summary and focus on what teams should measure before adopting it."
    ),
    "who should ignore the announcement": (
        "Use only the provided summary. Be explicit about which teams should not change course yet."
    ),
    "one portfolio project with real constraints": (
        "One project with real constraints, a small evaluation, a failure analysis and next steps "
        "beats many tutorials. Do not invent the author's results."
    ),
    "how to describe trade-offs in interviews": (
        "Structure answers as constraint, options, decision, measured result, and what you would "
        "change. Do not invent the author's numbers."
    ),
    "what to learn after RAG basics": (
        "Focus on evaluation, retrieval quality, latency and cost control, and deployment. Avoid "
        "listing every framework."
    ),
    "how to show evaluation thinking": (
        "Show a small evaluation set, a failure taxonomy and how changes were compared. Keep it "
        "concrete and modest."
    ),
    "bigger models fix bad retrieval": (
        "Model size does not recover documents the retriever never returned. Measure recall before "
        "switching models."
    ),
    "more agents mean more capability": (
        "Additional agents add coordination and failure modes. Start with one tool-using loop and "
        "add agents only for separable responsibilities."
    ),
    "fine-tuning replaces evaluation": (
        "Fine-tuning changes behaviour and style; it does not add missing knowledge. Keep an "
        "evaluation set for both."
    ),
    "vector search is enough on its own": (
        "Exact identifiers, product codes and rare names need lexical matching. Hybrid retrieval "
        "covers both."
    ),
    "prompt engineering is the main lever": (
        "Prompts matter, but retrieval quality, data and evaluation usually dominate outcomes. Say "
        "where prompt changes stop helping."
    ),
    "an evaluation harness": (
        "An evaluation harness runs a fixed set of cases and compares outputs across changes. It "
        "catches regressions but only for cases you wrote down."
    ),
    "a tracing tool for LLM calls": (
        "Tracing records prompts, retrieval context, tool calls and latency per request. It helps "
        "debug production failures but adds storage and privacy obligations."
    ),
    "a reranker": (
        "A cross-encoder reranker reorders a candidate set by query relevance. It improves precision "
        "at a latency cost and cannot recover missing candidates."
    ),
    "a schema validator": (
        "Schema validation rejects malformed structured output before it reaches downstream code. "
        "It cannot fix wrong values that still satisfy the schema."
    ),
    "a small local model for cheap classification": (
        "A small local model can handle routing and classification at low cost and with data "
        "residency. Expect lower accuracy on edge cases; keep a fallback."
    ),
    "when to fine-tune versus retrieve": (
        "Fine-tune for behaviour and format, retrieve for changing facts. State the trade-off in "
        "maintenance cost."
    ),
    "how much evaluation is enough": (
        "Enough evaluation covers the failure modes that would hurt users, not every possible input. "
        "Be concrete about coverage."
    ),
    "where agents still fail in production": (
        "Agents fail on ambiguous goals, tool errors, and missing stop conditions. Invite specific "
        "failure stories."
    ),
    "how to price AI features": (
        "Price against token and retrieval cost per successful task, not per request. Acknowledge "
        "uncertainty."
    ),
}

WEEKLY_FOCUS = {
    0: "production",
    1: "signal",
    2: "teardown",
    3: "career",
    4: "myth",
    5: "toolbox",
    6: "question",
}

NEWS_FEEDS = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
]

BEST_TIMES_NOTE = (
    "Weekday mornings and early afternoons in your audience's timezone perform best for professional "
    "audiences. These slots are planned in Asia/Karachi so they overlap Europe's morning and the US "
    "East Coast's working day: 08:30 (PKT morning), 12:30 (Europe morning), 17:30 (US morning), "
    "21:00 (US midday). Tuesday to Thursday carry the highest engagement, so the strongest technical "
    "posts are rotated into those days."
)

_LOCK = asyncio.Lock()
_STATE: dict[str, Any] = {"running": False, "last_error": "", "last_generated_at": "", "last_run_at": ""}


def _setting(key: str, default: str = "") -> str:
    with db_session() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def _save_setting(key: str, value: str) -> None:
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def _tz(name: str):
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone(timedelta(hours=5), "PKT")


def get_settings() -> dict[str, Any]:
    enabled = _setting("autopilot_enabled", "1") not in ("0", "false", "False", "")
    auto_publish = _setting("autopilot_auto_publish", "1") not in ("0", "false", "False", "")
    try:
        posts_per_day = int(_setting("autopilot_posts_per_day", str(DEFAULT_POSTS_PER_DAY)))
    except ValueError:
        posts_per_day = DEFAULT_POSTS_PER_DAY
    posts_per_day = max(1, min(5, posts_per_day))
    tz_name = _setting("autopilot_timezone", DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE
    saved_slots = _setting("autopilot_slots", "")
    slots = SLOT_PRESETS.get(posts_per_day, DEFAULT_SLOTS)
    if saved_slots:
        try:
            parsed = json.loads(saved_slots)
            if isinstance(parsed, list) and parsed:
                valid = [s for s in parsed if re.fullmatch(r"\d{2}:\d{2}", str(s))]
                if valid:
                    slots = valid[:5]
        except json.JSONDecodeError:
            pass
    return {
        "enabled": enabled,
        "auto_publish": auto_publish,
        "posts_per_day": posts_per_day,
        "timezone": tz_name,
        "slots": slots,
    }


def save_settings(
    *,
    enabled: bool | None = None,
    auto_publish: bool | None = None,
    posts_per_day: int | None = None,
    timezone_name: str | None = None,
    slots: list[str] | None = None,
) -> dict[str, Any]:
    if enabled is not None:
        _save_setting("autopilot_enabled", "1" if enabled else "0")
    if auto_publish is not None:
        _save_setting("autopilot_auto_publish", "1" if auto_publish else "0")
    if posts_per_day is not None:
        count = max(1, min(5, posts_per_day))
        _save_setting("autopilot_posts_per_day", str(count))
        _save_setting("autopilot_slots", json.dumps(SLOT_PRESETS.get(count, DEFAULT_SLOTS)))
    if timezone_name:
        _save_setting("autopilot_timezone", timezone_name)
    if slots:
        valid = [s for s in slots if re.fullmatch(r"\d{2}:\d{2}", s)]
        if valid:
            _save_setting("autopilot_slots", json.dumps(valid[:5]))
            _save_setting("autopilot_posts_per_day", str(min(5, max(3, len(valid)))))

    if auto_publish is not None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with db_session() as conn:
            if auto_publish:
                conn.execute(
                    """
                    UPDATE posts SET status = 'scheduled'
                    WHERE source_type = 'autopilot' AND status = 'draft'
                      AND scheduled_for != '' AND scheduled_for >= ?
                    """,
                    (now_iso,),
                )
            else:
                conn.execute(
                    """
                    UPDATE posts SET status = 'draft'
                    WHERE source_type = 'autopilot' AND status = 'scheduled'
                      AND scheduled_for >= ?
                    """,
                    (now_iso,),
                )
    return get_settings()


def _local_now(settings: dict[str, Any] | None = None) -> datetime:
    settings = settings or get_settings()
    return datetime.now(_tz(settings["timezone"]))


def _upcoming_slots(settings: dict[str, Any], limit: int = 6) -> list[datetime]:
    tz = _tz(settings["timezone"])
    now = datetime.now(tz)
    result: list[datetime] = []
    for day_offset in range(0, 4):
        day = (now + timedelta(days=day_offset)).date()
        for slot in settings["slots"]:
            hour, minute = (int(part) for part in slot.split(":"))
            candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
            if candidate <= now + timedelta(minutes=1):
                continue
            result.append(candidate)
            if len(result) >= limit:
                return result
    return result


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(second=0, microsecond=0).isoformat()


def _pillar_for(slot: datetime, settings: dict[str, Any]) -> dict[str, str]:
    slot_index = settings["slots"].index(slot.strftime("%H:%M")) if slot.strftime("%H:%M") in settings["slots"] else 0
    focus_key = WEEKLY_FOCUS.get(slot.weekday(), "production")
    focus_index = next((i for i, p in enumerate(PILLARS) if p["key"] == focus_key), 0)
    return PILLARS[(focus_index + slot_index) % len(PILLARS)]


STOPWORDS = set(
    "their there about which would could should while where when what have with this that from into "
    "your you they them than then also more most much many some such only over under between during "
    "before after above below again further once here both each few other same own because until "
    "against among within without through being been were was are is it its it's you're don't doesn't "
    "can't cannot will just make makes made using used use very really still even every"
    .split()
)


def _keywords(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z][a-z0-9-]{4,}", text.lower())
        if word not in STOPWORDS
    }


def _similarity(left: str, right: str) -> float:
    a, b = _keywords(left), _keywords(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _too_similar(text: str, recent: list[str]) -> str:
    for previous in recent:
        if _similarity(text, previous) >= 0.32:
            return previous[:160]
    return ""


def _pick_angle(
    pillar: dict[str, str], slot: datetime, recent: list[str], exclude: str = ""
) -> str:
    angles = PILLAR_ANGLES.get(pillar["key"], ["one concrete engineering trade-off"])
    blob = " ".join(recent).lower()
    candidates = []
    for angle in angles:
        if angle == exclude:
            continue
        keywords = _keywords(angle)
        hits = sum(1 for word in keywords if word in blob)
        if keywords and hits >= max(1, len(keywords) // 2):
            continue
        candidates.append(angle)
    pool = candidates or [angle for angle in angles if angle != exclude] or angles
    return pool[(slot.toordinal() + int(slot.strftime("%H%M"))) % len(pool)]


def _recent_posts(limit: int = 12) -> list[str]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT content FROM posts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [row["content"] for row in rows]


def _clean_post(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:markdown|text)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("__", "")
    cleaned = re.sub(r"^#{1,6}[ \t]+", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip().strip('"').strip("'").strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    tags = re.findall(r"#[A-Za-z][A-Za-z0-9]*", cleaned)
    if len(tags) > 3:
        for extra in tags[3:]:
            cleaned = cleaned.replace(extra, "")
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    elif not tags:
        cleaned = cleaned.rstrip() + "\n\n#AI #GenAI #MachineLearning"
    tag_match = re.search(r"((?:#[A-Za-z][A-Za-z0-9]*)(?:[ \t]+#[A-Za-z][A-Za-z0-9]*){0,2})[ \t]*$", cleaned)
    if tag_match:
        body = cleaned[: tag_match.start()].rstrip()
        cleaned = f"{body}\n\n{tag_match.group(1)}" if body else tag_match.group(1)
    if len(cleaned) > 2900:
        cleaned = cleaned[:2890].rsplit(" ", 1)[0] + "…"
    return cleaned.strip()


async def fetch_news_topics(limit: int = 12) -> list[dict[str, str]]:
    """Fetch recent AI stories from public RSS feeds."""
    headers = {"User-Agent": "CareerOS-Autopilot/1.0 (+personal LinkedIn assistant)"}
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
        responses = await asyncio.gather(
            *[client.get(url) for _, url in NEWS_FEEDS], return_exceptions=True
        )

    topics: list[dict[str, str]] = []
    for (source_name, _), resp in zip(NEWS_FEEDS, responses):
        if isinstance(resp, Exception) or resp.status_code >= 400:
            continue
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError:
            continue
        for node in root.iter():
            if node.tag.split("}")[-1].lower() not in ("item", "entry"):
                continue
            title = ""
            link = ""
            summary = ""
            for child in node:
                tag = child.tag.split("}")[-1].lower()
                if tag == "title":
                    title = (child.text or "").strip()
                elif tag == "link":
                    link = (child.text or "").strip() or child.attrib.get("href", "")
                elif tag in ("description", "summary", "content"):
                    summary = BeautifulSoup(child.text or "", "html.parser").get_text(" ", strip=True)
            if not title or not link:
                continue
            topics.append(
                {
                    "title": title,
                    "link": link,
                    "summary": summary[:700],
                    "source": source_name,
                }
            )
            if len(topics) >= limit:
                return topics
    return topics


def _used_topics() -> set[str]:
    try:
        return set(json.loads(_setting("autopilot_used_topics", "[]")))
    except json.JSONDecodeError:
        return set()


def _remember_topic(link: str) -> None:
    used = list(_used_topics())
    if link in used:
        used.remove(link)
    used.append(link)
    _save_setting("autopilot_used_topics", json.dumps(used[-200:]))


def _build_prompt(
    pillar: dict[str, str],
    slot: datetime,
    profile: dict[str, Any],
    topic: dict[str, str] | None,
    recent: list[str],
    angle: str,
) -> tuple[str, str]:
    recent_preview = "\n---\n".join(post[:220] for post in recent[:8]) or "None yet."
    experience_line = "; ".join(
        f"{entry.get('title', '')} at {entry.get('company', '')}"
        for entry in (profile.get("experience") or [])[:3]
    ) or "Not provided"
    notes_list = list_project_notes()
    project_context = ""
    if notes_list:
        chosen = notes_list[slot.toordinal() % len(notes_list)]
        project_context = (
            f"\nOptional real shipped project you may reference naturally if relevant to the angle:\n"
            f"- {chosen['title']}: {chosen['content'][:350]}"
        )

    context = "No external news for this post. Draw on evergreen engineering experience."
    if topic:
        context = (
            f"Source: {topic['source']}\nHeadline: {topic['title']}\n"
            f"Summary: {topic['summary'] or 'No summary available.'}\nLink: {topic['link']}"
        )
    context = context + project_context

    system_prompt = (
        "You are a senior AI/ML engineer writing a LinkedIn post in the first person for "
        f"{profile.get('full_name') or 'an AI engineer'}. "
        + GROUNDING_RULE
        + " Your writing is calm, specific and useful. Never invent a client, employer, deployment, "
        "dataset, metric or case study. If you use an example, describe a common engineering pattern "
        "in general terms or label it hypothetical. You never use markdown formatting or emojis. "
        "You never explain basic definitions to a practitioner audience. Return ONLY the post text."
    )
    notes = ANGLE_NOTES.get(
        angle,
        "Use one concrete mechanism, the failure it prevents, and one honest trade-off. Do not invent results.",
    )
    user_prompt = (
        f"Content pillar: {pillar['name']}.\nInstruction: {pillar['prompt']}\n"
        f"Stay on this exact angle and do not drift to another mechanism: {angle}.\n"
        f"Engineering notes (treat as ground truth; do not contradict or add unrelated fixes): {notes}\n"
        f"Every technical sentence must be directly supported by those notes. Do not add extra "
        f"mechanisms, benefits or failure modes that are not in the notes. If unsure, omit it.\n"
        f"{VOICE_RULES}\n\n"
        f"Today: {slot.strftime('%A, %d %B %Y')}\n"
        f"Author headline: {profile.get('headline') or 'AI/ML Engineer'}\n"
        f"Author about: {(profile.get('about') or '')[:700]}\n"
        f"Skills: {', '.join((profile.get('skills') or [])[:14])}\n"
        f"Real experience (reference only if relevant, never embellish): {experience_line}\n"
        f"Voice: {profile.get('voice_notes') or 'Direct, practical, engineering-focused, generous with detail.'}\n\n"
        f"Recent posts (do not repeat openings, examples or claims):\n{recent_preview}\n\n"
        f"Topic context:\n{context}\n\n"
        "Requirements:\n"
        "- 700 to 1100 characters.\n"
        "- First line is a credible hook that earns the click, with no clickbait. Do not open with "
        "'Deploying', 'Building', 'In today's', or a fabricated customer story.\n"
        "- Short paragraphs separated by blank lines; no walls of text.\n"
        "- One concrete insight, example or framework, and one non-obvious claim you can defend.\n"
        "- Name a real mechanism (chunking, reranking, evaluation set, index refresh, caching, schema "
        "validation, latency budget). No vague 'hybrid system' or 'better model' advice.\n"
        "- Assume the reader already ships AI systems. Never define RAG, LLM or embeddings.\n"
        "- Do not reuse the wording or examples from the style examples.\n"
        "- Do not invent a specific deployment, customer, dataset or numeric result.\n"
        "- Do not use 'let's break down', 'can be crucial', 'consider a scenario', 'game-changer', "
        "'in the ever-evolving', 'double-edged sword', 'it is crucial', 'invaluable', 'for instance' "
        "or similar filler.\n"
        "- Plain text only: no markdown, no bold, no bullet symbols, no emojis.\n"
        "- End with one genuine question that invites experienced practitioners to reply.\n"
        "- Finish with at most three relevant hashtags on the last line.\n"
        "- Do not address the reader as 'folks' or use corporate filler.\n"
    )
    return system_prompt, user_prompt


BANNED_PHRASES = (
    "let's break down",
    "can be crucial",
    "in today's fast",
    "in today's rapidly",
    "game-changer",
    "in the ever-evolving",
    "consider a scenario",
    "for example, if the system",
    "customer support chatbot",
    "revolutionize",
    "delve into",
    "unlock the power",
    "double-edged sword",
    "it is crucial",
    "invaluable",
    "for instance",
    "when is this the wrong choice",
    "plays a crucial role",
)
BANNED_OPENINGS = (
    "deploying ",
    "understanding how",
    "let's ",
    "imagine ",
    "in today",
)
MECHANISM_WORDS = (
    "chunk", "embed", "rerank", "retriev", "index", "eval", "benchmark", "latency", "token",
    "vector", "prompt", "cache", "schema", "guardrail", "threshold", "drift", "agent", "tool",
    "fine-tun", "dataset", "context", "inference", "pipeline", "metric",
)


def _quality_issue(text: str) -> str:
    low = text.lower()
    if len(text) < 600:
        return "The post is too short to be useful."
    if len(text) > 1600:
        return "The post is too long; tighten it to under 1600 characters."
    for phrase in BANNED_PHRASES:
        if phrase in low:
            return f"Remove the cliché or fabricated framing: '{phrase}'."
    if low.startswith(BANNED_OPENINGS):
        return "The opening line is generic or sounds like a fabricated case study. Start with a sharper claim."
    if not any(word in low for word in MECHANISM_WORDS):
        return "Name one concrete mechanism instead of generic advice."
    if low.count("\n\n") < 2:
        return "Break the post into short paragraphs separated by blank lines."
    if "?" not in text[-320:]:
        return "End with a genuine question that invites practitioners to reply."
    if not re.search(r"#[A-Za-z]", text):
        return "Finish with up to three professional hashtags."
    return ""


async def _review_post(content: str, notes: str) -> str:
    """Strict editor pass: remove claims the angle notes do not support."""
    system_prompt = (
        "You are a strict technical editor for LinkedIn posts. The engineering notes are the only "
        "ground truth. Remove or correct every sentence that is not supported by them. Never add new "
        "technical claims, mechanisms, metrics or examples. Keep the first-person practitioner voice, "
        "short paragraphs, one closing question and at most three hashtags. Return only the final post."
    )
    user_prompt = (
        f"Engineering notes:\n{notes}\n\nDraft to correct:\n{content}\n\nCorrected post:"
    )
    reviewed, _, _ = await generate_text(system_prompt, user_prompt, temperature=0.2)
    cleaned = _clean_post(reviewed)
    return cleaned if len(cleaned) >= 500 else content


async def _generate_one(
    slot: datetime,
    pillar: dict[str, str],
    topic: dict[str, str] | None,
    settings: dict[str, Any],
) -> dict[str, Any]:
    profile = get_profile()
    recent = _recent_posts()
    angle = _pick_angle(pillar, slot, recent)
    active_angle = angle
    system_prompt, user_prompt = _build_prompt(pillar, slot, profile, topic, recent, angle)
    content, provider, _ = await generate_text(system_prompt, user_prompt, temperature=0.55)
    cleaned = _clean_post(content)
    issue = _quality_issue(cleaned)
    duplicate = _too_similar(cleaned, recent)
    if issue or duplicate:
        alt_angle = _pick_angle(pillar, slot, recent, exclude=angle)
        active_angle = alt_angle
        problem = issue or (
            "This draft repeats a recent post too closely. Choose a different example and mechanism."
        )
        retry_system, retry_user = _build_prompt(
            pillar, slot, profile, topic, recent, alt_angle
        )
        retry_system = (
            retry_system
            + " A previous draft failed quality review: "
            + problem
            + " Rewrite the post and fix that issue. Return only the final post."
        )
        retry_user = (
            retry_user
            + "\n\nPrevious draft that must not be reused:\n"
            + cleaned[:1200]
            + "\n\nRewrite it completely about this angle: "
            + alt_angle
            + ". Do not reuse its opening, phrasing or examples."
        )
        content, provider, _ = await generate_text(retry_system, retry_user, temperature=0.5)
        cleaned = _clean_post(content)
        issue = _quality_issue(cleaned)
        duplicate = _too_similar(cleaned, recent)
    if issue:
        raise RuntimeError(f"Autopilot quality gate rejected the draft: {issue}")
    if duplicate:
        raise RuntimeError("Autopilot quality gate rejected a duplicate of a recent post.")

    reviewed = await _review_post(cleaned, ANGLE_NOTES.get(active_angle, ""))
    if not _quality_issue(reviewed) and not _too_similar(reviewed, recent):
        cleaned = reviewed

    cfg = get_ai_config()
    image_path, _, image_provider = await generate_post_image(
        cleaned, hf_token=cfg.get("hf_token", ""), allow_card_fallback=False
    )

    status = "scheduled" if settings["auto_publish"] else "draft"
    idem_key = str(uuid.uuid4())
    title = f"Autopilot · {pillar['name']}"
    source_ref = topic["link"] if topic else ""
    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO posts (
                platform, source_type, source_ref, title, content, status,
                scheduled_for, idempotency_key, ai_provider_used, image_path, image_prompt
            ) VALUES ('linkedin', 'autopilot', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_ref,
                title,
                cleaned,
                status,
                _iso_utc(slot),
                idem_key,
                provider,
                image_path,
                image_provider if image_path else "",
            ),
        )
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (cur.lastrowid,)).fetchone()

    if topic:
        _remember_topic(topic["link"])

    return {
        "id": row["id"],
        "title": row["title"],
        "content": row["content"],
        "status": row["status"],
        "scheduled_for": row["scheduled_for"],
        "source_ref": row["source_ref"],
        "image_path": row["image_path"],
        "pillar": pillar["name"],
    }


async def queue_autopilot_posts(force: bool = False, max_generate: int | None = None) -> dict[str, Any]:
    """Generate posts for the next empty slots. Safe to call repeatedly."""
    if _LOCK.locked():
        return {"ok": False, "reason": "Autopilot is already generating a post."}

    async with _LOCK:
        _STATE["running"] = True
        _STATE["last_error"] = ""
        _STATE["last_run_at"] = datetime.now(timezone.utc).isoformat()
        created: list[dict[str, Any]] = []
        try:
            settings = get_settings()
            if not settings["enabled"] and not force:
                return {"ok": True, "created": 0, "reason": "Autopilot is paused."}

            now_utc = datetime.now(timezone.utc)
            with db_session() as conn:
                rows = conn.execute(
                    """
                    SELECT scheduled_for FROM posts
                    WHERE source_type = 'autopilot' AND status = 'scheduled' AND scheduled_for != ''
                    """
                ).fetchall()
            queued = set()
            for row in rows:
                try:
                    when = datetime.fromisoformat(row["scheduled_for"])
                    if when.tzinfo is None:
                        when = when.replace(tzinfo=timezone.utc)
                    if when >= now_utc - timedelta(hours=2):
                        queued.add(row["scheduled_for"])
                except ValueError:
                    continue

            slots = _upcoming_slots(settings, limit=max(settings["posts_per_day"], 4))
            missing = [slot for slot in slots if _iso_utc(slot) not in queued]
            budget = max_generate if max_generate is not None else 2
            missing = missing[:budget]
            if not missing:
                return {"ok": True, "created": 0, "reason": "Queue already filled for the next slots."}

            news: list[dict[str, str]] = []
            try:
                news = await fetch_news_topics()
            except Exception:
                news = []
            used = _used_topics()
            fresh_news = [topic for topic in news if topic["link"] not in used]

            for slot in missing:
                pillar = _pillar_for(slot, settings)
                topic = None
                if pillar["key"] == "signal" and fresh_news:
                    topic = fresh_news.pop(0)
                elif pillar["key"] == "signal" and news:
                    topic = news[0]
                created.append(await _generate_one(slot, pillar, topic, settings))
                _STATE["last_generated_at"] = datetime.now(timezone.utc).isoformat()

            return {"ok": True, "created": len(created), "posts": created}
        except Exception as exc:  # keep the scheduler alive and surface the error
            _STATE["last_error"] = str(exc)[:800]
            return {"ok": False, "created": len(created), "error": str(exc), "posts": created}
        finally:
            _STATE["running"] = False


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _post_in_slot(post_row, slot_local: datetime, tz) -> bool:
    when = _parse_iso(post_row["scheduled_for"])
    return bool(when and when.astimezone(tz).strftime("%Y-%m-%d %H:%M") == slot_local.strftime("%Y-%m-%d %H:%M"))


def get_status() -> dict[str, Any]:
    settings = get_settings()
    tz = _tz(settings["timezone"])
    now_local = datetime.now(tz)
    now_utc = datetime.now(timezone.utc)

    with db_session() as conn:
        autopilot_rows = conn.execute(
            "SELECT * FROM posts WHERE source_type = 'autopilot' ORDER BY id DESC"
        ).fetchall()

    queue_rows = [
        row for row in autopilot_rows
        if row["status"] in ("scheduled", "draft") and _parse_iso(row["scheduled_for"]) and _parse_iso(row["scheduled_for"]) >= now_utc
    ]
    queue_rows.sort(key=lambda row: row["scheduled_for"])
    published_rows = [row for row in autopilot_rows if row["status"] == "published"]
    error_rows = [row for row in autopilot_rows if row["status"] in ("failed", "manual_required")]

    today_slots: list[dict[str, Any]] = []
    for slot in settings["slots"]:
        hour, minute = (int(part) for part in slot.split(":"))
        slot_local = datetime(now_local.year, now_local.month, now_local.day, hour, minute, tzinfo=tz)
        match = next((row for row in autopilot_rows if _post_in_slot(row, slot_local, tz)), None)
        if match:
            status = match["status"]
            post_id = match["id"]
            pillar = (match["title"] or "").replace("Autopilot · ", "")
            preview = match["content"][:160]
            url = match["external_post_url"]
        elif slot_local < now_local:
            status, post_id, pillar, preview, url = "missed", None, "", "", ""
        else:
            status, post_id, pillar, preview, url = "filling", None, "", "", ""
        today_slots.append(
            {
                "time": slot,
                "label": slot_local.strftime("%I:%M %p").lstrip("0"),
                "pillar": pillar,
                "status": status,
                "post_id": post_id,
                "preview": preview,
                "url": url,
            }
        )

    next_post = None
    if queue_rows:
        nxt = queue_rows[0]
        when = _parse_iso(nxt["scheduled_for"])
        if when:
            next_post = {
                "post_id": nxt["id"],
                "at": nxt["scheduled_for"],
                "local": when.astimezone(tz).strftime("%a %d %b, %I:%M %p").replace(" 0", " "),
                "pillar": (nxt["title"] or "").replace("Autopilot · ", ""),
                "preview": nxt["content"][:180],
            }

    published_7d = 0
    published_today = 0
    published_dates: set[str] = set()
    for row in published_rows:
        when = _parse_iso(row["published_at"])
        if not when:
            continue
        if when >= now_utc - timedelta(days=7):
            published_7d += 1
        local_day = when.astimezone(tz).strftime("%Y-%m-%d")
        if local_day == now_local.strftime("%Y-%m-%d"):
            published_today += 1
        published_dates.add(local_day)

    streak = 0
    cursor = now_local.date()
    if cursor.isoformat() not in published_dates:
        cursor -= timedelta(days=1)
    while cursor.isoformat() in published_dates:
        streak += 1
        cursor -= timedelta(days=1)

    queue = [
        {
            "id": row["id"],
            "title": row["title"],
            "content": row["content"],
            "status": row["status"],
            "scheduled_for": row["scheduled_for"],
            "local": (
                _parse_iso(row["scheduled_for"]).astimezone(tz).strftime("%a %d %b, %I:%M %p").replace(" 0", " ")
                if _parse_iso(row["scheduled_for"]) else ""
            ),
            "source_ref": row["source_ref"],
            "image_path": row["image_path"],
        }
        for row in queue_rows[:6]
    ]

    recent = [
        {
            "id": row["id"],
            "title": row["title"],
            "content": row["content"][:220],
            "published_at": row["published_at"],
            "url": row["external_post_url"],
        }
        for row in published_rows[:5]
    ]

    weekly_plan = []
    for offset in range(7):
        day = now_local.date() + timedelta(days=offset)
        focus_key = WEEKLY_FOCUS.get(day.weekday(), "production")
        focus = next((p for p in PILLARS if p["key"] == focus_key), PILLARS[0])
        weekly_plan.append(
            {
                "date": day.strftime("%a %d %b"),
                "focus": focus["name"],
                "summary": focus["summary"],
            }
        )

    return {
        "enabled": settings["enabled"],
        "auto_publish": settings["auto_publish"],
        "posts_per_day": settings["posts_per_day"],
        "timezone": settings["timezone"],
        "slots": settings["slots"],
        "local_time": now_local.strftime("%a %d %b, %I:%M %p").replace(" 0", " "),
        "today": today_slots,
        "next_post": next_post,
        "queue": queue,
        "recent": recent,
        "errors": [
            {
                "id": row["id"],
                "title": row["title"],
                "status": row["status"],
                "error": row["error_message"],
                "scheduled_for": row["scheduled_for"],
            }
            for row in error_rows[:3]
        ],
        "counts": {
            "queued": len(queue_rows),
            "published_today": published_today,
            "published_7d": published_7d,
            "published_total": len(published_rows),
            "streak_days": streak,
        },
        "generation": {
            "running": _STATE["running"],
            "last_error": _STATE["last_error"],
            "last_generated_at": _STATE["last_generated_at"],
            "last_run_at": _STATE["last_run_at"],
        },
        "strategy": {
            "pillars": PILLARS,
            "best_times": BEST_TIMES_NOTE,
            "weekly_plan": weekly_plan,
            "cadence": (
                f"{settings['posts_per_day']} posts per day, {len(settings['slots'])} slots, "
                "pre-generated ahead of time and published automatically."
            ),
            "engagement_note": (
                "LinkedIn's official API cannot read comments on posts, so replies cannot be auto-detected. "
                "Use Posts & Comments to paste a comment and publish a professional reply in one click."
            ),
        },
    }
