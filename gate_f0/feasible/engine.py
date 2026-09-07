"""Gate F0 offline feasible-engine for straight parallel two-lane corridor.

Corridors C0 (current) and CL (left) are parallel straight lines separated by
lane width `w`. Ego states: (s, v, m, tau):
   m = 0 KEEP, 1 CHANGING_LEFT, 2 LEFT ;  tau = seconds spent in CHANGING.
Lateral offset d from C0: KEEP=0, LEFT=w, CHANGING = w * quintic(tau/T_LC).
Longitudinal dynamics along s with accel primitives (same on both lanes).

Collision is axis-aligned (in corridor-local coordinates) rectangle overlap with
half-extents: ego (L/2 long, W/2 lat); actors stored in (s, lat) frames.
P0(H) = max s over m==0 branches at horizon (default-corridor maintainability).
PL(H) = max s over m==2 branches that COMPLETED the change before H.
"""
import math

import numpy as np

KEEP, CHANGING, LEFT = 0, 1, 2
ACCEL_DEFAULT = (-4.0, -2.0, 0.0, 1.5)


def quintic(r):
    r = min(max(r, 0.0), 1.0)
    return 10 * r ** 3 - 15 * r ** 4 + 6 * r ** 5


def step_long(s, v, a, dt, v_max):
    v1 = min(max(v + a * dt, 0.0), v_max)
    s1 = s + v * dt + 0.5 * a * dt * dt
    return s1, v1


class StraightCorridor:
    """Straight two-lane corridor; local frame: x=s along lane, lat to the left."""

    def __init__(self, length, lane_w, left_exists=True):
        self.length = length
        self.w = lane_w
        self.left_exists = left_exists


class OccupancyGT:
    """Future occupancy of actors in corridor-local (s, lat) with rect half-extents."""

    def __init__(self, n_steps, dt):
        self.dt = dt
        self.n_steps = n_steps
        self.actors = []

    def add_actor(self, s_series, lat_series, half_len, half_wid):
        self.actors.append({"s": np.asarray(s_series, float),
                            "lat": np.asarray(lat_series, float),
                            "hl": half_len, "hw": half_wid})

    def collides(self, ego_s, ego_lat, i, margin, ego_half=(2.2, 1.0)):
        e_lo_s, e_hi_s = ego_s - ego_half[0], ego_s + ego_half[0]
        e_lo_l, e_hi_l = ego_lat - ego_half[1], ego_lat + ego_half[1]
        m = margin
        for a in self.actors:
            if i >= len(a["s"]):
                continue
            s = float(a["s"][i])
            lat = float(a["lat"][i])
            lo_s, hi_s = s - a["hl"], s + a["hl"]
            lo_l, hi_l = lat - a["hw"], lat + a["hw"]
            if (e_lo_s < hi_s + m and e_hi_s > lo_s - m and
                    e_lo_l < hi_l + m and e_hi_l > lo_l - m):
                return True
        return False


def static_series(xy_s, xy_lat, n_steps):
    return np.full(n_steps + 1, float(xy_s)), np.full(n_steps + 1, float(xy_lat))


def compute_frontiers(cor, occ, s0, v0, accel_set, dt, v_max, n_steps,
                      horizons_steps, width=100, keep_per_bucket=20,
                      margin=0.5, ego_half=(2.2, 1.0), T_LC=3.0,
                      return_stats=False):
    buckets = (0, 2, 5, 8, 12, 1e9)

    def prune(group):
        kept = []
        for i in range(len(buckets) - 1):
            cand = [s for s in group if buckets[i] <= s[1] < buckets[i + 1]]
            cand.sort(key=lambda s: -s[0])
            kept.extend(cand[:keep_per_bucket])
        return kept

    def trim(states):
        keep_grp = prune([s for s in states if s[2] == KEEP])
        left_grp = prune([s for s in states if s[2] == LEFT])
        ch_grp = prune([s for s in states if s[2] == CHANGING])
        out = keep_grp + left_grp + ch_grp
        if len(out) < width:
            extra = sorted(states, key=lambda s: -s[0])[: width - len(out)]
            out += extra
        return out

    def d_of(m, tau):
        if m == KEEP:
            return 0.0
        if m == LEFT:
            return cor.w
        return cor.w * quintic(tau / T_LC)

    def feasible(svmt, i_step):
        s, v, m, tau = svmt
        if s > cor.length:
            return False
        return not occ.collides(s, d_of(m, tau), i_step, margin, ego_half)

    states = [(s0, v0, KEEP, 0.0)]
    P0, PL = [], []
    best0 = -1.0
    bestL = -1.0
    n0, nL = [], []
    for i in range(1, n_steps + 1):
        expanded = []
        for (s, v, m, tau) in states:
            if m == KEEP:
                for a in accel_set:
                    s1, v1 = step_long(s, v, a, dt, v_max)
                    st = (s1, v1, KEEP, 0.0)
                    if feasible(st, i):
                        expanded.append(st)
                if cor.left_exists:
                    for a in accel_set:
                        s1, v1 = step_long(s, v, a, dt, v_max)
                        nt = tau + dt
                        done = nt >= T_LC
                        st = (s1, v1, LEFT if done else CHANGING,
                              0.0 if done else nt)
                        if feasible(st, i):
                            expanded.append(st)
            elif m == CHANGING:
                for a in accel_set:
                    s1, v1 = step_long(s, v, a, dt, v_max)
                    nt = tau + dt
                    st = (s1, v1, LEFT if nt >= T_LC else CHANGING,
                          0.0 if nt >= T_LC else nt)
                    if feasible(st, i):
                        expanded.append(st)
            else:  # LEFT
                for a in accel_set:
                    s1, v1 = step_long(s, v, a, dt, v_max)
                    st = (s1, v1, LEFT, 0.0)
                    if feasible(st, i):
                        expanded.append(st)
        states = trim(expanded) if expanded else []
        m0 = max((s for s, v, m, t in states if m == KEEP), default=-1.0)
        mL = max((s for s, v, m, t in states if m == LEFT), default=-1.0)
        best0 = max(best0, m0)
        bestL = max(bestL, mL)
        if i in horizons_steps:
            P0.append(best0)
            PL.append(bestL)
            if return_stats:
                n0.append(sum(1 for s, v, m, t in states if m == KEEP))
                nL.append(sum(1 for s, v, m, t in states if m == LEFT))
    if return_stats:
        return P0, PL, {"n0": n0, "nL": nL}
    return P0, PL
