import uuid
from datetime import datetime, timezone
from typing import Any
from app.connectors.linkedin import extract_linkedin_post_urn
from app.connectors.registry import registry
from app.core.ai_provider import generate_text, get_ai_config
from app.core.image_provider import generate_post_image
from app.database import db_session
from app.models.schemas import (
    CommentGenerateRequest,
    PostGenerateRequest,
    PostUpdateRequest,
)
from app.services.profile_service import GROUNDING_RULE, get_profile, list_project_notes


def _row_to_post(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "platform": row["platform"],
        "source_type": row["source_type"],
        "source_ref": row["source_ref"],
        "title": row["title"],
        "content": row["content"],
        "status": row["status"],
        "scheduled_for": row["scheduled_for"],
        "idempotency_key": row["idempotency_key"],
        "external_post_id": row["external_post_id"],
        "external_post_url": row["external_post_url"],
        "error_message": row["error_message"],
        "ai_provider_used": row["ai_provider_used"],
        "image_path": row["image_path"] if "image_path" in row.keys() else "",
        "image_prompt": row["image_prompt"] if "image_prompt" in row.keys() else "",
        "created_at": row["created_at"],
        "published_at": row["published_at"],
    }


def _row_to_comment(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "platform": row["platform"],
        "target_url": row["target_url"],
        "target_urn": row["target_urn"],
        "source_post_text": row["source_post_text"],
        "draft_reply": row["draft_reply"],
        "status": row["status"],
        "idempotency_key": row["idempotency_key"],
        "external_comment_id": row["external_comment_id"],
        "error_message": row["error_message"],
        "ai_provider_used": row["ai_provider_used"],
        "image_path": row["image_path"] if "image_path" in row.keys() else "",
        "image_prompt": row["image_prompt"] if "image_prompt" in row.keys() else "",
        "created_at": row["created_at"],
        "published_at": row["published_at"],
    }


