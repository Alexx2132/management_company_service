import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import router as api_router
from app.core.config import settings
from app.services.live_update_hub import live_update_hub


@asynccontextmanager
async def lifespan(_: FastAPI):
    live_update_hub.set_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title=settings.APP_TITLE, lifespan=lifespan)

# CORS для web frontend (Nuxt dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/ping")
def ping():
    return {"status": "pong", "message": "Server is alive!"}


app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok"}
