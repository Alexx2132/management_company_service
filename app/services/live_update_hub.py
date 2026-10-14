import asyncio
from threading import Lock

from fastapi import HTTPException, WebSocket

from app.api.dependencies import authenticate_token, require_password_changed
from app.db.session import SessionLocal
from app.models.user import UserRole


def can_receive_update(db, user, payload: dict) -> bool:
    # Проверяем актуальные права на объект, даже если роль или назначение изменились после подключения.
    from app.models.message import MessageParticipant
    from app.models.ban_appeal import BanConversation
    from app.models.ticket_complaint import ComplaintComment
    from app.services.ticket_service import TicketService
    from app.services.ticket_complaint_service import TicketComplaintService

    entity = payload.get("entity")
    try:
        if entity == "ticket":
            if payload.get("complaint_id") is not None:
                TicketComplaintService(db)._get_accessible_complaint(payload["complaint_id"], user)
            ticket = TicketService(db).get_ticket(payload.get("ticket_id"), user)
            return user.role != UserRole.EXECUTOR or ticket.executor_id == user.id
        if entity == "complaint":
            service = TicketComplaintService(db)
            complaint = service._get_accessible_complaint(payload.get("complaint_id"), user)
            if payload.get("comment_id") is not None:
                comment = db.get(ComplaintComment, payload["comment_id"])
                return comment is not None and comment.complaint_id == complaint.id and service._comment_visible_for_user(complaint, comment, user)
            return True
        if entity == "message":
            return db.query(MessageParticipant.id).filter_by(
                conversation_id=payload.get("conversation_id"), user_id=user.id,
            ).first() is not None
        if entity == "ban_appeal":
            conversation = db.get(BanConversation, payload.get("conversation_id"))
            return conversation is not None and (
                user.role == UserRole.ADMIN or conversation.resident_id == user.id
            )
        if entity == "notification":
            if payload.get("user_id") is not None:
                return payload["user_id"] == user.id
            if payload.get("kind") == "ticket_created" and user.role in {UserRole.ADMIN, UserRole.DISPATCHER}:
                TicketService(db).get_ticket(payload.get("ticket_id"), user)
                return True
    except HTTPException:
        return False
    return False


class LiveUpdateHub:
    def __init__(self) -> None:
        self._connections: dict[WebSocket, str] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        with self._lock:
            self._loop = loop

    async def connect(self, websocket: WebSocket, token: str) -> None:
        await websocket.accept()
        with self._lock:
            self._connections[websocket] = token

    def disconnect(self, websocket: WebSocket) -> None:
        with self._lock:
            self._connections.pop(websocket, None)

    async def broadcast(self, payload: dict) -> None:
        with self._lock:
            connections = list(self._connections.items())

        stale_connections: list[WebSocket] = []
        for websocket, token in connections:
            try:
                async with SessionLocal() as db:
                    user = require_password_changed(await authenticate_token(token, db))
                    allowed = await db.run_sync(lambda session: can_receive_update(session, user, payload))
                if allowed:
                    await asyncio.wait_for(websocket.send_json(payload), timeout=5)
            except HTTPException:
                stale_connections.append(websocket)
                try:
                    await websocket.close(code=1008)
                except Exception:
                    pass
            except Exception:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            self.disconnect(websocket)

    def broadcast_from_sync(self, payload: dict) -> None:
        with self._lock:
            loop = self._loop

        if loop is None or loop.is_closed():
            return

        future = asyncio.run_coroutine_threadsafe(self.broadcast(payload), loop)

        def _consume_exception(done_future):
            try:
                done_future.exception()
            except Exception:
                return

        future.add_done_callback(_consume_exception)


live_update_hub = LiveUpdateHub()
