from fastapi import APIRouter, File, HTTPException, UploadFile
from app.config import UPLOADS_DIR
from app.core.cv_parser import extract_text_from_file
from app.models.schemas import LinkedInImportRequest, ProfileUpdate, ProjectNoteCreate
from app.services.profile_service import (
    create_project_note,
    delete_project_note,
    get_profile,
    import_linkedin_profile,
    list_project_notes,
    review_linkedin_profile,
    save_and_extract_cv,
    update_profile,
)

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("")
def read_profile():
    return get_profile()


@router.put("")
def save_profile(body: ProfileUpdate):
    return update_profile(body)


@router.post("/upload-cv")
async def upload_cv(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")
    dest = UPLOADS_DIR / file.filename
    content = await file.read()
    dest.write_bytes(content)
    try:
        raw_text = extract_text_from_file(dest)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await save_and_extract_cv(file.filename, raw_text)


@router.post("/re-extract")
async def reextract_saved_cv():
    profile = get_profile()
    if not profile.get("cv_raw_text"):
        raise HTTPException(status_code=400, detail="Upload a CV before re-running extraction.")
    return await save_and_extract_cv(profile.get("cv_filename", "cv"), profile["cv_raw_text"])


@router.post("/import-linkedin")
async def sync_linkedin_profile(body: LinkedInImportRequest):
    try:
        return await import_linkedin_profile(body.profile_text)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/review")
async def review_profile():
    try:
        return await review_linkedin_profile()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/notes")
def get_notes():
    return list_project_notes()


@router.post("/notes")
def add_note(body: ProjectNoteCreate):
    return create_project_note(body)


@router.delete("/notes/{note_id}")
def remove_note(note_id: int):
    delete_project_note(note_id)
    return {"deleted": True}
