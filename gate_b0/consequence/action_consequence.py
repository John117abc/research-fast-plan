"""Gate B0 action-conditioned feasible consequence R0(X) = {M,V}_{8 actions}."""
from feasible.engine import StraightCorridor  # noqa: E402

import common  # noqa: E402
from action_probe import constrained_rollout as cr  # noqa: E402
from action_probe.action_set import ACTIONS, ACTION_IDS  # noqa: E402

CFG = common.cfg()
V_HEALTH_HI = CFG["gates"]["discovery"]["v_health_hi"]


def compute_signature(v0, m0, tau0, slots_win, ego_abs_s, occupancy=True):
    """R0 for the state whose ego init is (0, v0, m0, tau0) relative to ego_abs_s.

    slots_win : occupancy frames (0.5 s) covering the next N steps, absolute s.
    Returns dict with per-action entries plus compact M/V vectors.
    """
    cor = StraightCorridor(cr.COR_LEN, common.lane_width())
    occ = cr.build_occ(slots_win, ego_abs_s) if occupancy else cr.empty_occ()
    empty = cr.empty_occ()
    actions = {}
    Mv, Vv = [], []
    for a in ACTIONS:
        pr = cr.run_probe((0.0, v0, m0, tau0), a["ax"], a["lateral"], occ, cor)
        pf = cr.run_probe((0.0, v0, m0, tau0), a["ax"], a["lateral"], empty, cor)
        qfree = float(pf["best"]) if (pf["valid"] and pf["best"] >= 0) else 0.0
        if pr["valid"] and pr["best"] >= 0:
            M, Q = 1, float(pr["best"])
        else:
            M, Q = 0, 0.0
        if M == 1 and qfree > 0:
            V_raw = Q / qfree
            V = min(max(V_raw, 0.0), 1.0)
        else:
            V_raw, V = None, 0.0
        actions[a["id"]] = {
            "id": a["id"], "valid": bool(pr["valid"]), "M": M, "Q": round(Q, 4),
            "Qfree": round(qfree, 4),
            "V_raw": (round(V_raw, 4) if V_raw is not None else None),
            "V": round(V, 4),
            "successor": ([round(x, 4) for x in pr["successor"]]
                          if pr["successor"] is not None else None),
        }
        Mv.append(M)
        Vv.append(V)
    return {"actions": actions, "M": Mv, "V": Vv,
            "qfree_ok": all(actions[i]["Qfree"] > 0 for i in ACTION_IDS),
            "v_anomaly": any(actions[i]["V_raw"] is not None and
                             actions[i]["V_raw"] > V_HEALTH_HI for i in ACTION_IDS)}
