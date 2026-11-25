from fastapi import APIRouter
from app.models.schemas import ChatRequest
from app.services.chat_service import get_chat_history, handle_chat_message

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/history")
def read_history():
    return get_chat_history()


@router.post("")
async def send_chat(body: ChatRequest):
    return await handle_chat_message(body.message)
