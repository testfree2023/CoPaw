# -*- coding: utf-8 -*-
"""WebSocket router for real-time task progress streaming.

This module provides WebSocket endpoints for:
- Subscribing to task progress updates
- Receiving real-time task status changes
"""
import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..runner.task_queue import TaskQueue

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tasks-websocket"])

# Global task queue reference
_task_queue = None

# WebSocket connections: task_id -> set of WebSocket connections
_active_connections: Dict[str, Set[WebSocket]] = {}


def set_task_queue(task_queue: TaskQueue) -> None:
    """Set task queue for WebSocket router."""
    global _task_queue
    _task_queue = task_queue
    logger.debug("Task queue set for WebSocket router")


class TaskProgressBroadcaster:
    """Broadcast task progress updates to WebSocket clients."""

    @staticmethod
    async def broadcast(task_id: str, event: dict) -> None:
        """Broadcast event to all clients subscribed to task_id.

        Args:
            task_id: Task UUID
            event: Event dict with type, data fields
        """
        if task_id not in _active_connections:
            return

        message = json.dumps({
            "task_id": task_id,
            "event": event,
        })

        disconnected = set()
        for ws in _active_connections[task_id]:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.add(ws)

        # Clean up disconnected clients
        for ws in disconnected:
            _active_connections[task_id].discard(ws)

        if not _active_connections[task_id]:
            del _active_connections[task_id]


@router.websocket("/task-ws/{task_id}")
async def task_progress_websocket(
    websocket: WebSocket,
    task_id: str,
) -> None:
    """WebSocket endpoint for task progress streaming.

    Clients connect to /task-ws/{task_id} to receive:
    - Task status changes (pending -> processing -> completed/failed)
    - Progress updates (agent thoughts, tool usage)
    - Final results

    Args:
        websocket: WebSocket connection
        task_id: Task UUID to subscribe to
    """
    await websocket.accept()

    # Subscribe to task
    if task_id not in _active_connections:
        _active_connections[task_id] = set()
    _active_connections[task_id].add(websocket)

    logger.info(f"Client subscribed to task {task_id}")

    # Send current task status immediately
    if _task_queue:
        task = await _task_queue.get_task(task_id)
        if task:
            # Send complete task state including result
            await websocket.send_text(json.dumps({
                "task_id": task_id,
                "event": {
                    "type": "status",
                    "status": task.status.value,
                    "task": task.model_dump(mode="json"),
                    "response": task.llm_response,
                    "verified": task.verification_result,
                    "verification_details": task.verification_details,
                    "last_error": task.last_error,
                },
            }))

    try:
        # Keep connection alive and handle client messages
        while True:
            try:
                # Handle any messages from client (ping/pong, unsubscribe)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0,
                )
                # Client can send {"action": "unsubscribe"} to close
                msg = json.loads(data)
                if msg.get("action") == "unsubscribe":
                    break
            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.ping()
    except WebSocketDisconnect:
        logger.debug(f"Client disconnected from task {task_id}")
    except Exception as e:
        logger.exception(f"WebSocket error for task {task_id}: {e}")
    finally:
        # Unsubscribe
        if task_id in _active_connections:
            _active_connections[task_id].discard(websocket)
            if not _active_connections[task_id]:
                del _active_connections[task_id]
        logger.info(f"Client unsubscribed from task {task_id}")
