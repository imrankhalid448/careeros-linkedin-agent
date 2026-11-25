"""Live job discovery from public, keyless job feeds.

LinkedIn's self-serve developer API does not expose job search; these feeds
provide real, currently-open postings that are filtered against the user's
target roles and skills.
"""

import asyncio
import html
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.database import db_session
from app.models.schemas import TrackJobRequest
from app.services.job_service import _row_to_job
from app.services.profile_service import get_profile

CACHE_TTL_SECONDS = 300

SOURCE_NAMES = ("Remotive", "Arbeitnow", "Jobicy", "RemoteOK", "Himalayas")

CORE_KEYWORDS = (
    "ai engineer",
    "artificial intelligence",
    "machine learning",
    "ml engineer",
    "mlops",
    "generative ai",
    "llm",
    "large language model",
    "computer vision",
    "deep learning",
    "natural language",
    "nlp",
    "data scientist",
    "prompt engineer",
    "rag",
    "pytorch",
    "tensorflow",
)

REMOTE_LOCATIONS = {"", "remote", "worldwide", "anywhere", "global", "flexible"}

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _clean_html(raw: Any) -> str:
    if not raw:
        return ""
    if not isinstance(raw, str):
        raw = str(raw)
    text = BeautifulSoup(html.unescape(raw), "html.parser").get_text("\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)[:4000]


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(_as_text(item) for item in value)
    return "" if value is None else str(value)


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", _as_text(value).lower()).strip()


def _timestamp(value: str) -> float:
    if not value:
        return 0.0
    try:
        cleaned = str(value).strip().replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned).timestamp()
    except Exception:
        return 0.0


def _keyword_hit(keyword: str, text: str) -> bool:
    keyword = _norm(keyword)
    if not keyword:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None


def _relevance(job: dict[str, Any], profile: dict[str, Any], query: str) -> int:
    title = _norm(job.get("title", ""))
    body = _norm(
        " ".join(
            [
                title,
                _as_text(job.get("tags")),
                _as_text(job.get("description"))[:2500],
            ]
        )
    )
    score = 0
    role_hit = False

    for role in profile.get("target_roles") or []:
        if _keyword_hit(role, title):
            score += 45
            role_hit = True
        elif _keyword_hit(role, body):
            score += 12
            role_hit = True

    for keyword in CORE_KEYWORDS:
        if _keyword_hit(keyword, title):
            score += 20
            role_hit = True
        elif _keyword_hit(keyword, body):
            score += 5
            role_hit = True

    for skill in (profile.get("skills") or [])[:20]:
        skill_norm = _norm(skill)
        if len(skill_norm) < 3:
            continue
        if _keyword_hit(skill_norm, title):
            score += 8
        elif _keyword_hit(skill_norm, body):
            score += 2

    if query and _keyword_hit(query, title):
        score += 40
        role_hit = True
    elif query and _keyword_hit(query, body):
        score += 8
        role_hit = True

    if not role_hit:
        return 0

    if job.get("work_mode") == "remote":
        score += 12
    location = _norm(job.get("location"))
    if any(token in location for token in ("worldwide", "anywhere", "global", "remote")):
        score += 6

    return min(100, score)


def _matches_location(job: dict[str, Any], location: str) -> bool:
    needle = _norm(location)
    if not needle:
        return True
    haystack = _norm(job.get("location", ""))
    if any(remote in haystack for remote in REMOTE_LOCATIONS if remote):
        return True
    return needle in haystack or haystack in needle


async def _fetch_remotive(client: httpx.AsyncClient, query: str) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": 100}
    if query:
        params["search"] = query
    resp = await client.get("https://remotive.com/api/remote-jobs", params=params)
    resp.raise_for_status()
    jobs = []
    for item in resp.json().get("jobs", []):
        jobs.append(
            {
                "id": f"remotive-{item.get('id')}",
                "title": (item.get("title") or "").strip(),
                "company": (item.get("company_name") or "").strip(),
                "location": item.get("candidate_required_location") or "Remote",
                "work_mode": "remote",
                "url": item.get("url") or "",
                "description": _clean_html(item.get("description", "")),
                "salary": item.get("salary") or "",
                "job_type": (item.get("job_type") or "").replace("_", " "),
                "tags": item.get("tags") or [],
                "posted_at": item.get("publication_date") or "",
                "source": "Remotive",
            }
        )
    return jobs


