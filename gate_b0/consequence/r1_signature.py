"""Gate B0-R1 representation R1(X) = {V0^u(t), VL^u(t)} (320 values)."""
from feasible.engine import StraightCorridor  # noqa: E402

import common  # noqa: E402
from action_probe import constrained_rollout as cr  # noqa: E402
from action_probe.action_set import ACTIONS, ACTION_IDS, FORCED_STEPS  # noqa: E402


def cols():
    out = []
    for u in ACTION_IDS:
        for b in ("V0", "VL"):
            for k in range(1, cr.N + 1):
                out.append("%s_%s_t%d" % (b, u, k))
    return out


COLS = cols()


def _ratio(p, pf):
    if p is None or pf is None or p <= 0 or pf <= 0:
        return 0.0
    return min(max(p / pf, 0.0), 1.0)


def compute_r1(v0, m0, tau0, slots_win, ego_abs_s, occupancy=True):
    """Full R1 for the state with ego init (0, v0, m0, tau0) at ego_abs_s."""
    cor = StraightCorridor(cr.COR_LEN, common.lane_width())
    occ = cr.build_occ(slots_win, ego_abs_s) if occupancy else cr.empty_occ()
    empty = cr.empty_occ()
    out = {}
    for a in ACTIONS:
        r = cr.run_probe_curves((0.0, v0, m0, tau0), a["ax"], a["lateral"], occ, cor)
        rf = cr.run_probe_curves((0.0, v0, m0, tau0), a["ax"], a["lateral"], empty, cor)
        for k in range(cr.N):
            out["V0_%s_t%d" % (a["id"], k + 1)] = round(_ratio(r["p0"][k], rf["p0"][k]), 4)
            out["VL_%s_t%d" % (a["id"], k + 1)] = round(_ratio(r["pL"][k], rf["pL"][k]), 4)
    return out


def successor_r1(entry, slots_abs, ego_abs_s):
    """Recompute full R1 at T(X,u) with occupancy rebased at t0+1s."""
    if entry.get("successor") is None:
        return None
    s, v, m, tau = entry["successor"]
    win = slots_abs[FORCED_STEPS: FORCED_STEPS + cr.N + 1]
    return compute_r1(float(v), int(m), float(tau), win, ego_abs_s + s)