async def generate_post_draft(req: PostGenerateRequest) -> dict[str, Any]:
    profile = get_profile()
    source_context = req.idea
    title = "LinkedIn Post Draft"
    source_ref = req.github_url or ""

    if req.project_note_id:
        notes = [n for n in list_project_notes() if n["id"] == req.project_note_id]
        if not notes:
            raise ValueError(f"Project note {req.project_note_id} not found.")
        note = notes[0]
        title = f"Post: {note['title']}"
        source_ref = note["github_url"] or note["title"]
        source_context = f"Project Title: {note['title']}\nGitHub: {note['github_url']}\nNotes:\n{note['content']}"

    system_prompt = (
        "You write authentic, concise, technical LinkedIn posts for an AI/ML Engineer in their own voice. "
        + GROUNDING_RULE
        + " Keep the post clear, practical, free of cringe buzzwords, and include a thoughtful takeaway or question. "
        "Return ONLY the post text ready for LinkedIn."
    )
    user_prompt = (
        f"Author: {profile['full_name']} ({profile['headline']})\n"
        f"Voice Notes: {profile['voice_notes'] or 'Direct, practical, engineering-focused'}\n"
        f"Tone Hint: {req.tone_hint or 'Authentic builder voice'}\n"
        f"GitHub Link: {req.github_url}\n"
        f"Source Material:\n{source_context}"
    )

    content, provider_used, is_external = await generate_text(system_prompt, user_prompt, temperature=0.5)

    image_path = ""
    image_prompt = ""
    try:
        image_path, image_prompt, _ = await generate_post_image(content, allow_card_fallback=False)
    except Exception:
        image_path, image_prompt = "", ""

    idem_key = str(uuid.uuid4())

    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO posts (
                platform, source_type, source_ref, title, content, status,
                idempotency_key, ai_provider_used, image_path, image_prompt
            ) VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)
            """,
            (
                req.platform,
                req.source_type,
                source_ref,
                title,
                content,
                idem_key,
                provider_used,
                image_path,
                image_prompt,
            ),
        )
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (cur.lastrowid,)).fetchone()

    return {"post": _row_to_post(row), "is_external": is_external}


def list_posts() -> list[dict[str, Any]]:
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
    return [_row_to_post(r) for r in rows]


def update_post(post_id: int, req: PostUpdateRequest) -> dict[str, Any]:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not row:
            raise ValueError("Post not found.")
        if row["status"] == "published":
            raise ValueError("Cannot edit an already published post.")

        new_title = req.title if req.title is not None else row["title"]
        new_content = req.content if req.content is not None else row["content"]
        new_sched = req.scheduled_for if req.scheduled_for is not None else row["scheduled_for"]
        new_status = "scheduled" if new_sched else "draft"

        conn.execute(
            "UPDATE posts SET title = ?, content = ?, scheduled_for = ?, status = ? WHERE id = ?",
            (new_title, new_content, new_sched, new_status, post_id),
        )
        updated = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    return _row_to_post(updated)


async def publish_post_now(post_id: int) -> dict[str, Any]:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not row:
            raise ValueError("Post not found.")
        # Idempotency guard: prevent duplicate publishing on double-click or retry
        if row["status"] in ("published", "publishing"):
            return {
                "post": _row_to_post(row),
                "message": "Post already published or currently publishing (duplicate prevented).",
            }
        conn.execute("UPDATE posts SET status = 'publishing', error_message = '' WHERE id = ?", (post_id,))

    connector = registry.get(row["platform"])
    image_path = row["image_path"] if "image_path" in row.keys() else ""
    result = await connector.publish_post(row["content"], row["idempotency_key"], image_path=image_path)

    now_iso = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        if result.success:
            conn.execute(
                """
                UPDATE posts SET
                    status = 'published',
                    external_post_id = ?,
                    external_post_url = ?,
                    published_at = ?,
                    error_message = ''
                WHERE id = ?
                """,
                (result.external_id, result.external_url, now_iso, post_id),
            )
        else:
            fallback_status = "manual_required" if result.manual_required else "failed"
            conn.execute(
                "UPDATE posts SET status = ?, error_message = ? WHERE id = ?",
                (fallback_status, result.message, post_id),
            )
        updated = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()

    return {"post": _row_to_post(updated), "message": result.message}


async def attach_generated_image(post_id: int, custom_prompt: str = "") -> dict[str, Any]:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not row:
            raise ValueError("Post not found.")
        if row["status"] == "published":
            raise ValueError("Cannot attach image to an already published post.")

    cfg = get_ai_config()
    filename, prompt_used, provider = await generate_post_image(
        row["content"], custom_prompt, hf_token=cfg.get("hf_token", "")
    )
    with db_session() as conn:
        conn.execute(
            "UPDATE posts SET image_path = ?, image_prompt = ? WHERE id = ?",
            (filename, prompt_used, post_id),
        )
        updated = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    return {"post": _row_to_post(updated), "image_provider": provider}


def attach_uploaded_image(post_id: int, filename: str) -> dict[str, Any]:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not row:
            raise ValueError("Post not found.")
        conn.execute("UPDATE posts SET image_path = ?, image_prompt = 'uploaded' WHERE id = ?", (filename, post_id))
        updated = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    return _row_to_post(updated)


def remove_post_image(post_id: int) -> dict[str, Any]:
    with db_session() as conn:
        conn.execute("UPDATE posts SET image_path = '', image_prompt = '' WHERE id = ?", (post_id,))
        updated = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not updated:
            raise ValueError("Post not found.")
    return _row_to_post(updated)


async def process_due_scheduled_posts() -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id, scheduled_for FROM posts WHERE status = 'scheduled' AND scheduled_for != ''"
        ).fetchall()
    for r in rows:
        if r["scheduled_for"] <= now_iso:
            try:
                await publish_post_now(r["id"])
            except Exception:
                pass


async def generate_comment_draft(req: CommentGenerateRequest) -> dict[str, Any]:
    if not req.source_post_text.strip():
        return {
            "needs_more_context": True,
            "message": "A link alone does not provide enough context. Please paste the post or comment text you want to reply to.",
        }

    profile = get_profile()
    system_prompt = (
        "You write thoughtful, specific LinkedIn comments for an AI/ML Engineer in their own voice. "
        + GROUNDING_RULE
        + " Keep it concise (2-4 sentences), specific to the post, and natural. Return ONLY the comment text."
    )
    user_prompt = (
        f"Commenter: {profile['full_name']} ({profile['headline']})\n"
        f"Voice Notes: {profile['voice_notes'] or 'Constructive, technical, concise'}\n"
        f"Intent: {req.intent or 'Add a thoughtful engineering perspective'}\n"
        f"Post / Comment Text:\n{req.source_post_text[:5000]}"
    )

    reply, provider_used, is_external = await generate_text(system_prompt, user_prompt, temperature=0.4)
    target_urn = extract_linkedin_post_urn(req.target_url)
    idem_key = str(uuid.uuid4())

    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO comments (platform, target_url, target_urn, source_post_text, draft_reply, status, idempotency_key, ai_provider_used)
            VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)
            """,
            (req.platform, req.target_url, target_urn, req.source_post_text, reply, idem_key, provider_used),
        )
        row = conn.execute("SELECT * FROM comments WHERE id = ?", (cur.lastrowid,)).fetchone()

    return {"needs_more_context": False, "comment": _row_to_comment(row), "is_external": is_external}


def list_comments() -> list[dict[str, Any]]:
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM comments ORDER BY id DESC").fetchall()
    return [_row_to_comment(r) for r in rows]


def update_comment(comment_id: int, draft_reply: str) -> dict[str, Any]:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
        if not row:
            raise ValueError("Comment not found.")
        conn.execute("UPDATE comments SET draft_reply = ? WHERE id = ?", (draft_reply, comment_id))
        updated = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
    return _row_to_comment(updated)


async def publish_comment_now(comment_id: int) -> dict[str, Any]:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
        if not row:
            raise ValueError("Comment not found.")
        if row["status"] in ("published", "publishing"):
            return {"comment": _row_to_comment(row), "message": "Comment already published (duplicate prevented)."}
        conn.execute("UPDATE comments SET status = 'publishing', error_message = '' WHERE id = ?", (comment_id,))

    connector = registry.get(row["platform"])
    result = await connector.post_comment(
        row["target_url"], row["target_urn"], row["draft_reply"], row["idempotency_key"]
    )
    now_iso = datetime.now(timezone.utc).isoformat()

    with db_session() as conn:
        if result.success:
            conn.execute(
                """
                UPDATE comments SET status = 'published', external_comment_id = ?, published_at = ?, error_message = ''
                WHERE id = ?
                """,
                (result.external_id, now_iso, comment_id),
            )
        else:
            status = "manual_required" if result.manual_required else "failed"
            conn.execute(
                "UPDATE comments SET status = ?, error_message = ? WHERE id = ?",
                (status, result.message, comment_id),
            )
        updated = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()

    return {"comment": _row_to_comment(updated), "message": result.message}
