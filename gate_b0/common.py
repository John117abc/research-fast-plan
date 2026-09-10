"""Gate B0 shared utilities: config, frozen geometry, Dev-108 indexing, occupancy.

Offline only. Does not import carla. Local frame: s along segment from origin,
lat to the left (same convention as gate_f1/offline/compute.py). Recorded actors
are physically in the current lane at lat<0 on this segment; the engine models
the alternative at +W, so occupancy mirrors lat as -ly (see build_occ).
"""
import glob
import json
import math
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = None
SEG = None
_UNIT = None

COARSE_FROM_MECH = None


def cfg():
    global CFG, COARSE_FROM_MECH
    if CFG is None:
        import yaml
        CFG = yaml.safe_load(open(os.path.join(ROOT, "gate_b0/config/gate_b0.yaml")))
        COARSE_FROM_MECH = CFG["coarse_map"]
    return CFG


def seg():
    global SEG, _UNIT
    if SEG is None:
        SEG = json.load(open(os.path.join(ROOT, cfg()["data"]["road_segment"])))
        ox, oy = SEG["origin"]
        th = SEG["heading_rad"]
        _UNIT = (ox, oy, (math.cos(th), math.sin(th)), (-math.sin(th), math.cos(th)))
    return SEG


def local(x, y):
    seg()
    ox, oy, u, n = _UNIT
    dx, dy = x - ox, y - oy
    return dx * u[0] + dy * u[1], dx * n[0] + dy * n[1]


def lane_width():
    s = seg()
    if len(s["c0"]) < 60:
        return 3.5
    tot = 0.0
    for i in range(0, 60, 2):
        a, b = s["c0"][i], s["cl"][i]
        tot += math.hypot(a[0] - b[0], a[1] - b[1])
    return tot / 30.0


def coarse_of(mech):
    return cfg()["coarse_map"][mech]


def _family_key(spec):
    bw = cfg()["param_group"]["bin_width"]
    cell = spec.get("cell", "")
    if "L" in spec:
        return "L%d" % (int(spec["L"]) // bw)
    if "d_conflict" in spec:
        return "d%d" % (int(spec["d_conflict"]) // bw)
    if "occ_s" in spec:
        return "o%d" % (int(spec["occ_s"]) // bw)
    if cell.startswith("lead") and "s0" in spec:
        return "s%d" % (int(spec["s0"]) // bw)
    return "na"


def param_group(spec):
    return "%s|v%s|%s" % (spec.get("cell"), spec.get("ego_v"), _family_key(spec))


def list_states():
    """Return metadata records for every Dev-108 raw file."""
    out = []
    for path in sorted(glob.glob(os.path.join(ROOT, cfg()["data"]["raw_root"], "*/*/row*.ndjson"))):
        parts = path.replace("\\", "/").split("/")
        mech, cell = parts[-3], parts[-2]
        row = int(parts[-1].replace("row", "").replace(".ndjson", ""))
        with open(path) as fh:
            first = json.loads(fh.readline())
        spec = first.get("scenario", {}).get("spec", {})
        actors = [a["actor_id"] for a in first.get("actors", [])]
        out.append({
            "state_id": "%s_r%d" % (cell, row),
            "run_id": "%s/%s/row%d" % (mech, cell, row),
            "case_id": "%s_r%d" % (cell, row),
            "path": path,
            "mech": mech,
            "cell": cell,
            "row": row,
            "fine_mechanism": cell,
            "coarse_mechanism": coarse_of(mech),
            "param_group_id": param_group(spec),
            "spec": spec,
            "ego_speed": float(first.get("scenario", {}).get("v_target", 0.0)),
            "ego_s": float(first.get("ego_s", 0.0)),
            "ego_lane_id": first.get("ego", {}).get("lane_id"),
            "target_actor_ids": actors,
            "decision_frame": first.get("frame"),
        })
    return out


def load_rows(path):
    rows = [json.loads(l) for l in open(path)]
    rows.sort(key=lambda r: r["sim_t"])
    return rows


def _pick(rows, t, tol=0.3):
    best = min(rows, key=lambda r: abs(r["sim_t"] - t))
    return best if abs(best["sim_t"] - t) < tol else None


def build_slots(path, rows=None, record_s=None):
    """Occupancy frames at 0.5 s from t0 to t0+record_s (absolute local s)."""
    if rows is None:
        rows = load_rows(path)
    if record_s is None:
        record_s = cfg()["data"]["record_s"]
    dt = cfg()["data"]["dt"]
    lw = lane_width()
    marg = cfg()["data"]["lane_filter_margin"]
    slots = []
    for t in np.arange(0.0, record_s + 1e-6, dt):
        r = _pick(rows, float(t))
        acts = []
        if r is not None:
            for a in r["actors"]:
                tf = a["transform"]
                sx, ly = local(tf["x"], tf["y"])
                if abs(ly) > lw + marg:
                    continue
                e = a["bbox"]["extent"]
                acts.append((sx, ly, max(float(e[0]), 1.0), max(float(e[1]), 0.3)))
        slots.append(acts)
    return slots
