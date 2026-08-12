import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSockets"])

@router.websocket("/ws/{run_id}")
async def websocket_run_events(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for real-time optimization run event streaming.
    Subscribes to Redis pub/sub channel for the given run_id.
    Falls back to polling DB if Redis is unavailable.
    """
    from core.validators import validate_run_id
    from auth.middleware import decode_token
    from db.runs_repository import RunsRepository

    try:
        validate_run_id(run_id)
    except Exception:
        await websocket.close(code=1008, reason="Invalid run_id format")
        return

    # JWT Authentication
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return
        
    try:
        payload = decode_token(token)
        user_id = payload.get("user_id")
    except Exception:
        await websocket.close(code=1008, reason="Invalid token")
        return

    run = await RunsRepository.get_run(run_id)
    if not run:
        await websocket.close(code=1008, reason="Run not found")
        return
        
    if str(run.get("created_by")) != str(user_id) and run.get("created_by") is not None:
        await websocket.close(code=1008, reason="Forbidden")
        return

    await websocket.accept()
    logger.info(f"WebSocket connected for run {run_id} by user {user_id}")

    try:
        from cache.redis_client import get_redis
        redis = await get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"run:{run_id}:events")

        # Send initial status from DB
        try:
            if run:
                from core.events import CanonicalEvent, EventData
                initial_event = CanonicalEvent(
                    event="initial_status",
                    run_id=run_id,
                    status=run.get("status", "queued"),
                    phase=run.get("plan", {}).get("phase") if isinstance(run.get("plan"), dict) else "planning"
                )
                await websocket.send_json(initial_event.model_dump())
        except Exception as db_err:
            logger.warning(f"Could not fetch initial status for {run_id}: {db_err}")

        # Listen for events
        while True:
            try:
                message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=30.0)
                if message and message.get("type") == "message":
                    data = message.get("data", "{}")
                    event = json.loads(data) if isinstance(data, str) else data
                    await websocket.send_json(event)

                    # Close cleanly when run completes
                    if event.get("event") in ("run_complete", "run_failed"):
                        await websocket.close()
                        break
                else:
                    # Send keepalive ping
                    await websocket.send_json({"event": "heartbeat", "run_id": run_id})
            except asyncio.TimeoutError:
                await websocket.send_json({"event": "heartbeat", "run_id": run_id})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for run {run_id}")
    except Exception as e:
        logger.error(f"WebSocket error for run {run_id}: {e}")
        try:
            await websocket.send_json({"event": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await pubsub.unsubscribe(f"run:{run_id}:events")
        except Exception:
            pass
