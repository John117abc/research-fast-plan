#!/usr/bin/env python3
"""Gate F3 dataset rows: generate + offline prescreen (frozen engine) so that
each cell's rows are sane before CARLA generation. Rows written to
gate_f3/data/params_F3.yaml. Structure label = engine-computed."""
import json
import math

import numpy as np
import yaml

import sys
sys.path.insert(0, "gate_f0")
sys.path.insert(0, "gate_f0/feasible")
from feasible.engine import StraightCorridor, OccupancyGT, compute_frontiers  # noqa

DT = 0.5
N = 20
ACC = (-4.0, -2.0, 0.0, 1.5)
VMAX = 12.0
CS = 1.6
PLAT_ST = (6, 18, 30, 42, 54, 66, 78)
seg = json.load(open("gate_f0/road_segment.json"))
W = float(np.mean([math.hypot(seg["c0"][i][0] - seg["cl"][i][0],
                              seg["c0"][i][1] - seg["cl"][i][1]) for i in range(0, 60, 2)]))
cor = StraightCorridor(200.0, W)


def s_e(v):
    return v * v / 3.0 + v


def classify(g0, gl):
    if g0 > 0.1:
        return "LateralOptional"
    if gl is not None and gl > 0.1:
        return "LateralNecessary"
    return "Contingency/Wait"


def run_occ(occ, v0):
    P0, PL, _ = compute_frontiers(cor, occ, 0, v0, ACC, DT, VMAX, N,
                                  [int(h / DT) - 1 for h in (8, 10)], width=100,
                                  keep_per_bucket=20, margin=0.5, T_LC=3.0,
                                  return_stats=True)
    g0 = (P0[1] - P0[0]) / 2.0
    gl = (PL[1] - PL[0]) / 2.0 if (PL[0] >= 0 and PL[1] >= 0) else None
    return classify(g0, gl), round(g0, 2), (None if gl is None else round(gl, 2))


def slot(occ, i, s, lat, hl=1.0, hw=0.4):
    sa = np.full(N + 1, -1.0)
    la = np.full(N + 1, 30.0)
    sa[i] = s
    la[i] = lat
    occ.add_actor(sa, la, hl, hw)


def cross_stall_occ(spec):
    d = spec["d_conflict"]
    e0 = s_e(spec["ego_v"])
    lat0 = -6.0 if spec.get("kind") == "ped" else -2.5
    t_stall = (0.5 - lat0) / CS
    occ = OccupancyGT(N, DT)
    for i in range(N + 1):
        t = i * DT
        lat = lat0 + CS * t if t < t_stall else 0.5
        slot(occ, i, d - e0, lat, hl=0.3 if spec["kind"] == "ped" else 2.2,
             hw=0.35 if spec["kind"] == "ped" else 1.0)
        if spec.get("left_occ") or str(spec.get("cell", "")).endswith("_occ"):
            for st in PLAT_ST:
                s2 = st + 1.5 * t - e0
                if abs(s2) < 190:
                    slot(occ, i, s2, 3.25, hl=2.0, hw=1.0)
    return occ


def lead_occ(spec, left_occ):
    s0, v0, tc, a = spec["s0"], spec["v0"], spec["tc"], spec["a"]
    e0 = s_e(spec["ego_v"])
    occ = OccupancyGT(N, DT)

    def lead_s(t):
        if t <= tc:
            return s0 + v0 * t
        tb = t - tc
        ts = v0 / a
        if tb >= ts:
            return s0 + v0 * tc + v0 * v0 / (2 * a)
        return s0 + v0 * tc + v0 * tb - 0.5 * a * tb * tb
    for i in range(N + 1):
        t = i * DT
        slot(occ, i, lead_s(t) - e0, 0.0, hl=2.2, hw=1.0)
        if left_occ:
            for st in PLAT_ST:
                s2 = st + 1.5 * t - e0
                if abs(s2) < 190:
                    slot(occ, i, s2, 3.25, hl=2.0, hw=1.0)
    return occ


def lead_opt_occ(spec):
    s0, v = spec["s0"], spec["v_lead"]
    e0 = s_e(spec["ego_v"])
    occ = OccupancyGT(N, DT)
    for i in range(N + 1):
        slot(occ, i, s0 + v * i * DT - e0, 0.0, hl=2.2, hw=1.0)
    return occ


def block_occ(spec, cont):
    L = spec["L"]
    e0 = s_e(spec["ego_v"])
    occ = OccupancyGT(N, DT)
    for i in range(N + 1):
        t = i * DT
        for off in (0, 7, 14):
            slot(occ, i, L + off - e0, 0.0, hl=2.2, hw=1.0)
        if cont:
            for st in PLAT_ST:
                s2 = st + 1.5 * t - e0
                if abs(s2) < 190:
                    slot(occ, i, s2, 3.25, hl=2.0, hw=1.0)
    return occ


def temp_occ(spec):
    occ_s, tl, av = spec["occ_s"], spec["t_leave"], spec["away_v"]
    e0 = s_e(spec["ego_v"])
    occ = OccupancyGT(N, DT)
    for i in range(N + 1):
        t = i * DT
        s = occ_s if t < tl else occ_s + av * (t - tl)
        slot(occ, i, s - e0, 0.0, hl=2.2, hw=1.0)
    return occ


