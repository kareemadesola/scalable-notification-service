"""
In-App Notification Service
- FastAPI app with WebSocket support
- Connected clients register by user_id
- When a notification is written to DB via the API, this service
  broadcasts it to all active WebSocket connections for that user
- Exposes GET /ws/{user_id} for WebSocket connections
- Exposes GET /inapp/notifications/{user_id} for offline inbox (poll)
"""
import asyncio
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import DefaultDict

import asyncpg
import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

logger = structlog.get_logger()

DATABASE_URL = os.environ["DATABASE_URL"]

# user_id -> set of active WebSocket connections
_connections: DefaultDict[str, set[WebSocket]] = defaultdict(set)


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(1, 11):
        try:
            app.state.db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)
            break
        except Exception as exc:
            logger.warning("DB connection failed, retrying", attempt=attempt, error=str(exc))
            if attempt == 10:
                raise
            await asyncio.sleep(attempt * 2)
    logger.info("In-App service started")
    yield
    await app.state.db_pool.close()
    logger.info("In-App service shut down")


app = FastAPI(title="In-App Notification Service", lifespan=lifespan)


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await websocket.accept()
    _connections[user_id].add(websocket)
    logger.info("WebSocket connected", user_id=user_id, total=len(_connections[user_id]))

    try:
        # Send any unread pending in-app notifications on connect
        pool = websocket.app.state.db_pool
        rows = await pool.fetch(
            """
            SELECT id, subject, body, metadata, created_at
            FROM notifications
            WHERE user_id = $1
              AND channel = 'inapp'
              AND is_read = FALSE
            ORDER BY created_at DESC
            LIMIT 50
            """,
            user_id,
        )
        for row in rows:
            await websocket.send_json({
                "id": row["id"],
                "subject": row["subject"],
                "body": row["body"],
                "metadata": row["metadata"],
                "created_at": row["created_at"].isoformat(),
            })

        # Keep connection alive; client can send pings
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        _connections[user_id].discard(websocket)
        if not _connections[user_id]:
            del _connections[user_id]
        logger.info("WebSocket disconnected", user_id=user_id)


@app.post("/inapp/broadcast/{user_id}")
async def broadcast(user_id: str, payload: dict):
    """
    Called internally by the Notification API after writing an in-app
    notification to the DB. Pushes to all active connections for the user.
    """
    sockets = _connections.get(user_id, set())
    dead = set()
    for ws in sockets:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    for ws in dead:
        sockets.discard(ws)

    logger.info("Broadcast sent", user_id=user_id, recipients=len(sockets) - len(dead))
    return {"delivered_to": len(sockets) - len(dead)}
