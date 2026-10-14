import asyncio
import os
from asyncpg import PostgresError
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import router as api_router
from app.api.attachments import router as attachment_router, PublicBackgrounds
from app.core.config import settings
from app.db.session import engine
from app.services.live_update_hub import live_update_hub
from app.services.push_notification_service import finish_push_deliveries


@asynccontextmanager
async def lifespan(_: FastAPI):
    live_update_hub.set_loop(asyncio.get_running_loop())
    try:
        yield
    finally:
        live_update_hub.set_loop(None)
        await finish_push_deliveries()
        await engine.dispose()


app = FastAPI(title=settings.APP_TITLE, lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.include_router(attachment_router)
os.makedirs("static/uploads/settings", exist_ok=True)
app.mount("/static/uploads/settings", PublicBackgrounds(directory="static/uploads/settings"), name="public-backgrounds")


@app.get("/ping")
def ping():
    return {"status": "pong", "message": "Server is alive!"}


app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
async def readiness_check():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, PostgresError, OSError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    return {"status": "ok"}
