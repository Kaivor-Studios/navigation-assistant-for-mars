"""Smoke tests for the NAM backend.

Run with: pytest -v
Or run the script directly: python3 tests/test_smoke.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the app + verify all modules load
from app.main import app
from app.core.geo import sample_elevation, slope_at, hazard_at
from app.core.router import plan_route, PRESETS
from app.core.environment import find_shelters, find_water, assess_radiation
from app.core.walk import walk_init, walk_terrain_patch
from app.core.assistant import list_tools, invoke_tool, chat_respond
from app.core.sim import create_event, list_events


def test_elevation_spot_checks():
    """Verify the MOLA grid samples match published values."""
    # Jezero crater: ~-2.6 km
    assert -3500 < sample_elevation(18.4447, 77.4508) < -2000
    # Olympus Mons summit region: ~+21 km
    assert 19000 < sample_elevation(18.65, 226.2) < 23000
    # Hellas Planitia: deep basin
    assert sample_elevation(-42.4, 70.0) < -4000
    # Valles Marineris: deep canyon
    assert sample_elevation(-13.9, 302.0) < -4000


def test_slope_at_grid():
    s = slope_at(18.4447, 77.4508)
    assert s is not None and 0 <= s < 30


def test_hazard_returns_class():
    h = hazard_at(18.4447, 77.4508)
    assert h.hazard_class in ("low", "moderate", "high", "extreme")
    assert 0 <= h.hazard_score <= 100


def test_route_plan_jezero_to_nili():
    r = plan_route(18.4447, 77.4508, 24.0, 80.0, preset="balanced")
    assert r.ok
    assert r.stats.length_km > 0
    assert len(r.waypoints) >= 1


def test_route_plan_presets():
    for p in ("balanced", "terrain", "speed"):
        r = plan_route(0.0, 0.0, 5.0, 5.0, preset=p)
        assert r.preset == p


def test_find_shelters_jezero():
    s = find_shelters(18.4447, 77.4508, max_radius_km=1000)
    assert s["count"] >= 1


def test_find_water():
    w = find_water(18.4447, 77.4508, max_radius_km=500)
    assert w["count"] >= 1


def test_radiation_baseline():
    r = assess_radiation(0.0, 0.0)
    assert 0.1 < r["dose_mSv_per_day"] < 1.5  # sanity: 0.21 mSv/day baseline ± atmospheric factor


def test_walk_init():
    w = walk_init(18.4447, 77.4508)
    assert w["elev_m"] < 0  # Jezero is below the datum
    assert w["eye_height_m"] == 1.7
    assert "provenance" in w


def test_walk_terrain_patch():
    p = walk_terrain_patch(18.4447, 77.4508, radius_m=500, resolution_m=25)
    assert p["grid_shape"][0] >= 20
    assert len(p["heights_m"]) > 100


def test_assistant_tools_count():
    tools = list_tools()
    # 16 v1 + 8 new + 1 extra (enter_walk_view) = 25
    assert len(tools) >= 24


def test_assistant_chat_jezero():
    r = chat_respond("where is Jezero crater?")
    assert "Jezero" in r["text"] or "jezero" in r["text"].lower()


def test_assistant_chat_shelters():
    r = chat_respond("find shelters near Olympus Mons")
    # Should invoke find_shelter tool
    assert any(tc["tool"] == "find_shelter" for tc in r.get("tool_calls", [])) or "shelter" in r["text"].lower()


def test_sim_event():
    e = create_event(kind="sep", lat=18.0, lon=77.0, severity="X-flare-class")
    assert e["kind"] == "sep"
    assert e["severity"] == "X-flare-class"
    assert e["operational_impact"]["shelter_required"] is True


def test_health_endpoint():
    """Verify the FastAPI app instance has /health registered."""
    paths = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/health" in paths
    assert "/api/v1/elevation" in paths
    assert "/api/v1/walk/init" in paths
    assert "/api/v1/assistant/chat" in paths
    assert "/ws/events" in paths


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
