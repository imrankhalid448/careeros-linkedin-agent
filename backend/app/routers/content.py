import uuid
from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from app.config import UPLOADS_DIR
from app.models.schemas import (
    CommentGenerateRequest,
    CommentUpdateRequest,
    PostGenerateRequest,
    PostUpdateRequest,
)
from app.services.content_service import (
    attach_generated_image,
    attach_uploaded_image,
    generate_comment_draft,
    generate_post_draft,
    list_comments,
    list_posts,
    publish_comment_now,
    publish_post_now,
    remove_post_image,
    update_comment,
    update_post,
)

router = APIRouter(prefix="/api/content", tags=["content"])


@router.get("/posts")
def get_posts():
    return list_posts()


@router.post("/posts/generate")
async def create_post_draft(body: PostGenerateRequest):
    try:
        return await generate_post_draft(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/posts/{post_id}")
def edit_post(post_id: int, body: PostUpdateRequest):
    try:
        return update_post(post_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/posts/{post_id}/publish")
async def approve_and_publish_post(post_id: int):
    try:
        return await publish_post_now(post_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/posts/{post_id}/generate-image")
async def generate_image_for_post(post_id: int, custom_prompt: str = Body("", embed=True)):
    try:
        return await attach_generated_image(post_id, custom_prompt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/posts/{post_id}/upload-image")
async def upload_image_for_post(post_id: int, file: UploadFile = File(...)):
    ext = (file.filename or "image.png").split(".")[-1].lower()
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        raise HTTPException(status_code=400, detail="Use .png, .jpg, .jpeg, or .webp image.")
    filename = f"upload_{uuid.uuid4().hex[:10]}.{ext}"
    (UPLOADS_DIR / filename).write_bytes(await file.read())
    try:
        return attach_uploaded_image(post_id, filename)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/posts/{post_id}/image")
def delete_image_for_post(post_id: int):
    try:
        return remove_post_image(post_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/comments")
def get_comments():
    return list_comments()


@router.post("/comments/generate")
async def create_comment_draft(body: CommentGenerateRequest):
    try:
        return await generate_comment_draft(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/comments/reply-now")
async def reply_to_comment_now(body: CommentGenerateRequest):
    try:
        draft = await generate_comment_draft(body)
        if draft.get("needs_more_context"):
            return draft
        result = await publish_comment_now(draft["comment"]["id"])
        return {
            "generated": draft,
            "comment": result["comment"],
            "message": result["message"],
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/comments/{comment_id}")
def edit_comment(comment_id: int, body: CommentUpdateRequest):
    try:
        return update_comment(comment_id, body.draft_reply)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/comments/{comment_id}/publish")
async def approve_and_publish_comment(comment_id: int):
    try:
        return await publish_comment_now(comment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
