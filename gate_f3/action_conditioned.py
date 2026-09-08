#!/usr/bin/env python3
"""Gate F3-A3 Action-Conditioned Equivalence Test on Dev-108.

For each state, expand the lateral action by candidate start time t_s in
{0,1,...,6}s:
    Q_L(t_s) = max feasible progress at H=10 of a lane change whose lateral
               motion starts at t_s (no change before t_s);
    Q_K      = max KEEP progress at H=10 (never change).
R(X) = [Q_K, Q_L(0),...,Q_L(6)] is the action-consequence structure.
This is a diagnostic; it uses a local restricted search, not a model, and does
not change the frozen engine/labels used elsewhere.
"""
import glob
import json
import math
import os

import numpy as np

sys_path_ok = True
try:
    import sys
    sys.path.insert(0, "gate_f0")
    sys.path.insert(0, "gate_f0/feasible")
    sys.path.insert(0, "gate_f1/common")
    from feasible.engine import StraightCorridor, OccupancyGT  # noqa: E402
    import geo  # noqa: E402
except Exception as e:  # noqa
    sys_path_ok = False
    raise

DT = 0.5
N = 20
H10 = int(10.0 / DT) - 1  # index 19 -> horizon 10 s
ACC = (-4.0, -2.0, 0.0, 1.5)
VMAX = 12.0
T_LC = 3.0
MARGIN = 0.5
EPS = 0.1


def load_state(path):
    rows = [json.loads(l) for l in open(path)]
    rows.sort(key=lambda r: r["sim_t"])
    seg = json.load(open("gate_f0/road_segment.json"))
    geo.load_seg("gate_f0/road_segment.json")
    lane_w = geo.lane_width()
    meta = rows[0].get("scenario") or {}
    v0 = float(meta.get("v0") or rows[0].get("v0") or
               max(rows[0]["ego"]["speed_mps"], 0.5))
    s0 = float(rows[0].get("ego_s", 0.0))
    ox, oy = seg["origin"]
    th = seg["heading_rad"]
    u = (math.cos(th), math.sin(th))
    n = (-math.sin(th), math.cos(th))

    def local(x, y):
        dx, dy = x - ox, y - oy
        return dx * u[0] + dy * u[1], dx * n[0] + dy * n[1]

    def pick(t):
        best = min(rows, key=lambda r: abs(r["sim_t"] - t))
        return best if abs(best["sim_t"] - t) < 0.3 else None

    slots = []
    for t in np.arange(0, 10.0 + 1e-6, DT):
        r = pick(float(t))
        acts = []
        if r is not None:
            for a in r["actors"]:
                sx, ly = local(a["transform"]["x"], a["transform"]["y"])
                if abs(ly) > lane_w + 4.0:
                    continue
                e = a["bbox"]["extent"]
                acts.append((sx - s0, -ly, max(float(e[0]), 1.0),
                             max(float(e[1]), 0.3)))
        slots.append(acts)
    return slots, v0, s0, lane_w


