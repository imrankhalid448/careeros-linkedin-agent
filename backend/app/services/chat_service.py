import json
from typing import Any
from app.core.ai_provider import generate_text
from app.database import db_session
from app.models.schemas import PostGenerateRequest
from app.services.content_service import generate_post_draft
from app.services.job_service import list_jobs
from app.services.profile_service import GROUNDING_RULE, get_profile, list_project_notes


def get_chat_history() -> list[dict[str, Any]]:
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM chat_history ORDER BY id ASC LIMIT 50").fetchall()
    return [
        {
            "id": r["id"],
            "role": r["role"],
            "message": r["message"],
            "cards": json.loads(r["cards_json"] or "[]"),
            "ai_provider_used": r["ai_provider_used"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


async def handle_chat_message(user_message: str) -> dict[str, Any]:
    lower = user_message.lower()
    cards: list[dict[str, Any]] = []
    notes = list_project_notes()
    jobs = list_jobs()
    profile = get_profile()
    provider_used = ""

    with db_session() as conn:
        conn.execute(
            "INSERT INTO chat_history (role, message) VALUES ('user', ?)",
            (user_message,),
        )

    # 1. Detect post drafting intent (e.g. "Use my QuantEye project notes to draft a LinkedIn post")
    wants_post = any(k in lower for k in ["post", "draft", "write about", "share"])
    if wants_post:
        matched_note = None
        for n in notes:
            if n["title"].lower() in lower:
                matched_note = n
                break
        if matched_note:
            res = await generate_post_draft(
                PostGenerateRequest(
                    platform="linkedin",
                    source_type="project_note",
                    project_note_id=matched_note["id"],
                )
            )
            cards.append({"type": "post_draft", "data": res["post"]})
            provider_used = res["post"]["ai_provider_used"]
        else:
            res = await generate_post_draft(
                PostGenerateRequest(
                    platform="linkedin",
                    source_type="idea",
                    idea=user_message,
                )
            )
            cards.append({"type": "post_draft", "data": res["post"]})
            provider_used = res["post"]["ai_provider_used"]

    # 2. Detect job review intent (e.g. "review today's job alerts and show me the three roles that best match my CV")
    wants_jobs = any(k in lower for k in ["job", "role", "match", "alert", "apply"])
    if wants_jobs:
        top_jobs = jobs[:3]
        for j in top_jobs:
            cards.append({"type": "job_match", "data": j})

    # 3. Synthesize concise assistant response
    system_prompt = (
        "You are the user's personal LinkedIn & Career AI Agent. "
        + GROUNDING_RULE
        + " Be concise and helpful. Reference the generated post card and/or top matching job cards if present."
    )
    context_summary = (
        f"Profile Confirmed: {profile['confirmed']}, Name: {profile['full_name']}\n"
        f"Available Project Notes: {[n['title'] for n in notes]}\n"
        f"Saved Jobs Count: {len(jobs)}\n"
        f"Generated Cards This Turn: {[c['type'] for c in cards]}"
    )

    try:
        reply_text, provider_used, _ = await generate_text(
            system_prompt,
            f"User request: {user_message}\n\nWorkspace state:\n{context_summary}",
            temperature=0.3,
        )
    except Exception as exc:
        if cards:
            reply_text = f"Here are the items prepared from your workspace (note: {exc})."
        else:
            reply_text = f"I couldn't reach the AI model right now: {exc}"

    with db_session() as conn:
        cur = conn.execute(
            "INSERT INTO chat_history (role, message, cards_json, ai_provider_used) VALUES ('assistant', ?, ?, ?)",
            (reply_text, json.dumps(cards), provider_used),
        )
        row = conn.execute("SELECT * FROM chat_history WHERE id = ?", (cur.lastrowid,)).fetchone()

    return {
        "id": row["id"],
        "role": row["role"],
        "message": row["message"],
        "cards": cards,
        "ai_provider_used": provider_used,
        "created_at": row["created_at"],
    }
