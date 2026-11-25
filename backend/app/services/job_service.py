import json
from typing import Any
import httpx
from bs4 import BeautifulSoup
from app.core.ai_provider import extract_json_block, generate_text
from app.database import db_session
from app.models.schemas import JobImportRequest
from app.services.profile_service import GROUNDING_RULE, get_profile

VALID_JOB_STATUSES = {"Saved", "Preparing", "Applied", "Interview", "Offer", "Rejected"}


def _row_to_job(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "company": row["company"],
        "location": row["location"],
        "work_mode": row["work_mode"],
        "sponsorship": row["sponsorship"],
        "apply_url": row["apply_url"],
        "source_type": row["source_type"],
        "raw_text": row["raw_text"],
        "match_score": row["match_score"],
        "match_reasons": json.loads(row["match_reasons_json"] or "[]"),
        "gaps": json.loads(row["gaps_json"] or "[]"),
        "constraints": json.loads(row["constraints_json"] or "[]"),
        "status": row["status"],
        "cv_edits_suggestion": row["cv_edits_suggestion"],
        "cover_letter_draft": row["cover_letter_draft"],
        "screening_qa": json.loads(row["screening_qa_json"] or "[]"),
        "ai_provider_used": row["ai_provider_used"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def _fetch_job_url_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    return text[:12000]


async def import_and_assess_job(req: JobImportRequest) -> dict[str, Any]:
    raw_text = req.raw_text.strip()
    if not raw_text and req.apply_url.strip():
        try:
            raw_text = await _fetch_job_url_text(req.apply_url.strip())
        except Exception as exc:
            raise RuntimeError(
                f"Could not fetch job page ({exc}). Please paste the job description text directly."
            ) from exc

    if not raw_text:
        raise ValueError("Provide either job listing text or a fetchable career page URL.")

    profile = get_profile()
    system_prompt = (
        "You assess job listings for an AI/ML Engineer strictly against their verified CV and preferences. "
        + GROUNDING_RULE
        + " Prioritize AI Engineer, ML Engineer, Computer Vision Engineer, and Generative AI Engineer roles. "
        "If visa sponsorship is not explicitly mentioned in the job text, set sponsorship to 'unknown'. "
        "Return ONLY valid JSON with keys: "
        "title, company, location, work_mode (remote/hybrid/onsite/unknown), sponsorship (yes/no/unknown), "
        "apply_url, match_score (integer 0-100), match_reasons (list of strings citing CV evidence), "
        "gaps (list of strings), constraints (list of strings covering location, onsite, work auth, sponsorship)."
    )
    user_prompt = (
        f"Candidate Target Roles: {', '.join(profile['target_roles'])}\n"
        f"Preferred Locations: {', '.join(profile['preferred_locations'])}\n"
        f"Work Preferences: {profile['work_preferences']}\n"
        f"Work Authorization: {profile['work_authorization'] or 'Not specified'}\n"
        f"Skills: {', '.join(profile['skills'])}\n"
        f"CV Raw Text:\n{profile['cv_raw_text'][:8000]}\n\n"
        f"Job URL (if provided): {req.apply_url}\n"
        f"Job Listing Text:\n{raw_text[:8000]}"
    )

    provider_used = ""
    is_external = False
    parsed: dict[str, Any] = {}
    warning = ""
    try:
        reply, provider_used, is_external = await generate_text(system_prompt, user_prompt, temperature=0.2)
        parsed = extract_json_block(reply)
    except Exception as exc:
        warning = f"Job saved, but AI assessment could not run ({exc})."

    sponsorship = str(parsed.get("sponsorship", "unknown") or "unknown").lower()
    if sponsorship not in {"yes", "no", "unknown"}:
        sponsorship = "unknown"

    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, location, work_mode, sponsorship, apply_url, source_type, raw_text,
                match_score, match_reasons_json, gaps_json, constraints_json, status, ai_provider_used
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Saved', ?)
            """,
            (
                parsed.get("title") or "Untitled Role",
                parsed.get("company") or "",
                parsed.get("location") or "",
                parsed.get("work_mode") or "unknown",
                sponsorship,
                req.apply_url or parsed.get("apply_url") or "",
                req.source_type,
                raw_text,
                int(parsed.get("match_score") or 0),
                json.dumps(parsed.get("match_reasons", [])),
                json.dumps(parsed.get("gaps", [])),
                json.dumps(parsed.get("constraints", [])),
                provider_used,
            ),
        )
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (cur.lastrowid,)).fetchone()

    return {"job": _row_to_job(row), "is_external": is_external, "warning": warning}


def list_jobs() -> list[dict[str, Any]]:
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY match_score DESC, id DESC").fetchall()
    return [_row_to_job(r) for r in rows]


def update_job_status(job_id: int, status: str) -> dict[str, Any]:
    if status not in VALID_JOB_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {sorted(VALID_JOB_STATUSES)}.")
    with db_session() as conn:
        cur = conn.execute(
            "UPDATE jobs SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, job_id),
        )
        if cur.rowcount == 0:
            raise ValueError("Job not found.")
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(row)


async def prepare_application(job_id: int) -> dict[str, Any]:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            raise ValueError("Job not found.")
    job = _row_to_job(row)
    profile = get_profile()

    system_prompt = (
        "You prepare tailored job application materials strictly grounded in the candidate's real CV. "
        + GROUNDING_RULE
        + " Return ONLY valid JSON with keys: "
        "cv_edits_suggestion (string with concrete bullet/keyword adjustments), "
        "cover_letter_draft (concise 150-220 word cover letter), "
        "screening_qa (list of 3 objects with keys: question, answer)."
    )
    user_prompt = (
        f"Candidate: {profile['full_name']} — {profile['headline']}\n"
        f"CV Text:\n{profile['cv_raw_text'][:8000]}\n\n"
        f"Target Job: {job['title']} at {job['company']}\n"
        f"Job Description:\n{job['raw_text'][:7000]}"
    )

    reply, provider_used, is_external = await generate_text(system_prompt, user_prompt, temperature=0.3)
    prep = extract_json_block(reply)

    new_status = "Preparing" if job["status"] == "Saved" else job["status"]
    with db_session() as conn:
        conn.execute(
            """
            UPDATE jobs SET
                cv_edits_suggestion = ?,
                cover_letter_draft = ?,
                screening_qa_json = ?,
                status = ?,
                ai_provider_used = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                prep.get("cv_edits_suggestion", ""),
                prep.get("cover_letter_draft", ""),
                json.dumps(prep.get("screening_qa", [])),
                new_status,
                provider_used,
                job_id,
            ),
        )
        updated = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    return {"job": _row_to_job(updated), "is_external": is_external}