async def _fetch_arbeitnow(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    resp = await client.get("https://www.arbeitnow.com/api/job-board-api")
    resp.raise_for_status()
    jobs = []
    for item in resp.json().get("data", []):
        created = item.get("created_at")
        posted = ""
        if isinstance(created, (int, float)) and created > 0:
            posted = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
        jobs.append(
            {
                "id": f"arbeitnow-{item.get('slug')}",
                "title": (item.get("title") or "").strip(),
                "company": (item.get("company_name") or "").strip(),
                "location": item.get("location") or "Germany",
                "work_mode": "remote" if item.get("remote") else "onsite",
                "url": item.get("url") or "",
                "description": _clean_html(item.get("description", "")),
                "salary": "",
                "job_type": ", ".join(item.get("job_types") or []),
                "tags": item.get("tags") or [],
                "posted_at": posted,
                "source": "Arbeitnow",
            }
        )
    return jobs


async def _fetch_jobicy(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    resp = await client.get("https://jobicy.com/api/v2/remote-jobs", params={"count": 50})
    resp.raise_for_status()
    jobs = []
    for item in resp.json().get("jobs", []):
        salary = ""
        if item.get("annualSalaryMin") or item.get("annualSalaryMax"):
            salary = f"${item.get('annualSalaryMin') or '?'}–${item.get('annualSalaryMax') or '?'}"
        industry = item.get("jobIndustry")
        tags = industry if isinstance(industry, list) else ([industry] if industry else [])
        jobs.append(
            {
                "id": f"jobicy-{item.get('id')}",
                "title": _as_text(item.get("jobTitle")).strip(),
                "company": _as_text(item.get("companyName")).strip(),
                "location": _as_text(item.get("jobGeo")) or "Remote",
                "work_mode": "remote",
                "url": item.get("url") or "",
                "description": _clean_html(
                    _as_text(item.get("jobDescription") or item.get("jobExcerpt"))
                ),
                "salary": salary,
                "job_type": _as_text(item.get("jobType")),
                "tags": [_as_text(tag) for tag in tags if _as_text(tag)],
                "posted_at": item.get("pubDate") or "",
                "source": "Jobicy",
            }
        )
    return jobs


async def _fetch_remoteok(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    resp = await client.get("https://remoteok.com/api")
    resp.raise_for_status()
    jobs = []
    for item in resp.json():
        if not item.get("id") or not item.get("position"):
            continue
        salary = ""
        low, high = item.get("salary_min") or 0, item.get("salary_max") or 0
        if low or high:
            salary = f"${int(low):,}–${int(high):,}"
        jobs.append(
            {
                "id": f"remoteok-{item.get('id')}",
                "title": (item.get("position") or "").strip(),
                "company": (item.get("company") or "").strip(),
                "location": item.get("location") or "Remote",
                "work_mode": "remote",
                "url": item.get("url") or item.get("apply_url") or "",
                "description": _clean_html(item.get("description", "")),
                "salary": salary,
                "job_type": "",
                "tags": item.get("tags") or [],
                "posted_at": item.get("date") or "",
                "source": "RemoteOK",
            }
        )
    return jobs


async def _fetch_himalayas(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor = ""
    for _ in range(5):
        params: dict[str, Any] = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        resp = await client.get("https://himalayas.app/jobs/api", params=params)
        resp.raise_for_status()
        data = resp.json()
        page_items = data.get("jobs") or []
        items.extend(page_items)
        cursor = data.get("nextCursor") or ""
        if not cursor or not page_items:
            break

    jobs = []
    for item in items:
        restrictions = item.get("locationRestrictions") or []
        location = (
            ", ".join(_as_text(region) for region in restrictions if _as_text(region))
            if restrictions
            else "Worldwide"
        )
        salary = ""
        if item.get("minSalary") or item.get("maxSalary"):
            currency = _as_text(item.get("currency")) or "$"
            salary = f"{currency}{item.get('minSalary') or '?'}–{item.get('maxSalary') or '?'}"
        posted = ""
        if isinstance(item.get("pubDate"), (int, float)):
            posted = datetime.fromtimestamp(item["pubDate"], tz=timezone.utc).isoformat()
        tags = list(item.get("categories") or []) + list(item.get("parentCategories") or [])
        jobs.append(
            {
                "id": f"himalayas-{item.get('guid') or item.get('applicationLink')}",
                "title": _as_text(item.get("title")).strip(),
                "company": _as_text(item.get("companyName")).strip(),
                "location": location,
                "work_mode": "remote",
                "url": item.get("applicationLink") or item.get("guid") or "",
                "description": _clean_html(item.get("description", "")),
                "salary": salary,
                "job_type": _as_text(item.get("employmentType")),
                "tags": [_as_text(tag) for tag in tags if _as_text(tag)],
                "posted_at": posted,
                "source": "Himalayas",
            }
        )
    return jobs


def _dedupe(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output = []
    for job in jobs:
        title = _norm(job.get("title", ""))
        company = _norm(job.get("company", ""))
        if not title:
            continue
        key = f"{title}|{company}"
        if key in seen:
            continue
        seen.add(key)
        output.append(job)
    return output


async def discover_jobs(
    query: str = "",
    location: str = "",
    limit: int = 80,
    refresh: bool = False,
) -> dict[str, Any]:
    profile = get_profile()
    cache_key = f"{_norm(query)}|{_norm(location)}|{limit}|{profile.get('updated_at')}"
    now = time.time()
    if not refresh and cache_key in _cache and now - _cache[cache_key][0] < CACHE_TTL_SECONDS:
        return _cache[cache_key][1]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CareerOS/1.0 job discovery",
        "Accept": "application/json",
    }
    feed_query = query or ((profile.get("target_roles") or ["AI Engineer"])[0])
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=headers) as client:
        results = await asyncio.gather(
            _fetch_remotive(client, feed_query),
            _fetch_arbeitnow(client),
            _fetch_jobicy(client),
            _fetch_remoteok(client),
            _fetch_himalayas(client),
            return_exceptions=True,
        )

    sources: list[dict[str, Any]] = []
    collected: list[dict[str, Any]] = []
    for name, result in zip(SOURCE_NAMES, results):
        if isinstance(result, Exception):
            sources.append({"name": name, "count": 0, "ok": False, "error": str(result)[:160]})
            continue
        sources.append({"name": name, "count": len(result), "ok": True, "error": ""})
        collected.extend(result)

    collected = [job for job in _dedupe(collected) if _matches_location(job, location)]

    for job in collected:
        job["relevance"] = _relevance(job, profile, query)

    relevant = sorted(
        collected,
        key=lambda job: (-job["relevance"], -_timestamp(job.get("posted_at", ""))),
    )
    displayed = relevant[:limit]

    payload = {
        "jobs": displayed,
        "sources": sources,
        "query": query,
        "location": location,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total": len(displayed),
        "relevant_count": sum(1 for job in displayed if job["relevance"] >= 20),
        "remote_count": sum(1 for job in displayed if job.get("work_mode") == "remote"),
        "scanned": len(collected),
        "profile_roles": profile.get("target_roles") or [],
    }
    _cache[cache_key] = (now, payload)
    return payload


def track_discovered_job(req: TrackJobRequest) -> dict[str, Any]:
    apply_url = (req.apply_url or "").strip()
    with db_session() as conn:
        if apply_url:
            row = conn.execute("SELECT * FROM jobs WHERE apply_url = ?", (apply_url,)).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM jobs WHERE title = ? AND company = ?",
                (req.title.strip(), req.company.strip()),
            ).fetchone()
        if row:
            return {"job": _row_to_job(row), "already_tracked": True, "message": "Already in your pipeline."}

        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, location, work_mode, sponsorship, apply_url, source_type,
                raw_text, match_score, status, ai_provider_used
            )
            VALUES (?, ?, ?, ?, 'unknown', ?, ?, ?, 0, 'Saved', '')
            """,
            (
                req.title.strip() or "Untitled Role",
                req.company.strip(),
                req.location.strip(),
                req.work_mode or "unknown",
                apply_url,
                (req.source or "discovered").strip() or "discovered",
                req.description.strip() or req.title.strip(),
            ),
        )
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (cur.lastrowid,)).fetchone()

    return {"job": _row_to_job(row), "already_tracked": False, "message": "Added to your pipeline."}
