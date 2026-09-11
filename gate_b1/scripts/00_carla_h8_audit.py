#!/usr/bin/env python3
"""B1-0 Step 1: CARLA H=8s compatibility audit (hard Gate).

On the frozen 72 confirmatory states, truncate the horizon 10s -> 8s and
recompute R1^8s (8 actions x 2 branches x 16 t = 256) plus successor R1^8s,
then:
  - Spearman(d_R8s, d_R10s) over cross-mechanism pairs (must be >= 0.90)
  - re-run B0-C1 conditions C1-C4 with UNCHANGED thresholds.

Does NOT modify any frozen file/result. R1^8s is a Waymo-adapted variant.

usage: python gate_b1/scripts/00_carla_h8_audit.py
"""
import csv
import glob
import json
import os
import sys

import numpy as np

B1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(B1)
B0 = os.path.join(ROOT, "gate_b0")
sys.path.insert(0, ROOT)
sys.path.insert(0, B0)
sys.path.insert(0, os.path.join(ROOT, "gate_f0"))

import common  # noqa: E402
from action_probe import constrained_rollout as cr  # noqa: E402
from action_probe.action_set import ACTIONS, ACTION_IDS, FORCED_STEPS  # noqa: E402
from feasible.engine import StraightCorridor  # noqa: E402

CONF = os.path.join(B0, "results/confirmatory")
RAW = os.path.join(B0, "confirmatory/raw")
OUT = os.path.join(B1, "results/b1_0/step1_carla_h8")
N8 = 16                       # 8.0 s at dt=0.5
SEED, NBOOT, CUTS = 100, 10000, [0, 10, 25, 50, 75, 100]


def cols8():
    out = []
    for u in ACTION_IDS:
        for b in ("V0", "VL"):
            for k in range(1, N8 + 1):
                out.append("%s_%s_t%d" % (b, u, k))
    return out


COLS8 = cols8()


def _ratio(p, pf):
    if p is None or pf is None or p <= 0 or pf <= 0:
        return 0.0
    return min(max(p / pf, 0.0), 1.0)


def compute_r1_8s(v0, m0, tau0, slots_win, ego_abs_s):
    cor = StraightCorridor(cr.COR_LEN, common.lane_width())
    occ = cr.build_occ(slots_win, ego_abs_s, n_steps=N8)
    empty = cr.empty_occ(n_steps=N8)
    out = {}
    for a in ACTIONS:
        r = cr.run_probe_curves((0.0, v0, m0, tau0), a["ax"], a["lateral"], occ, cor,
                                n_steps=N8)
        rf = cr.run_probe_curves((0.0, v0, m0, tau0), a["ax"], a["lateral"], empty, cor,
                                 n_steps=N8)
        for k in range(N8):
            out["V0_%s_t%d" % (a["id"], k + 1)] = round(_ratio(r["p0"][k], rf["p0"][k]), 4)
            out["VL_%s_t%d" % (a["id"], k + 1)] = round(_ratio(r["pL"][k], rf["pL"][k]), 4)
    return out


def list_states():
    states = {}
    for path in sorted(glob.glob(os.path.join(RAW, "*/*/*.ndjson"))):
        parts = path.replace("\\", "/").split("/")
        mech, cell = parts[-3], parts[-2]
        cid = parts[-1][:-len(".ndjson")]
        with open(path) as fh:
            first = json.loads(fh.readline())
        sc = first.get("scenario", {})
        states[cid] = {"path": path, "mech": mech, "cell": cell,
                       "coarse": common.coarse_of(mech),
                       "ego_speed": float(sc.get("v_target", 0.0)),
                       "ego_s": float(first.get("ego_s", 0.0))}
    return states


def rankdata(a):
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), float)
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and a[order[j + 1]] == a[order[i]]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1
        i = j + 1
    return ranks


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3 or np.std(x) < 1e-12 or np.std(y) < 1e-12:
        return float("nan")
    return float(np.corrcoef(rankdata(x), rankdata(y))[0, 1])