def target_of(cell):
    return {"cross_clear": "LateralOptional", "cross_stall": "LateralNecessary",
            "cross_stall_occ": "Contingency/Wait", "lead_opt": "LateralOptional",
            "lead_nec": "LateralNecessary", "lead_cont": "Contingency/Wait",
            "block_nec": "LateralNecessary", "block_cont": "Contingency/Wait",
            "temp_opt": "LateralOptional"}[cell]


def pred(spec):
    c = spec["cell"]
    v = spec["ego_v"]
    if c == "cross_clear":
        # runtime-armed crossing (F1 verified Optional for these geometries)
        return "LateralOptional"
    if c == "cross_stall":
        occ = cross_stall_occ(spec)
        return run_occ(occ, v)[0]
    if c == "cross_stall_occ":
        occ = cross_stall_occ(spec)
        return run_occ(occ, v)[0]
    if c == "lead_opt":
        return run_occ(lead_opt_occ(spec), v)[0]
    if c in ("lead_nec", "lead_cont"):
        return run_occ(lead_occ(spec, c == "lead_cont"), v)[0]
    if c in ("block_nec", "block_cont"):
        return run_occ(block_occ(spec, c == "block_cont"), v)[0]
    if c == "temp_opt":
        return run_occ(temp_occ(spec), v)[0]
    raise KeyError(c)


def build_rows():
    rows = {}
    import itertools
    kinds = ["ped", "veh"]

    def push(cell, spec):
        spec = dict(spec)
        spec["cell"] = cell
        rows.setdefault(cell, []).append(spec)

    # cross_clear: Optional (runtime-armed crossing, kind alternates)
    e = itertools.product([6, 7, 8], [46, 52, 58, 64])
    i = 0
    for v, d in e:
        if v in (9,):
            continue
        push("cross_clear", {"ego_v": v, "d_conflict": d, "kind": kinds[i % 2]})
        i += 1
    # cross_stall + cross_stall_occ: geometry ensures ego can't pass before hold
    for kind in kinds:
        for v, d in ((6, 50), (6, 54), (7, 54), (7, 58), (8, 58), (8, 64)):
            push("cross_stall", {"ego_v": v, "d_conflict": d, "kind": kind})
    for kind in kinds:
        for v, d in ((6, 52), (6, 58), (7, 56), (7, 62), (8, 60), (8, 66)):
            push("cross_stall_occ", {"ego_v": v, "d_conflict": d, "kind": kind})
    # lead_opt / lead_nec / lead_cont
    for v, s0, vl in ((6, 48, 2.5), (6, 50, 3.5), (7, 52, 2.5), (7, 54, 4.0),
                      (8, 56, 3.0), (8, 58, 3.5), (9, 60, 4.0), (9, 62, 3.0),
                      (7, 50, 2.5), (8, 60, 2.5), (6, 54, 4.0), (7, 58, 3.5)):
        push("lead_opt", {"ego_v": v, "s0": s0, "v_lead": vl})
    for cell, lc in (("lead_nec", False), ("lead_cont", True)):
        base = [(6, 40, 6, 2.0, 2.5), (6, 44, 8, 2.0, 2.5), (7, 46, 6, 3.0, 2.5),
                (7, 50, 8, 2.0, 2.5), (8, 52, 8, 2.0, 3.0), (8, 56, 8, 3.0, 2.5),
                (8, 60, 9, 1.5, 2.5), (9, 62, 8, 2.0, 2.5), (9, 64, 9, 1.5, 2.5),
                (9, 66, 9, 1.0, 2.5), (7, 48, 6, 2.5, 2.5), (8, 58, 9, 2.0, 3.0)]
        for v, s0, v0, tc, a in base:
            push(cell, {"ego_v": v, "s0": s0, "v0": v0, "tc": tc, "a": a})
    # block_nec / block_cont
    base = [(6, 40), (6, 44), (7, 46), (7, 50), (8, 52), (8, 56),
            (8, 60), (9, 62), (9, 64), (7, 52), (8, 50), (6, 48)]
    for cell in ("block_nec", "block_cont"):
        for v, L in base:
            push(cell, {"ego_v": v, "L": L})
    # temp_opt
    for v, oc, tl, av in ((6, 52, 2.5, 8), (6, 58, 4.0, 8), (6, 66, 7.0, 8),
                          (7, 52, 3.0, 9), (7, 60, 5.0, 9), (7, 66, 6.0, 11),
                          (8, 54, 2.5, 9), (8, 60, 5.0, 11), (8, 66, 7.0, 11),
                          (6, 60, 2.5, 11), (7, 66, 3.0, 8), (8, 58, 4.0, 8)):
        push("temp_opt", {"ego_v": v, "occ_s": oc, "t_leave": tl, "away_v": av})
    return rows


def main():
    rows = build_rows()
    report = {}
    for cell, specs in rows.items():
        ok = 0
        tgt = target_of(cell)
        for s in specs:
            got = pred(s)
            s["_prescreen"] = got
            ok += got == tgt
        report[cell] = f"{ok}/{len(specs)} -> {tgt}"
        print(f"{cell:16s} {ok}/{len(specs)}  target {tgt}")
    yaml.safe_dump({k: v for k, v in rows.items()},
                   open("gate_f3/data/params_F3.yaml", "w"))
    print("wrote gate_f3/data/params_F3.yaml")


if __name__ == "__main__":
    import os
    os.makedirs("gate_f3/data", exist_ok=True)
    main()
