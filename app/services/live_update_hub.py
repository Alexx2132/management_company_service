import asyncio
from threading import Lock

from fastapi import WebSocket


class LiveUpdateHub:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._lock:
            self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        with self._lock:
            self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, payload: dict) -> None:
        with self._lock:
            connections = list(self._connections)

        stale_connections: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_json(payload)
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
