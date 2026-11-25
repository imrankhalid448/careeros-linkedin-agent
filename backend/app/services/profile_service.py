import json
import re
from typing import Any
from app.connectors.registry import registry
from app.core.ai_provider import extract_json_block, generate_text
from app.database import db_session
from app.models.schemas import ProfileUpdate, ProjectNoteCreate

GROUNDING_RULE = (
    "STRICT RULE: Only use facts explicitly present in the user's CV, LinkedIn text, and project notes. "
    "NEVER invent experience, metrics, degrees, certifications, employers, or work authorization."
)


URL_PATTERN = re.compile(
    r"(?:https?://)?(?:[a-z0-9-]+\.)?(?:linkedin\.com/in|github\.com)/[^\s<>\"',;)]+",
    re.IGNORECASE,
)


def _extract_links(text: str) -> list[str]:
    links: list[str] = []
    for match in URL_PATTERN.finditer(text or ""):
        url = match.group(0).strip().rstrip(".,;)")
        if not url.lower().startswith("http"):
            url = f"https://{url.lstrip('/')}"
        if url not in links:
            links.append(url)
    return links[:10]


def _canonical_link(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url.strip().rstrip("/")).lower()


def _dedupe_links(links: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for link in links:
        if not isinstance(link, str):
            continue
        value = link.strip().rstrip("/")
        if not value:
            continue
        key = _canonical_link(value)
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def get_profile() -> dict[str, Any]:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone()
    return {
        "full_name": row["full_name"],
        "headline": row["headline"],
        "about": row["about"],
        "skills": json.loads(row["skills_json"] or "[]"),
        "experience": json.loads(row["experience_json"] or "[]"),
        "portfolio_links": json.loads(row["portfolio_links_json"] or "[]"),
        "target_roles": json.loads(row["target_roles_json"] or "[]"),
        "preferred_locations": json.loads(row["preferred_locations_json"] or "[]"),
        "work_preferences": row["work_preferences"],
        "work_authorization": row["work_authorization"],
        "cv_filename": row["cv_filename"],
        "cv_raw_text": row["cv_raw_text"],
        "linkedin_raw_text": row["linkedin_raw_text"],
        "voice_notes": row["voice_notes"],
        "confirmed": bool(row["confirmed"]),
        "updated_at": row["updated_at"],
    }


def update_profile(data: ProfileUpdate) -> dict[str, Any]:
    with db_session() as conn:
        conn.execute(
            """
            UPDATE user_profile SET
                full_name = ?,
                headline = ?,
                about = ?,
                skills_json = ?,
                experience_json = ?,
                portfolio_links_json = ?,
                target_roles_json = ?,
                preferred_locations_json = ?,
                work_preferences = ?,
                work_authorization = ?,
                linkedin_raw_text = ?,
                voice_notes = ?,
                confirmed = ?,
                updated_at = datetime('now')
            WHERE id = 1
            """,
            (
                data.full_name,
                data.headline,
                data.about,
                json.dumps(data.skills),
                json.dumps(data.experience),
                json.dumps(data.portfolio_links),
                json.dumps(data.target_roles),
                json.dumps(data.preferred_locations),
                data.work_preferences,
                data.work_authorization,
                data.linkedin_raw_text,
                data.voice_notes,
                1 if data.confirmed else 0,
            ),
        )
    return get_profile()


async def save_and_extract_cv(filename: str, raw_text: str) -> dict[str, Any]:
    with db_session() as conn:
        conn.execute(
            "UPDATE user_profile SET cv_filename = ?, cv_raw_text = ?, confirmed = 0, updated_at = datetime('now') WHERE id = 1",
            (filename, raw_text),
        )

    current = get_profile()
    system_prompt = (
        "You extract structured career profile data from a user's CV and optional LinkedIn text. "
        + GROUNDING_RULE
        + " Return ONLY valid JSON with keys: full_name, headline, about, skills (list of strings), "
        "experience (list of objects with title, company, duration, highlights), portfolio_links (list of strings), "
        "work_authorization (string, empty if not stated). "
        "Be compact: at most 5 experience entries, each with at most 3 short highlights, "
        "about under 600 characters, and no markdown outside the JSON."
    )
    user_prompt = (
        f"CV Text:\n{raw_text[:6000]}\n\n"
        f"Existing LinkedIn Text (if any):\n{current['linkedin_raw_text'][:1500]}"
    )

    extraction_warning = ""
    provider_used = ""
    is_external = False
    try:
        reply, provider_used, is_external = await generate_text(system_prompt, user_prompt, temperature=0.1)
        extracted = extract_json_block(reply)
        portfolio_links = [
            link
            for link in (extracted.get("portfolio_links") or current["portfolio_links"])
            if isinstance(link, str)
        ]
        for link in _extract_links(raw_text):
            if link not in portfolio_links:
                portfolio_links.append(link)
        with db_session() as conn:
            conn.execute(
                """
                UPDATE user_profile SET
                    full_name = COALESCE(NULLIF(?, ''), full_name),
                    headline = COALESCE(NULLIF(?, ''), headline),
                    about = COALESCE(NULLIF(?, ''), about),
                    skills_json = ?,
                    experience_json = ?,
                    portfolio_links_json = ?,
                    work_authorization = COALESCE(NULLIF(?, ''), work_authorization),
                    updated_at = datetime('now')
                WHERE id = 1
                """,
                (
                    extracted.get("full_name", ""),
                    extracted.get("headline", ""),
                    extracted.get("about", ""),
                    json.dumps(extracted.get("skills", current["skills"])),
                    json.dumps(extracted.get("experience", current["experience"])),
                    json.dumps(_dedupe_links(portfolio_links)),
                    extracted.get("work_authorization", ""),
                ),
            )
    except Exception as exc:
        reason = str(exc).strip() or type(exc).__name__
        extraction_warning = (
            f"CV saved, but AI auto-extraction could not run ({reason}). "
            "Make sure Ollama and the selected model are running, then re-extract."
        )

    return {
        "profile": get_profile(),
        "ai_provider_used": provider_used,
        "is_external": is_external,
        "warning": extraction_warning,
    }


def _as_list(value: Any, fallback: list) -> list:
    return value if isinstance(value, list) and len(value) > 0 else fallback


async def import_linkedin_profile(profile_text: str = "") -> dict[str, Any]:
    """Sync the profile from LinkedIn.

    The connected OpenID account supplies verified identity. Because LinkedIn
    does not expose headline/about/skills to self-serve apps, pasted profile
    text is parsed by the local model to fill the remaining sections.
    """
    current = get_profile()
    identity: dict[str, Any] = {}
    warnings: list[str] = []
    provider_used = ""
    is_external = False

    connector = registry.get("linkedin")
    if connector.get_auth_status().connected:
        try:
            identity = await connector.fetch_identity()
        except Exception as exc:
            warnings.append(f"LinkedIn identity could not be fetched ({exc}).")
    else:
        warnings.append("LinkedIn is not connected. Connect your account under Connectors.")

    text = (profile_text or "").strip()
    extracted: dict[str, Any] = {}
    if text:
        system_prompt = (
            "You extract structured profile data from copied LinkedIn profile text. "
            + GROUNDING_RULE
            + " Return ONLY valid JSON with keys: full_name, headline, about, skills (list of strings), "
            "experience (list of objects with title, company, duration, highlights), portfolio_links (list of strings), "
            "target_roles (list of strings), preferred_locations (list of strings), work_authorization (string). "
            "Be compact: at most 5 experience entries with at most 3 short highlights, "
            "about under 600 characters, and no markdown outside the JSON."
        )
        user_prompt = f"LinkedIn profile text:\n{text[:8000]}"
        try:
            reply, provider_used, is_external = await generate_text(
                system_prompt, user_prompt, temperature=0.2
            )
            extracted = extract_json_block(reply)
        except Exception as exc:
            reason = str(exc).strip() or type(exc).__name__
            warnings.append(f"Profile text saved, but AI extraction could not run ({reason}).")
    elif not identity:
        warnings.append(
            "Paste your LinkedIn profile text to extract headline, about, skills and experience."
        )

    links = list(current["portfolio_links"])
    for link in _as_list(extracted.get("portfolio_links"), []):
        if isinstance(link, str) and link.strip() and link.strip() not in links:
            links.append(link.strip())
    for link in _extract_links(text):
        if link not in links:
            links.append(link)
    if identity.get("profile_url") and identity["profile_url"] not in links:
        links.append(identity["profile_url"])

    merged = ProfileUpdate(
        full_name=identity.get("name") or extracted.get("full_name") or current["full_name"],
        headline=extracted.get("headline") or current["headline"],
        about=extracted.get("about") or current["about"],
        skills=_as_list(extracted.get("skills"), current["skills"]),
        experience=[
            item
            for item in _as_list(extracted.get("experience"), current["experience"])
            if isinstance(item, dict)
        ],
        portfolio_links=_dedupe_links(links),
        target_roles=_as_list(extracted.get("target_roles"), current["target_roles"]),
        preferred_locations=_as_list(
            extracted.get("preferred_locations"), current["preferred_locations"]
        ),
        work_preferences=current["work_preferences"],
        work_authorization=extracted.get("work_authorization") or current["work_authorization"],
        linkedin_raw_text=text or current["linkedin_raw_text"],
        voice_notes=current["voice_notes"],
        confirmed=False,
    )

    updated_fields = [
        key
        for key in (
            "full_name",
            "headline",
            "about",
            "skills",
            "experience",
            "portfolio_links",
            "target_roles",
            "preferred_locations",
            "work_authorization",
            "linkedin_raw_text",
        )
        if getattr(merged, key) != current.get(key)
    ]

    if not updated_fields:
        return {
            "profile": current,
            "identity": identity,
            "updated_fields": [],
            "ai_provider_used": provider_used,
            "is_external": is_external,
            "warnings": warnings,
            "warning": " ".join(warnings),
        }

    update_profile(merged)
    return {
        "profile": get_profile(),
        "identity": identity,
        "updated_fields": updated_fields,
        "ai_provider_used": provider_used,
        "is_external": is_external,
        "warnings": warnings,
        "warning": " ".join(warnings),
    }


async def review_linkedin_profile() -> dict[str, Any]:
    profile = get_profile()
    notes = list_project_notes()
    notes_summary = "\n".join(f"- {n['title']}: {n['content'][:500]}" for n in notes[:6])

    system_prompt = (
        "You are a senior AI/ML career coach reviewing a LinkedIn profile. "
        + GROUNDING_RULE
        + " Compare the user's current wording against their target roles and real CV/project evidence. "
        "Return ONLY valid JSON with keys: "
        "headline (object: current, proposed, why_it_helps), "
        "about (object: current, proposed, why_it_helps), "
        "skills (object: current, proposed, why_it_helps), "
        "experience (object: current, proposed, why_it_helps)."
    )
    user_prompt = (
        f"Target Roles: {', '.join(profile['target_roles'])}\n"
        f"Current Headline: {profile['headline']}\n"
        f"Current About: {profile['about']}\n"
        f"Current Skills: {', '.join(profile['skills'])}\n"
        f"Current Experience: {json.dumps(profile['experience'])}\n"
        f"CV Raw Text:\n{profile['cv_raw_text'][:8000]}\n"
        f"LinkedIn Raw Text:\n{profile['linkedin_raw_text'][:4000]}\n"
        f"Project Notes:\n{notes_summary}"
    )

    reply, provider_used, is_external = await generate_text(system_prompt, user_prompt, temperature=0.3)
    review = extract_json_block(reply)
    return {
        "review": review,
        "ai_provider_used": provider_used,
        "is_external": is_external,
    }


def list_project_notes() -> list[dict[str, Any]]:
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM project_notes ORDER BY id DESC").fetchall()
    return [
        {
            "id": r["id"],
            "title": r["title"],
            "content": r["content"],
            "github_url": r["github_url"],
            "tags": json.loads(r["tags_json"] or "[]"),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def create_project_note(note: ProjectNoteCreate) -> dict[str, Any]:
    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO project_notes (title, content, github_url, tags_json)
            VALUES (?, ?, ?, ?)
            """,
            (note.title, note.content, note.github_url, json.dumps(note.tags)),
        )
        note_id = cur.lastrowid
        row = conn.execute("SELECT * FROM project_notes WHERE id = ?", (note_id,)).fetchone()
    return {
        "id": row["id"],
        "title": row["title"],
        "content": row["content"],
        "github_url": row["github_url"],
        "tags": json.loads(row["tags_json"] or "[]"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def delete_project_note(note_id: int) -> None:
    with db_session() as conn:
        conn.execute("DELETE FROM project_notes WHERE id = ?", (note_id,))
