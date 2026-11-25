import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import UPLOADS_DIR, settings
from app.database import init_db
from app.routers import autopilot, chat, connectors, content, jobs, profile, settings as settings_router
from app.services.autopilot_service import queue_autopilot_posts
from app.services.content_service import process_due_scheduled_posts

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    scheduler.add_job(process_due_scheduled_posts, "interval", seconds=30, id="scheduled_posts")
    scheduler.add_job(
        queue_autopilot_posts,
        "interval",
        minutes=5,
        id="autopilot_queue",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now() + timedelta(seconds=20),
    )
    scheduler.start()
    asyncio.create_task(queue_autopilot_posts())
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Personal Career & LinkedIn AI Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router)
app.include_router(content.router)
app.include_router(jobs.router)
app.include_router(connectors.router)
app.include_router(autopilot.router)
app.include_router(chat.router)
app.include_router(settings_router.router)
app.mount("/api/media", StaticFiles(directory=str(UPLOADS_DIR)), name="media")


@app.get("/api/health")
def health():
    return {"status": "ok"}