def main():
    os.makedirs(os.path.join(OUT, "figures"), exist_ok=True)
    states = list_states()
    assert len(states) == 72, len(states)

    # ---- compute R1^8s + successor R1^8s from raw ----
    X8, S8, meta = {}, {}, {}
    cor = StraightCorridor(cr.COR_LEN, common.lane_width())
    for cid, st in states.items():
        slots = common.build_slots(st["path"])
        occ = cr.build_occ(slots[: N8 + 1], st["ego_s"], n_steps=N8)
        r1d = compute_r1_8s(st["ego_speed"], 0, 0.0, slots[: N8 + 1], st["ego_s"])
        X8[cid] = np.array([r1d[c] for c in COLS8])
        S8[cid] = {}
        for a in ACTIONS:
            pr = cr.run_probe((0.0, st["ego_speed"], 0, 0.0), a["ax"], a["lateral"], occ, cor,
                              n_steps=N8)
            if not pr["valid"]:
                S8[cid][a["id"]] = None
                continue
            s = pr["successor"]
            win = slots[FORCED_STEPS: FORCED_STEPS + N8 + 1]
            sr = compute_r1_8s(float(s[1]), int(s[2]), float(s[3]), win, st["ego_s"] + s[0])
            S8[cid][a["id"]] = np.array([sr[c] for c in COLS8])
        meta[cid] = {"coarse": st["coarse"], "group": "%s|%s" % (st["cell"], st["mech"])}
        print("done", cid)

    # ---- d_R10s for comparison (already frozen) ----
    l10 = list(csv.DictReader(open(os.path.join(CONF, "r1_signatures.csv"))))
    COLS10 = [c for c in l10[0].keys() if "_t" in c]
    X10 = {r["state_id"]: np.array([float(r[c]) for c in COLS10]) for r in l10}

    ids = sorted(states)
    # ---- cross pairs: d0/d1 at 8s and 10s ----
    pairs = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            if meta[a]["coarse"] == meta[b]["coarse"]:
                continue
            d0_8 = float(np.mean(np.abs(X8[a] - X8[b])))
            d0_10 = float(np.mean(np.abs(X10[a] - X10[b])))
            d1s_8 = [float(np.mean(np.abs(S8[a][u] - S8[b][u])))
                     for u in ACTION_IDS if S8[a][u] is not None and S8[b][u] is not None]
            pairs.append({"state_i": a, "state_j": b, "coarse_i": meta[a]["coarse"],
                          "coarse_j": meta[b]["coarse"], "same_group": int(meta[a]["group"] == meta[b]["group"]),
                          "d0_8": d0_8, "d0_10": d0_10,
                          "d1_8": float(np.mean(d1s_8)) if d1s_8 else float("nan")})
    c_d0_8 = np.array([p["d0_8"] for p in pairs])
    c_d0_10 = np.array([p["d0_10"] for p in pairs])
    c_d1_8 = np.array([p["d1_8"] for p in pairs])
    rho_dist = spearman(c_d0_8, c_d0_10)

    # ---- same-mechanism matched controls at 8s ----
    same = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            if meta[a]["coarse"] != meta[b]["coarse"]:
                continue
            same.append({"state_i": a, "state_j": b,
                         "d0_8": float(np.mean(np.abs(X8[a] - X8[b]))),
                         "same_group": int(meta[a]["group"] == meta[b]["group"]),
                         "d1_8": float(np.mean([np.mean(np.abs(S8[a][u] - S8[b][u]))
                                                for u in ACTION_IDS
                                                if S8[a][u] is not None and S8[b][u] is not None]))})
    s_d0 = np.array([s["d0_8"] for s in same])
    s_grp = np.array([s["same_group"] for s in same])
    D = np.abs(s_d0[None, :] - c_d0_8[:, None])
    D[:, s_grp == 1] = np.inf
    nearest = np.argmin(D, axis=1)
    m_d1 = np.array([same[int(k)]["d1_8"] for k in nearest])

    # ---- quantiles / C1-C4 ----
    qcuts = np.percentile(c_d0_8, CUTS)
    qmask = {}
    qrows = []
    for q in range(5):
        lo, hi = qcuts[q], qcuts[q + 1]
        m = (c_d0_8 >= lo) & (c_d0_8 <= hi if q == 4 else c_d0_8 < hi)
        qmask["Q%d" % (q + 1)] = m
        qrows.append({"quantile": "Q%d" % (q + 1), "n": int(m.sum()),
                      "D1_median": round(float(np.median(c_d1_8[m])), 5)})
    rho_all = spearman(c_d0_8, c_d1_8)
    mech = {}
    for combo in [("cross", "lead"), ("block_or_occupancy", "cross"),
                  ("block_or_occupancy", "lead")]:
        key = set(combo)
        m = np.array([set([p["coarse_i"], p["coarse_j"]]) == key for p in pairs])
        mech["|".join(sorted(combo))] = round(spearman(c_d0_8[m], c_d1_8[m]), 4)

    ids_idx = {s: k for k, s in enumerate(ids)}
    ci = np.array([ids_idx[p["state_i"]] for p in pairs])
    cj = np.array([ids_idx[p["state_j"]] for p in pairs])
    rng = np.random.default_rng(SEED)
    boot_rho, boot_q = [], []
    for _ in range(NBOOT):
        pres = np.zeros(len(ids), bool)
        pres[rng.integers(0, len(ids), len(ids))] = True
        cm = pres[ci] & pres[cj]
        if cm.sum() >= 3:
            boot_rho.append(spearman(c_d0_8[cm], c_d1_8[cm]))
            q1 = c_d1_8[cm & qmask["Q1"]]
            q5 = c_d1_8[cm & qmask["Q5"]]
            if len(q1) and len(q5):
                boot_q.append(float(np.median(q1) - np.median(q5)))

    def ci95(v):
        v = [x for x in v if x == x]
        return (round(float(np.percentile(v, 2.5)), 5), round(float(np.percentile(v, 97.5)), 5)) if v else (None, None)

    med_q1 = float(np.median(c_d1_8[qmask["Q1"]]))
    med_q5 = float(np.median(c_d1_8[qmask["Q5"]]))
    ratio = float(np.median(c_d1_8)) / (float(np.median(m_d1)) + 1e-12)
    lo_rho, hi_rho = ci95(boot_rho)
    conds = {
        "dist_rank_corr>=0.90": bool(rho_dist >= 0.90),
        "C1_rho>=0.60_CIlow>0.40": bool(rho_all >= 0.60 and lo_rho is not None and lo_rho > 0.40),
        "C2_Q1<=0.5*Q5": bool(med_q1 <= 0.5 * med_q5),
        "C3_two_of_three_mech_rho>0.50": bool(sum(1 for v in mech.values() if v > 0.50) >= 2),
        "C4_matched_ratio<=1.25": bool(ratio <= 1.25),
    }
    result = {"n_cross_pairs": len(pairs), "n_same_pairs": len(same),
              "spearman_d8_d10": round(rho_dist, 4),
              "spearman_d0_d1_8s": round(rho_all, 4),
              "spearman_CI": [lo_rho, hi_rho],
              "median_D1_Q1": round(med_q1, 5), "median_D1_Q5": round(med_q5, 5),
              "matched_ratio": round(ratio, 4),
              "mechanism_rho": mech, "quantiles": qrows,
              "conditions": conds,
              "STEP1_PASS": bool(all(conds.values()))}
    json.dump(result, open(os.path.join(OUT, "step1_result.json"), "w"), indent=1)
    with open(os.path.join(OUT, "pair_distances_8s.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(pairs[0].keys()))
        w.writeheader()
        w.writerows(pairs)
    _figures(c_d0_8, c_d0_10, c_d1_8, qrows, mech)
    _report(result)
    print(json.dumps(result, indent=1))


def _figures(d0_8, d0_10, d1_8, qrows, mech):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.figure(); plt.scatter(d0_8, d0_10, s=5, alpha=0.25)
    plt.xlabel("d_R8s"); plt.ylabel("d_R10s"); plt.title("Step1: 8s vs 10s pairwise distance")
    plt.savefig(os.path.join(OUT, "figures", "step1_d8_vs_d10.png"), dpi=120, bbox_inches="tight"); plt.close()
    plt.figure(); plt.scatter(d0_8, d1_8, s=5, alpha=0.25)
    plt.xlabel("d0 (8s)"); plt.ylabel("D1 (8s)"); plt.title("Step1: d0->D1 at 8s")
    plt.savefig(os.path.join(OUT, "figures", "step1_d0_vs_d1_8s.png"), dpi=120, bbox_inches="tight"); plt.close()


def _report(r):
    L = ["# B1-0 Step 1: CARLA H=8s compatibility audit", "",
         "Frozen 72 confirmatory states; horizon truncated 10s -> 8s; no threshold change.",
         "", "## Pre-registered criterion",
         "Spearman(d_R8s, d_R10s) >= 0.90 AND C1-C4 all PASS.", "",
         "## Result",
         "- cross-mechanism pairs: %d; same-mechanism pairs: %d" % (r["n_cross_pairs"], r["n_same_pairs"]),
         "- Spearman(d_R8s, d_R10s) = **%.3f**" % r["spearman_d8_d10"],
         "- Spearman(d0,D1) at 8s = %.3f, 95%% CI [%s, %s]" % (r["spearman_d0_d1_8s"], r["spearman_CI"][0], r["spearman_CI"][1]),
         "- median D1: Q1=%.4f Q5=%.4f; matched ratio=%.4f" % (r["median_D1_Q1"], r["median_D1_Q5"], r["matched_ratio"]),
         "- mechanism rho: %s" % r["mechanism_rho"], "",
         "| condition | met |", "|---|---|"]
    for k, v in r["conditions"].items():
        L.append("| %s | %s |" % (k, v))
    L += ["", "## Verdict: **%s**" % ("STEP1 PASS -> continue B1-0 Steps 2-6" if r["STEP1_PASS"]
          else "STEP1 FAIL -> STOP B1-0; do not adapt R1 for Waymo"), ""]
    open(os.path.join(OUT, "STEP1_report.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
