"""WebSocket handlers for /ws/events and /ws/presence."""
from __future__ import annotations
import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core.sim import list_presence, list_events, tick_presence


ws_router = APIRouter()


class ConnectionManager:
    """Track connected clients per channel so any service can broadcast."""
    def __init__(self):
        # channel -> set of WebSocket
        self._channels: dict[str, set[WebSocket]] = {"events": set(), "presence": set()}

    async def connect(self, channel: str, ws: WebSocket):
        await ws.accept()
        self._channels.setdefault(channel, set()).add(ws)

    def disconnect(self, channel: str, ws: WebSocket):
        self._channels.get(channel, set()).discard(ws)

    async def broadcast(self, channel: str, message: dict):
        for ws in list(self._channels.get(channel, set())):
            try:
                await ws.send_text(json.dumps(message, ensure_ascii=False))
            except Exception:
                self._channels[channel].discard(ws)


manager = ConnectionManager()


@ws_router.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    """Multiplexed event stream.

    Sends a welcome message on connect, then forwards any events broadcast
    to the 'events' channel (storm.alert, presence.update, plan.changed,
    telemetry.tick). Other parts of the app can publish events via
    `await manager.broadcast('events', {...})`.
    """
    await manager.connect("events", websocket)
    try:
        await websocket.send_text(json.dumps({
            "type": "hello",
            "channel": "events",
            "subscribed": ["storm.alert", "presence.update", "plan.changed", "telemetry.tick"],
            "server_time": time.time(),
        }))
        # Drive a 1 Hz telemetry tick + occasional presence updates
        last_presence_tick = 0.0
        while True:
            await asyncio.sleep(1.0)
            # Telemetry tick
            await websocket.send_text(json.dumps({
                "type": "telemetry.tick",
                "sol": 1245,
                "simulated": True,
                "timestamp": time.time(),
            }))
            # Presence update every 5 s
            if time.time() - last_presence_tick > 5.0:
                tick_presence()
                await websocket.send_text(json.dumps({
                    "type": "presence.update",
                    "agents": list_presence(),
                    "simulated": True,
                }))
                last_presence_tick = time.time()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect("events", websocket)


@ws_router.websocket("/ws/presence")
async def ws_presence(websocket: WebSocket):
    """Dedicated presence stream (1 Hz)."""
    await manager.connect("presence", websocket)
    try:
        await websocket.send_text(json.dumps({
            "type": "hello",
            "channel": "presence",
            "agents": list_presence(),
            "simulated": True,
        }))
        while True:
            await asyncio.sleep(1.0)
            tick_presence()
            await websocket.send_text(json.dumps({
                "type": "presence.update",
                "agents": list_presence(),
                "simulated": True,
                "timestamp": time.time(),
            }))
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect("presence", websocket)


async def publish_storm_alert(event: dict):
    """Broadcast a storm.alert event to all /ws/events subscribers."""
    await manager.broadcast("events", {
        "type": "storm.alert",
        "event": event,
    })
