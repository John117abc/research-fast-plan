"""Gate B1 Waymo adapter (plant2 side): canonical state -> corridor-local geometry.

Canonical state is produced by the waymo_rc extractor and contains raw parsed
Waymo fields only. This module does NO R1 / collision / feasible math; it only
builds the map/actor interface consumed by the frozen gate_b0 engine.
"""
import json
import math

import numpy as np


def load_canonical(path):
    return json.load(open(path))


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def polyline_np(lane):
    return np.array(lane["polyline"], float)  # (N,3)


def project_point(px, py, poly):
    """Nearest point on polyline: returns (s_arc, lat_signed, heading, dist)."""
    p = np.array([px, py])
    best = None
    s_accum = 0.0
    for i in range(len(poly) - 1):
        a, b = poly[i, :2], poly[i + 1, :2]
        ab = b - a
        L = np.linalg.norm(ab)
        if L < 1e-9:
            continue
        t = float(np.clip(np.dot(p - a, ab) / (L * L), 0.0, 1.0))
        proj = a + t * ab
        d = np.linalg.norm(p - proj)
        h = math.atan2(ab[1], ab[0])
        if best is None or d < best[3]:
            # signed lateral: left of segment direction is +
            n = np.array([-math.sin(h), math.cos(h)])
            lat = float(np.dot(p - proj, n))
            best = (s_accum + t * L, lat, h, d)
        s_accum += L
    return best if best is not None else (0.0, 0.0, 0.0, 1e9)


def find_ego_lane(ego, lanes):
    """Nearest driving-lane centerline whose direction passes through the ego."""
    best = None
    for lane in lanes:
        if lane.get("type", 2) not in (1, 2):   # driving lanes only
            continue
        poly = polyline_np(lane)
        s, lat, h, d = project_point(ego["x"], ego["y"], poly)
        dh = abs(wrap(h - ego["heading"]))
        if dh > math.radians(30) or abs(lat) > 2.5:
            continue
        score = abs(lat)
        if best is None or score < best[0]:
            best = (score, lane, s, lat, h)
    if best is None:
        return None
    return {"lane": best[1], "s": best[2], "lat": best[3], "heading": best[4]}


def find_left_lane(ego, ego_lane, lanes, horizon_s=8.0):
    """Strict geometric left-adjacent same-direction driving lane.

    Requires: same driving type, heading diff < 20 deg, median lateral offset in
    [2.5,4.5] m, lateral std < 0.8 m over the overlap, and >= 40 m of overlap
    ahead. Deterministic; returns None when no such lane exists.
    """
    u = np.array([math.cos(ego["heading"]), math.sin(ego["heading"])])
    n = np.array([-math.sin(ego["heading"]), math.cos(ego["heading"])])
    et = ego_lane["lane"].get("type", 2)
    best = None
    for lane in lanes:
        if lane["id"] == ego_lane["lane"]["id"] or lane.get("type", 2) != et:
            continue
        poly = polyline_np(lane)
        dxy = poly[:, :2] - np.array([ego["x"], ego["y"]])
        lon = dxy @ u
        lat = dxy @ n
        m = (lon > -10) & (lon < max(60.0, horizon_s * 12.0))
        if m.sum() < 5:
            continue
        lat_m = lat[m]
        lon_m = lon[m]
        if (lon_m.max() - lon_m.min()) < 40.0:
            continue
        if not (2.5 <= np.median(lat_m) <= 4.5) or np.std(lat_m) > 0.8:
            continue
        _, _, h, _ = project_point(ego["x"], ego["y"], poly)
        if abs(wrap(h - ego["heading"])) > math.radians(20):
            continue
        score = abs(float(np.median(lat_m)) - 3.5)
        if best is None or score < best[0]:
            best = (score, lane, float(np.median(lat_m)), h)
    if best is None:
        return None
    return {"lane": best[1], "lat": best[2], "heading": best[3], "lane_width": best[2]}


def lane_width_from_pair(ego_lane, left_lane):
    return left_lane["lane_width"]


