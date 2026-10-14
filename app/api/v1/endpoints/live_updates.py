import asyncio
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.db.session import SessionLocal
from app.api.dependencies import authenticate_token, require_password_changed
from app.services.live_update_hub import live_update_hub

router = APIRouter()


def _normalize_ws_token(raw_token: str | None) -> str:
    if not raw_token:
        return ""
    token = unquote(str(raw_token)).strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in {"'", '"'}:
        token = token[1:-1]
    return token[7:] if token.lower().startswith("bearer ") else token


@router.websocket("/updates")
async def websocket_updates(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    own_origin = str(websocket.url.replace(
        scheme="https" if websocket.url.scheme == "wss" else "http", path="", query="",
    )).rstrip("/")
    if origin and origin not in {*settings.CORS_ORIGINS, own_origin}:
        await websocket.close(code=1008)
        return
    token = _normalize_ws_token(
        websocket.headers.get("authorization") or websocket.cookies.get("uk_token")
        or websocket.query_params.get("token")
    )

    try:
        async with SessionLocal() as db:
            require_password_changed(await authenticate_token(token, db))
        await live_update_hub.connect(websocket, token)
        while True:
            # Соединение не держит транзакцию; отзыв JWT проверяется даже без новых событий.
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=15)
            except TimeoutError:
                message = None
            async with SessionLocal() as db:
                require_password_changed(await authenticate_token(token, db))
            if message == "ping":
                await websocket.send_text("pong")
    except HTTPException:
        await websocket.close(code=1008)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        live_update_hub.disconnect(websocket)
