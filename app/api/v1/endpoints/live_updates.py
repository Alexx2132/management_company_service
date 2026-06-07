from urllib.parse import unquote

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt

from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories.user_repository import UserRepository
from app.schemas.token import TokenData
from app.services.live_update_hub import live_update_hub

router = APIRouter()


def _normalize_ws_token(raw_token: str | None) -> str:
    if not raw_token:
        return ""
    token = unquote(str(raw_token)).strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in {"'", '"'}:
        token = token[1:-1]
    return token


@router.websocket("/updates")
async def websocket_updates(websocket: WebSocket):
    token = _normalize_ws_token(websocket.cookies.get("uk_token") or websocket.query_params.get("token"))
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    db = SessionLocal()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        token_data = TokenData(user_id=user_id)
        user = UserRepository(db).get_by_id(int(token_data.user_id))
        if user is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await live_update_hub.connect(websocket)
        while True:
            await websocket.receive_text()
    except (JWTError, ValueError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    except WebSocketDisconnect:
        live_update_hub.disconnect(websocket)
    finally:
        live_update_hub.disconnect(websocket)
        db.close()
