from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.router import router as api_router
from fastapi.staticfiles import StaticFiles
import os


app = FastAPI(title=settings.APP_TITLE)

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
