"""Gate B0 constrained rollout.

Generalizes gate_f0/feasible/engine.compute_frontiers without modifying it:
  - arbitrary init state (s, v, mode, tau)
  - a forced prefix of `FORCED_STEPS` steps with a fixed (ax, lateral intent)
  - then the standard free beam search

Frames: all ego s and actor s are ABSOLUTE local s (from segment origin).
Occupancy is rebuilt relative to the ego init position so the search runs with
ego at s=0. Lateral intent semantics:
  keep : mode KEEP -> KEEP ; mode LEFT -> LEFT ; mode CHANGING -> invalid (no abort)
  left : mode KEEP -> CHANGING ; mode CHANGING -> continue ; mode LEFT -> invalid
"""
import numpy as np

from feasible.engine import (KEEP, CHANGING, LEFT, StraightCorridor,  # noqa: E402
                             OccupancyGT, quintic, step_long)

import common  # noqa: E402
from action_probe.action_set import FORCED_STEPS  # noqa: E402

CFG = common.cfg()
DT = CFG["data"]["dt"]
N = int(round(CFG["data"]["horizon_s"] / DT))
ACCEL = tuple(CFG["engine"]["accel"])
VMAX = CFG["engine"]["v_max"]
T_LC = CFG["engine"]["T_LC"]
MARGIN = CFG["engine"]["margin"]
EGO_HALF = tuple(CFG["engine"]["ego_half"])
COR_LEN = CFG["engine"]["corridor_length"]
WIDTH = CFG["engine"]["width"]
KEEP_PER_BUCKET = CFG["engine"]["keep_per_bucket"]
BUCKETS = (0, 2, 5, 8, 12, 1e9)


def empty_occ(n_steps=N, dt=DT):
    return OccupancyGT(n_steps, dt)


def build_occ(slots_abs, ego_abs_s, n_steps=N, dt=DT):
    """slots_abs: list of frames (0.5 s) of (s_abs, lat, hl, hw). lat mirrored."""
    occ = OccupancyGT(n_steps, dt)
    for i, acts in enumerate(slots_abs):
        if not acts:
            occ.add_actor(np.full(n_steps + 1, -1.0), np.full(n_steps + 1, 30.0), 1.0, 1.0)
            continue
        for (s_abs, lat, hl, hw) in acts:
            s_arr = np.full(n_steps + 1, -1.0)
            lat_arr = np.full(n_steps + 1, 30.0)
            s_arr[i] = s_abs - ego_abs_s
            lat_arr[i] = -lat
            occ.add_actor(s_arr, lat_arr, hl, hw)
    return occ


def _d_of(m, tau, w):
    if m == KEEP:
        return 0.0
    if m == LEFT:
        return w
    return w * quintic(tau / T_LC)


def _feasible(state, occ, i, cor):
    s, v, m, tau = state
    if s > cor.length:
        return False
    return not occ.collides(s, _d_of(m, tau, cor.w), i, MARGIN, EGO_HALF)


def _apply_fixed(state, ax, lateral, i, occ, cor):
    s, v, m, tau = state
    if lateral == "keep":
        if m == CHANGING:
            return None
        nm, ntau = m, (0.0 if m == KEEP else tau)
    else:
        if m == LEFT:
            return None
        nt = tau + DT
        nm = LEFT if nt >= T_LC else CHANGING
        ntau = 0.0 if nt >= T_LC else nt
    s1, v1 = step_long(s, v, ax, DT, VMAX)
    st = (s1, v1, nm, ntau)
    return st if _feasible(st, occ, i, cor) else None


def _expand_all(state, i, occ, cor):
    s, v, m, tau = state
    out = []

    def try_add(ax, nm, ntau):
        s1, v1 = step_long(s, v, ax, DT, VMAX)
        st = (s1, v1, nm, ntau)
        if _feasible(st, occ, i, cor):
            out.append(st)

    if m == KEEP:
        for a in ACCEL:
            try_add(a, KEEP, 0.0)
        if cor.left_exists:
            for a in ACCEL:
                nt = tau + DT
                try_add(a, LEFT if nt >= T_LC else CHANGING, 0.0 if nt >= T_LC else nt)
    elif m == CHANGING:
        for a in ACCEL:
            nt = tau + DT
            try_add(a, LEFT if nt >= T_LC else CHANGING, 0.0 if nt >= T_LC else nt)
    else:
        for a in ACCEL:
            try_add(a, LEFT, 0.0)
    return out


def _prune(group):
    kept = []
    for i in range(len(BUCKETS) - 1):
        cand = [s for s in group if BUCKETS[i] <= s[1] < BUCKETS[i + 1]]
        cand.sort(key=lambda s: -s[0])
        kept.extend(cand[:KEEP_PER_BUCKET])
    return kept


def _trim(states):
    out = (_prune([s for s in states if s[2] == KEEP]) +
           _prune([s for s in states if s[2] == LEFT]) +
           _prune([s for s in states if s[2] == CHANGING]))
    if len(out) < WIDTH:
        extra = sorted(states, key=lambda s: -s[0])[: WIDTH - len(out)]
        out += extra
    return out


def run_probe(init_state, ax, lateral, occ, cor, n_steps=N, forced_steps=None):
    """Return dict(valid, successor, best, n_final). init_state=(s,v,m,tau)."""
    fs = FORCED_STEPS if forced_steps is None else forced_steps
    st = init_state
    for k in range(1, fs + 1):
        st = _apply_fixed(st, ax, lateral, k, occ, cor)
        if st is None:
            return {"valid": False, "successor": None, "best": -1.0, "n_final": 0}
    successor = st
    states = [st]
    for i in range(fs + 1, n_steps + 1):
        exp = []
        for s in states:
            exp.extend(_expand_all(s, i, occ, cor))
        states = _trim(exp) if exp else []
        if not states:
            break
    best = max((s[0] for s in states), default=-1.0)
    return {"valid": True, "successor": successor, "best": best, "n_final": len(states)}


def run_probe_curves(init_state, ax, lateral, occ, cor, n_steps=N, forced_steps=None):
    """Per-step best-ever frontiers for the two branches after forcing u.

    Returns dict(valid, p0, pL) where p0/pL are length-n_steps lists (t=0.5..10s)
    of best-ever max s over KEEP / completed-LEFT states, -1 if never feasible.
    """
    fs = FORCED_STEPS if forced_steps is None else forced_steps
    chain = [init_state]
    st = init_state
    for k in range(1, fs + 1):
        st = _apply_fixed(st, ax, lateral, k, occ, cor)
        if st is None:
            return {"valid": False, "p0": [-1.0] * n_steps, "pL": [-1.0] * n_steps}
        chain.append(st)
    p0 = [None] * (n_steps + 1)
    pL = [None] * (n_steps + 1)
    best0 = bestL = -1.0
    for k in range(1, fs + 1):
        s, v, m, tau = chain[k]
        if m == KEEP:
            best0 = max(best0, s)
        if m == LEFT:
            bestL = max(bestL, s)
        p0[k], pL[k] = best0, bestL
    states = [st]
    for i in range(fs + 1, n_steps + 1):
        exp = []
        for s in states:
            exp.extend(_expand_all(s, i, occ, cor))
        states = _trim(exp) if exp else []
        if states:
            m0 = max((s[0] for s in states if s[2] == KEEP), default=-1.0)
            mL = max((s[0] for s in states if s[2] == LEFT), default=-1.0)
            best0, bestL = max(best0, m0), max(bestL, mL)
        p0[i], pL[i] = best0, bestL
    return {"valid": True, "p0": p0[1:], "pL": pL[1:]}