def json_lanes(js):
    """Convert data_json 'roads' to adapter lanes (map_element_id = lane type)."""
    lanes = []
    for r in js["roads"]:
        if r["type"] != "lane":
            continue
        lanes.append({"id": r["id"], "type": r.get("map_element_id", 2),
                      "polyline": [[p["x"], p["y"], p.get("z", 0.0)] for p in r["geometry"]],
                      "entry_lanes": [], "exit_lanes": []})
    return lanes


def ego_state_from_json(js, idx=None):
    if idx is None:
        idx = 10
    o = js["objects"][js["metadata"]["sdc_track_index"]]
    return {"x": o["position"][idx]["x"], "y": o["position"][idx]["y"],
            "heading": o["heading"][idx],
            "vx": o["velocity"][idx]["x"], "vy": o["velocity"][idx]["y"],
            "speed": math.hypot(o["velocity"][idx]["x"], o["velocity"][idx]["y"]),
            "length": o["length"], "width": o["width"], "idx": idx,
            "valid": bool(o["valid"][idx])}


def ego_state(canonical, idx=None):
    if idx is None:
        idx = canonical["current_time_index"]
    f = canonical["ego"]["frames"][idx]
    return {"x": f["x"], "y": f["y"], "heading": f["heading"],
            "vx": f["vx"], "vy": f["vy"], "speed": math.hypot(f["vx"], f["vy"]),
            "length": f["length"], "width": f["width"], "idx": idx}


def build_slots(canonical, ego, horizon_s=8.0, dt=0.5, lat_filter=4.0):
    """Occupancy frames (dt grid) in ego frame: (s_abs, lat, hl, hw).

    s_abs is longitudinal distance from ego position along ego heading; lat is
    lateral (+left). The frozen engine expects current corridor at lat 0 and
    left corridor at +W, so NO lateral mirror is applied here.
    """
    idx0 = ego["idx"]
    hz = int(round(horizon_s / dt))
    step = int(round(dt / 0.1))  # Waymo 10 Hz -> 0.5 s
    u = np.array([math.cos(ego["heading"]), math.sin(ego["heading"])])
    n = np.array([-math.sin(ego["heading"]), math.cos(ego["heading"])])
    actors = [canonical["ego"]] + canonical["actors"]
    slots = []
    for k in range(hz + 1):
        fi = idx0 + k * step
        frame = []
        if fi < len(actors[0]["frames"]):
            for a in actors:
                s = a["frames"][fi]
                if not s["valid"]:
                    continue
                dxy = np.array([s["x"] - ego["x"], s["y"] - ego["y"]])
                lon = float(dxy @ u)
                lat = float(dxy @ n)
                if abs(lat) > lat_filter + 4.0:
                    continue
                frame.append((lon, lat, max(s["length"] / 2.0, 1.0),
                              max(s["width"] / 2.0, 0.3)))
        slots.append(frame)
    return slots


def interaction_actor_ids(canonical, ego, lane_w, horizon_s=8.0, dt=0.5,
                          margin=0.5, ego_half_w=1.0):
    """Actors whose swept bbox intersects the current/left corridor band."""
    idx0 = ego["idx"]
    hz = int(round(horizon_s / dt))
    step = int(round(dt / 0.1))
    u = np.array([math.cos(ego["heading"]), math.sin(ego["heading"])])
    n = np.array([-math.sin(ego["heading"]), math.cos(ego["heading"])])
    ids = {}
    for a in canonical["actors"]:
        for k in range(hz + 1):
            fi = idx0 + k * step
            if fi >= len(a["frames"]):
                break
            s = a["frames"][fi]
            if not s["valid"]:
                continue
            dxy = np.array([s["x"] - ego["x"], s["y"] - ego["y"]])
            lat = float(dxy @ n)
            hw = max(s["width"] / 2.0, 0.3)
            cur = abs(lat - 0.0) < hw + ego_half_w + margin
            left = abs(lat - lane_w) < hw + ego_half_w + margin
            if cur or left:
                rec = ids.setdefault(a["id"], {"t": [], "corridor": set(), "min_margin": 1e9})
                rec["t"].append(round(k * dt, 2))
                rec["corridor"].add("current" if cur else "left")
                rec["min_margin"] = min(rec["min_margin"],
                                        min(abs(lat), abs(lat - lane_w)) - hw - ego_half_w)
                break
    return ids
