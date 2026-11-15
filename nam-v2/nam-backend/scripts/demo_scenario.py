#!/usr/bin/env python3
"""Demo scenario: Jezero sol-1245 SEP evacuation drill.

End-to-end test of the v2 backend's storm-response planning:
1. Simulate an X-class solar particle event at Jezero
2. Plan a storm response: fetch event -> find shelters -> plan terrain-averse route -> assess dose
3. Print the full evacuation plan with provenance
"""
import json
import requests
import sys

BASE = "http://127.0.0.1:8000"

print("=" * 70)
print("NAM v2 demo scenario: Jezero sol-1245 SEP evacuation drill")
print("=" * 70)

print("\n[1/6] Checking backend health...")
r = requests.get(f"{BASE}/health", timeout=5)
assert r.status_code == 200, f"backend not healthy: {r.status_code}"
print(f"  backend OK: {r.json()['version']}, data_loaded={r.json()['data_loaded']}")

print("\n[2/6] Initializing at Jezero crater (18.4447N, 77.4508E)...")
r = requests.get(f"{BASE}/api/v1/walk/init", params={"lat": 18.4447, "lon": 77.4508, "heading_deg": 0}, timeout=10)
w = r.json()
print(f"  Terrain elevation: {w['elev_m']} m above MOLA areoid")
print(f"  Eye elevation:     {w['eye_elev_m']} m (incl. 1.7 m suit)")
print(f"  Local slope:       {w['slope_deg']} deg")
print(f"  Local roughness:   {w['roughness_m']} m")

print("\n[3/6] Baseline radiation at Jezero (no SEP)...")
r = requests.get(f"{BASE}/api/v1/radiation", params={"lat": 18.4447, "lon": 77.4508}, timeout=10)
rad = r.json()
print(f"  Baseline dose:     {rad['dose_mSv_per_day']} mSv/day  (~{rad['dose_mSv_per_year']} mSv/year)")
print(f"  Career limit frac: {rad['annual_career_limit_fraction_pct']}% of NASA 1 Sv/year")
print(f"  Provenance:        {rad['model']['reference']}")

print("\n[4/6] SIMULATING X-class solar particle event at Jezero...")
r = requests.post(f"{BASE}/api/v1/env/storms/simulate",
                  params={"kind": "sep", "lat": 18.4447, "lon": 77.4508, "severity": "X-flare-class"},
                  timeout=10)
event = r.json()["event"]
print(f"  Event ID:        {event['id']}")
print(f"  Kind:            {event['kind']} (severity {event['severity']})")
print(f"  Duration:        {event['duration_sols']} sols")
print(f"  Intensity:       peak_flux {event['intensity']['peak_flux_pfu']} pfu, dose equiv {event['intensity']['dose_equiv_msv']} mSv")
print(f"  Operational:     EVA halt={event['operational_impact']['eva_halt']}, shelter required={event['operational_impact']['shelter_required']}")
print(f"  Provenance:      {event['provenance']['model']}")
print(f"  Reference:       {event['provenance']['reference']}")

print("\n[5/6] Assistant planning storm response via chat...")
r = requests.post(f"{BASE}/api/v1/assistant/chat",
                  json={"message": f"plan storm response for event {event['id']} from 18.4447, 77.4508"},
                  stream=True, timeout=60)
text_chunks = []
tool_calls = []
result = None
for line in r.iter_lines():
    if line and line.startswith(b"data: "):
        ev = json.loads(line[6:].decode("utf-8"))
        if ev.get("type") == "token":
            text_chunks.append(ev["text"])
        elif ev.get("type") == "tool_call":
            tool_calls.append(ev)
        elif ev.get("type") == "result":
            result = ev.get("result")
        elif ev.get("type") == "done":
            break
print(f"  Assistant text:  {''.join(text_chunks)[:300]}")
print(f"  Tool calls:      {[tc.get('tool') for tc in tool_calls]}")

print("\n[6/6] Direct storm-response plan via assistant.tool endpoint...")
r = requests.post(f"{BASE}/api/v1/assistant/tool/plan_storm_response",
                  json={"event_id": event["id"], "current_lat": 18.4447, "current_lon": 77.4508},
                  timeout=30)
plan = r.json()["result"]
print(f"\n  Evacuation plan:")
print(f"    Event:         {plan['event']['kind']} ({plan['event']['severity']})")
print(f"    Current pos:   ({plan['current_position']['lat']}, {plan['current_position']['lon']})")
print(f"    Shelters found: {len(plan['shelters_within_reach'])}")
if plan.get("recommended_shelter"):
    sh = plan["recommended_shelter"]
    print(f"    Recommended:   {sh['name']} ({sh['kind']}, {sh['distance_km']} km)")
    print(f"                   scores: sheltering={sh['scores']['sheltering_index']}, "
          f"rad_shield={sh['scores']['radiation_shielding']}, "
          f"therm={sh['scores']['thermal_stability']}, "
          f"access={sh['scores']['access_difficulty']}")
    print(f"    Reference:     {sh['published_reference']}")
if plan.get("route_to_shelter"):
    rt = plan["route_to_shelter"]
    print(f"    Route:         preset={rt['preset']}, ok={rt['ok']}")
    if rt.get("stats"):
        s = rt["stats"]
        print(f"                   length {s['length_km']} km, ascent {s['ascent_m']} m, max slope {s['max_slope_deg']} deg")
        print(f"                   est {s['est_sols']} sols at 100 m/sol EVA pace")
    print(f"                   {rt.get('waypoints_count', 0)} waypoints sampled")
if plan.get("dose_estimate"):
    de = plan["dose_estimate"]
    print(f"    Dose estimate: {de['total_dose_mSv']} mSv total over {de['path_length_km']} km path")
    print(f"                   per-step doses: {len(de['steps'])} sampled points")

print("\n" + "=" * 70)
print("Demo complete. Every value labelled [SIM] or [MODELLED] is advisory.")
print("Provenance:")
print("  Elevation:    MOLA MEGDR 4 px/deg (NASA PDS)")
print("  Roughness:    MOLA roughness 1 px/deg (NASA PDS)")
print("  Radiation:    RAD on Curiosity, Hassler et al. 2014, Science 343, 1244797")
print("  SEP events:   Guo et al. 2018, Space Weather 16, 977-988")
print("  Dust events:  Montabone et al. 2015, Icarus 251, 65-95 (MY34 PEDE)")
print("  Shelters:     Cushing et al. 2007 (lava-tube skylights) + USGS SIM 3292 (Tanaka 2014)")
print("  Water ice:    SWIM project, swim.psi.edu (Morgan et al. 2021, Nat. Astron.)")
print("=" * 70)