def run_restricted(slots, v0, lane_w, lc_start_s):
    """Search: no lateral transition before lc_start_s; Q_K / Q_L(10s)."""
    KEEP, CHANGING, LEFT = 0, 1, 2
    occ = OccupancyGT(N, DT)
    for i, acts in enumerate(slots):
        if not acts:
            occ.add_actor(np.full(N + 1, -1.0), np.full(N + 1, 30.0), 1.0, 1.0)
            continue
        for (sx, ly, hl, hw) in acts:
            sa = np.full(N + 1, -1.0)
            la = np.full(N + 1, 30.0)
            sa[i] = sx
            la[i] = ly
            occ.add_actor(sa, la, hl, hw)
    cor = StraightCorridor(200.0, lane_w)
    buckets = (0, 2, 5, 8, 12, 1e9)

    def quintic(r):
        r = min(max(r, 0.0), 1.0)
        return 10 * r ** 3 - 15 * r ** 4 + 6 * r ** 5

    def prune(group):
        kept = []
        for i in range(len(buckets) - 1):
            cand = [s for s in group if buckets[i] <= s[1] < buckets[i + 1]]
            cand.sort(key=lambda s: -s[0])
            kept.extend(cand[:20])
        return kept

    def trim(states):
        out = prune([s for s in states if s[2] == KEEP]) + \
              prune([s for s in states if s[2] == LEFT]) + \
              prune([s for s in states if s[2] == CHANGING])
        if len(out) < 100:
            extra = sorted(states, key=lambda s: -s[0])[: 100 - len(out)]
            out += extra
        return out

    def d_of(m, tau):
        if m == KEEP:
            return 0.0
        if m == LEFT:
            return cor.w
        return cor.w * quintic(tau / T_LC)

    def step_long(s, v, a):
        v1 = min(max(v + a * DT, 0.0), VMAX)
        s1 = s + v * DT + 0.5 * a * DT * DT
        return s1, v1

    def feasible(svmt, i):
        s, v, m, tau = svmt
        if s > cor.length:
            return False
        return not occ.collides(s, d_of(m, tau), i, MARGIN, (2.2, 1.0))

    states = [(0.0, v0, KEEP, 0.0)]
    lc_first = int(round(lc_start_s / DT))
    best0 = bestL = -1.0
    for i in range(1, N + 1):
        exp = []
        for (s, v, m, tau) in states:
            if m == KEEP:
                for a in ACC:
                    s1, v1 = step_long(s, v, a)
                    st = (s1, v1, KEEP, 0.0)
                    if feasible(st, i):
                        exp.append(st)
                if cor.left_exists and (i - 1) >= lc_first:
                    for a in ACC:
                        s1, v1 = step_long(s, v, a)
                        nt = tau + DT
                        st = (s1, v1, LEFT if nt >= T_LC else CHANGING,
                              0.0 if nt >= T_LC else nt)
                        if feasible(st, i):
                            exp.append(st)
            elif m == CHANGING:
                for a in ACC:
                    s1, v1 = step_long(s, v, a)
                    nt = tau + DT
                    st = (s1, v1, LEFT if nt >= T_LC else CHANGING,
                          0.0 if nt >= T_LC else nt)
                    if feasible(st, i):
                        exp.append(st)
            else:
                for a in ACC:
                    s1, v1 = step_long(s, v, a)
                    st = (s1, v1, LEFT, 0.0)
                    if feasible(st, i):
                        exp.append(st)
        states = trim(exp) if exp else []
        m0 = max((s for s, v, m, t in states if m == KEEP), default=-1.0)
        mL = max((s for s, v, m, t in states if m == LEFT), default=-1.0)
        best0 = max(best0, m0)
        bestL = max(bestL, mL)
        if i == N:
            return best0, bestL
    return best0, bestL


def main():
    groups = ["block_nec", "lead_nec", "cross_stall", "lead_opt"]
    out = {g: [] for g in groups}
    for f in sorted(glob.glob("gate_f3/data/raw/*/*/row*.summary.json")):
        j = json.load(open(f))
        cell = j["cell"]
        if cell not in groups:
            continue
        raw = f.replace(".summary.json", ".ndjson")
        slots, v0, s0, lane_w = load_state(raw)
        QK, _ = run_restricted(slots, v0, lane_w, 0.0)
        QL = []
        for ts in range(0, 7):
            _, ql = run_restricted(slots, v0, lane_w, float(ts))
            QL.append(round(ql, 2) if ql >= 0 else None)
        out[cell].append({"v0": v0, "s0": round(s0, 1), "Q_K": round(QK, 2),
                          "Q_L": QL})
    # aggregate
    print(f"{'group':12s} | Q_K | Q_L(0) Q_L(1) Q_L(2) Q_L(3) Q_L(4) Q_L(5) Q_L(6)")
    agg = {}
    for g, vals in out.items():
        qk = np.mean([v["Q_K"] for v in vals])
        ql = [np.mean([v["Q_L"][k] for v in vals if v["Q_L"][k] is not None])
              for k in range(7)]
        agg[g] = {"Q_K": round(float(qk), 1), "Q_L": [round(x, 1) for x in ql]}
        print(f"{g:12s} | {qk:5.1f} | " + " ".join(f"{x:6.1f}" for x in ql))
    json.dump(agg, open("gate_f3/results/F3A3_action_curves.json", "w"), indent=1)
    print("saved F3A3_action_curves.json")


if __name__ == "__main__":
    main()
