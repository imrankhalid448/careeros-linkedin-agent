from fastapi import APIRouter, HTTPException
from app.models.schemas import JobImportRequest, JobStatusUpdate, TrackJobRequest
from app.services.job_discovery_service import discover_jobs, track_discovered_job
from app.services.job_service import (
    import_and_assess_job,
    list_jobs,
    prepare_application,
    update_job_status,
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def get_jobs():
    return list_jobs()


@router.get("/discover")
async def get_discovered_jobs(
    q: str = "",
    location: str = "",
    limit: int = 80,
    refresh: bool = False,
):
    try:
        return await discover_jobs(q, location, min(max(limit, 1), 120), refresh)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/track")
def track_job(body: TrackJobRequest):
    try:
        return track_discovered_job(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import")
async def import_job(body: JobImportRequest):
    try:
        return await import_and_assess_job(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{job_id}/prepare")
async def prep_job_application(job_id: int):
    try:
        return await prepare_application(job_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{job_id}/status")
def change_job_status(job_id: int, body: JobStatusUpdate):
    try:
        return update_job_status(job_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
