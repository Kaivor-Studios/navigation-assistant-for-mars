"""Pydantic models for request/response validation."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Optional


class LatLonIn(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-360, le=360)


class NodeIn(BaseModel):
    name: str
    type: str = "waypoint"
    lat: float
    lon: float
    radius_m: float = 0.0
    properties: dict = {}


class RouteIn(BaseModel):
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    preset: str = "balanced"


class MissionIn(BaseModel):
    name: str
    objective: str = ""
    kind: str = "route"


class WaypointIn(BaseModel):
    lat: float
    lon: float
    name: str = "WP"


class StopIn(BaseModel):
    lat: float
    lon: float
    reason: str = ""
    activity: str = ""


class ChatIn(BaseModel):
    message: str
    mission_id: Optional[str] = None
