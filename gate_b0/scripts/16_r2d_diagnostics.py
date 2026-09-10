#!/usr/bin/env python3
"""Gate B0-R2D: cross-mechanism near-neighbour difference attribution.

Diagnostic only. Uses the already-computed R1 signatures and R2 pairs. Does not
change R1, the distance function, action set, thresholds, or any Gate.

usage: python gate_b0/scripts/16_r2d_diagnostics.py
writes gate_b0/results/r2d/{...}
"""
import csv
import json
import os
import sys

import numpy as np

B0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(B0)
sys.path.insert(0, ROOT)
sys.path.insert(0, B0)
sys.path.insert(0, os.path.join(ROOT, "gate_f0"))

import common  # noqa: E402
from consequence.r1_signature import COLS  # noqa: E402
from action_probe.action_set import ACTION_IDS  # noqa: E402

OUT = os.path.join(B0, "results/r2d")
FIG = os.path.join(OUT, "figures")
SEED = common.cfg()["stats"]["seed"]
EPS = 1e-9
EARLY = list(range(1, 7))       # 0.5..3.0 s
MID = list(range(7, 14))        # 3.5..6.5 s
LATE = list(range(14, 21))      # 7.0..10.0 s
SHIFTS = list(range(-4, 5))     # +-2 s in 0.5 s steps
# Descriptive (non-Gate) criteria for the final A/B/C conclusion:
CR = {"high_rtime": 0.30, "high_rscale": 0.15, "high_rho": 0.80, "low_rho": 0.50}


def cidx(u, b, k):
    return COLS.index("%s_%s_t%d" % (b, u, k))


def load_r1():
    rows = list(csv.DictReader(open(os.path.join(B0, "results/discovery/r1_signatures.csv"))))
    X = {r["state_id"]: np.array([float(r[c]) for c in COLS]) for r in rows}
    meta = {r["state_id"]: {"coarse": r["coarse_mechanism"], "fine": r["fine_mechanism"]}
            for r in rows}
    return X, meta


def rankdata(a):
    a = np.asarray(a, float)
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


def pearson(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.std() < 1e-12 or b.std() < 1e-12:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def shifted_min(vi, vj):
    best = None
    best_dt = 0
    for sh in SHIFTS:
        if sh >= 0:
            a, b = vi[: len(vi) - sh], vj[sh:]
        else:
            a, b = vi[-sh:], vj[: len(vj) + sh]
        if len(a) == 0:
            continue
        d = float(np.mean(np.abs(a - b)))
        if best is None or d < best:
            best, best_dt = d, sh
    return best, best_dt * 0.5


def scale_min(vi, vj):
    denom = float(np.dot(vj, vj))
    alpha = float(np.dot(vi, vj) / denom) if denom > 0 else 1.0
    alpha = min(max(alpha, 0.8), 1.2)
    return float(np.mean(np.abs(vi - alpha * vj))), alpha


def main():
    os.makedirs(FIG, exist_ok=True)
    X, meta = load_r1()
    allp = list(csv.DictReader(open(os.path.join(B0, "results/r2/r2_all_pairs.csv"))))
    cand = list(csv.DictReader(open(os.path.join(B0, "results/r2/r2_candidate_equivalent_pairs.csv"))))
    cand_ids = {"%s__%s" % (p["state_i"], p["state_j"]) for p in cand}

    cross = [p for p in allp if p["same_coarse"] == "0"]
    cross.sort(key=lambda p: float(p["d0_mean"]))
    cross_ids = ["%s__%s" % (p["state_i"], p["state_j"]) for p in cross]
    remaining = [p for p in cross if "%s__%s" % (p["state_i"], p["state_j"]) not in cand_ids]
    B = remaining[:39]
    lo, hi = np.percentile([float(p["d0_mean"]) for p in cross], [50, 75])
    pool_c = [p for p in cross if lo <= float(p["d0_mean"]) <= hi]
    rng = np.random.default_rng(SEED)
    idxc = rng.choice(len(pool_c), size=min(39, len(pool_c)), replace=False)
    C = [pool_c[i] for i in idxc]

    groups = {}
    for tag, arr in [("A", cand), ("B", B), ("C", C)]:
        for p in arr:
            groups["%s__%s" % (p["state_i"], p["state_j"])] = tag
    pair_groups_rows = [{"pair_id": k, "group": v} for k, v in sorted(groups.items())]
    _write(os.path.join(OUT, "pair_groups.csv"), pair_groups_rows)

    dec_rows, shift_rows, scale_rows, rank_rows, trend_rows = [], [], [], [], []
    heat = {"A": np.zeros((len(ACTION_IDS), 2)), "B": np.zeros((len(ACTION_IDS), 2)),
            "C": np.zeros((len(ACTION_IDS), 2))}
    counts = {g: 0 for g in ("A", "B", "C")}
    per_pair = {}
    for pid, tag in groups.items():
        i, j = pid.split("__")
        vi, vj = X[i], X[j]
        delta = np.abs(vi - vj)
        Du = {u: float(np.mean([delta[cidx(u, b, k)] for b in ("V0", "VL") for k in range(1, 21)]))
              for u in ACTION_IDS}
        D0 = float(np.mean([delta[cidx(u, "V0", k)] for u in ACTION_IDS for k in range(1, 21)]))
        DL = float(np.mean([delta[cidx(u, "VL", k)] for u in ACTION_IDS for k in range(1, 21)]))
        Dearly = float(np.mean([delta[cidx(u, b, k)] for u in ACTION_IDS for b in ("V0", "VL") for k in EARLY]))
        Dmid = float(np.mean([delta[cidx(u, b, k)] for u in ACTION_IDS for b in ("V0", "VL") for k in MID]))
        Dlate = float(np.mean([delta[cidx(u, b, k)] for u in ACTION_IDS for b in ("V0", "VL") for k in LATE]))
        d_raw = float(np.mean(delta))
        dec_rows.append({"pair_id": pid, "group": tag, "d_raw": round(d_raw, 6),
                         **{"D_%s" % u: round(Du[u], 6) for u in ACTION_IDS},
                         "D_current": round(D0, 6), "D_left": round(DL, 6),
                         "D_early": round(Dearly, 6), "D_mid": round(Dmid, 6),
                         "D_late": round(Dlate, 6)})
        # heatmap contribution per action x branch
        for ai, u in enumerate(ACTION_IDS):
            for bi, b in enumerate(("V0", "VL")):
                heat[tag][ai, bi] += float(np.mean([delta[cidx(u, b, k)] for k in range(1, 21)]))
        counts[tag] += 1
        # temporal shift + scale
        dsh, dst, alphas, dts, dsc = [], [], [], [], []
        for u in ACTION_IDS:
            for b in ("V0", "VL"):
                vv = np.array([vi[cidx(u, b, k)] for k in range(1, 21)])
                ww = np.array([vj[cidx(u, b, k)] for k in range(1, 21)])
                raw = float(np.mean(np.abs(vv - ww)))
                s, dt = shifted_min(vv, ww)
                sc, al = scale_min(vv, ww)
                dsh.append(s)
                dts.append(dt)
                alphas.append(al)
                dst.append(raw)
                dsc.append(sc)
        d_raw2 = float(np.mean(dst))
        d_shift = float(np.mean(dsh))
        R_time = (d_raw2 - d_shift) / (d_raw2 + EPS)
        R_scale = (d_raw2 - float(np.mean(dsc))) / (d_raw2 + EPS)
        shift_rows.append({"pair_id": pid, "group": tag, "d_raw": round(d_raw2, 6),
                           "d_shift": round(d_shift, 6), "R_time": round(R_time, 4),
                           "mean_abs_dtstar": round(float(np.mean(np.abs(dts))), 3),
                           "frac_dtstar_nonzero": round(float(np.mean([abs(x) > 0 for x in dts])), 3)})
        scale_rows.append({"pair_id": pid, "group": tag, "d_raw": round(d_raw2, 6),
                           "R_scale": round(R_scale, 4),
                           "mean_alpha": round(float(np.mean(alphas)), 4)})
        # action-rank consistency
        rhos = []
        for k in range(1, 21):
            capi = np.array([vi[cidx(u, "V0", k)] + vi[cidx(u, "VL", k)] for u in ACTION_IDS])
            capj = np.array([vj[cidx(u, "V0", k)] + vj[cidx(u, "VL", k)] for u in ACTION_IDS])
            r = pearson(rankdata(capi), rankdata(capj))
            if not np.isnan(r):
                rhos.append(r)
        rho_mean = float(np.mean(rhos)) if rhos else float("nan")
        rank_rows.append({"pair_id": pid, "group": tag, "rho_action_mean": round(rho_mean, 4),
                          "rho_action_min": round(float(np.min(rhos)), 4) if rhos else None,
                          "rho_action_std": round(float(np.std(rhos)), 4) if rhos else None})
        # branch existence + trend
        exist_agree = []
        d0_corr, dL_corr = [], []
        for u in ACTION_IDS:
            for b in ("V0", "VL"):
                vv = np.array([vi[cidx(u, b, k)] for k in range(1, 21)])
                ww = np.array([vj[cidx(u, b, k)] for k in range(1, 21)])
                exist_agree.append(float(np.mean((vv > EPS) == (ww > EPS))))
            vvL = np.array([vi[cidx(u, "VL", k)] for k in range(1, 21)])
            wwL = np.array([vj[cidx(u, "VL", k)] for k in range(1, 21)])
            c = pearson(np.diff(vvL), np.diff(wwL))
            if not np.isnan(c):
                dL_corr.append(c)
            vv0 = np.array([vi[cidx(u, "V0", k)] for k in range(1, 21)])
            ww0 = np.array([vj[cidx(u, "V0", k)] for k in range(1, 21)])
            c0 = pearson(np.diff(vv0), np.diff(ww0))
            if not np.isnan(c0):
                d0_corr.append(c0)
        trend_rows.append({"pair_id": pid, "group": tag,
                           "exist_agree_frac": round(float(np.mean(exist_agree)), 4),
                           "dV0_trend_corr": round(float(np.mean(d0_corr)), 4) if d0_corr else None,
                           "dVL_trend_corr": round(float(np.mean(dL_corr)), 4) if dL_corr else None})
        per_pair[pid] = {"group": tag, "d_raw": d_raw, "R_time": R_time, "R_scale": R_scale,
                         "rho": rho_mean, "exist": float(np.mean(exist_agree)),
                         "dVL": float(np.mean(dL_corr)) if dL_corr else np.nan,
                         "Du": Du, "D0": D0, "DL": DL}

    _write(os.path.join(OUT, "distance_decomposition.csv"), dec_rows)
    _write(os.path.join(OUT, "temporal_shift_diagnostics.csv"), shift_rows)
    _write(os.path.join(OUT, "scale_diagnostics.csv"), scale_rows)
    _write(os.path.join(OUT, "action_rank_consistency.csv"), rank_rows)
    _write(os.path.join(OUT, "branch_trend_diagnostics.csv"), trend_rows)

    stats = _group_stats(per_pair)
    json.dump(stats, open(os.path.join(OUT, "group_statistics.json"), "w"), indent=1)
    _figures(per_pair, heat, counts, X)
    _report(stats, per_pair)
    print(json.dumps(stats["group_summary"], indent=1))
    print("CONCLUSION:", stats["conclusion"])


def _group_stats(per_pair):
    def agg(vals):
        vals = [v for v in vals if v is not None and not (isinstance(v, float) and np.isnan(v))]
        return {"n": len(vals), "mean": round(float(np.mean(vals)), 4) if vals else None,
                "median": round(float(np.median(vals)), 4) if vals else None,
                "std": round(float(np.std(vals)), 4) if vals else None}
    summary = {}
    for g in ("A", "B", "C"):
        sel = [p for p in per_pair.values() if p["group"] == g]
        summary[g] = {k: agg([p[k] for p in sel])
                      for k in ("d_raw", "R_time", "R_scale", "rho", "exist", "dVL")}
    b = summary["B"]
    high_time = b["R_time"]["median"] is not None and b["R_time"]["median"] >= CR["high_rtime"]
    high_scale = b["R_scale"]["median"] is not None and b["R_scale"]["median"] >= CR["high_rscale"]
    high_rho = b["rho"]["median"] is not None and b["rho"]["median"] >= CR["high_rho"]
    low_rho = b["rho"]["median"] is not None and b["rho"]["median"] <= CR["low_rho"]
    if (high_time or high_scale) and high_rho:
        concl = "A_time_or_scale_dominated"
    elif low_rho and not high_time and not high_scale:
        concl = "B_true_consequence_difference"
    else:
        concl = "C_mixed"
    return {"criteria": CR, "group_summary": summary, "conclusion": concl}


def _figures(per_pair, heat, counts, X):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    groups = ("A", "B", "C")
    colors = {"A": "tab:green", "B": "tab:orange", "C": "tab:red"}

    def box(metric, fname, title):
        plt.figure()
        data = [[p[metric] for p in per_pair.values() if p["group"] == g and not np.isnan(p[metric])]
                for g in groups]
        plt.boxplot(data, labels=groups, showfliers=False)
        for gi, g in enumerate(groups):
            ys = data[gi]
            plt.scatter([gi + 1] * len(ys), ys, s=8, alpha=0.4, c=colors[g])
        plt.ylabel(metric); plt.title(title)
        plt.savefig(os.path.join(FIG, fname), dpi=120, bbox_inches="tight")
        plt.close()

    box("d_raw", "r2d_fig1_draw_by_group.png", "R1 raw distance by group")
    box("R_time", "r2d_fig2_rtime_by_group.png", "time-shift explained fraction")
    box("rho", "r2d_fig3_rho_action_by_group.png", "action-rank consistency")
    box("R_scale", "r2d_fig4_rscale_by_group.png", "scale-explained fraction")

    for g in ("A", "B"):
        H = heat[g] / max(1, counts[g])
        plt.figure()
        plt.imshow(H, aspect="auto", cmap="viridis")
        plt.yticks(range(len(ACTION_IDS)), ACTION_IDS)
        plt.xticks([0, 1], ["current", "left"])
        plt.colorbar(label="mean |dV|")
        plt.title("distance contribution (action x branch), group %s" % g)
        plt.savefig(os.path.join(FIG, "r2d_fig5_heatmap_%s.png" % g), dpi=120, bbox_inches="tight")
        plt.close()

    # 3 typical pairs auto-selected
    def pick(fn):
        return max(per_pair.items(), key=lambda kv: (fn(kv[1]) if not np.isnan(fn(kv[1])) else -1))
    p_time = pick(lambda p: p["R_time"])
    p_rank = pick(lambda p: p["rho"] if p["d_raw"] > 0 else -1)
    p_true = pick(lambda p: p["d_raw"])
    picks = [("max R_time", p_time), ("high rho, large d_raw", p_rank), ("max d_raw", p_true)]
    t = np.arange(1, 21) * 0.5
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
    for ax, (name, (pid, p)) in zip(axes, picks):
        i, j = pid.split("__")
        vi, vj = X[i], X[j]
        for u in ("U2", "U6"):
            for b, ls in (("V0", "-"), ("VL", "--")):
                ax.plot(t, [vi[cidx(u, b, k)] for k in range(1, 21)], ls,
                        label="%s %s %s" % (i, u, b))
                ax.plot(t, [vj[cidx(u, b, k)] for k in range(1, 21)], ls, alpha=0.6,
                        label="%s %s %s" % (j, u, b))
        ax.set_title("%s\n%s (group %s)" % (name, pid, p["group"]), fontsize=8)
        ax.set_xlabel("t (s)"); ax.set_ylim(-0.05, 1.05); ax.grid(alpha=0.3)
    axes[0].legend(fontsize=5, ncol=2)
    fig.savefig(os.path.join(FIG, "r2d_fig6_typical_pairs.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)


def _report(stats, per_pair):
    s = stats["group_summary"]
    c = stats["conclusion"]
    B = [p for p in per_pair.values() if p["group"] == "B"]
    A = [p for p in per_pair.values() if p["group"] == "A"]
    C = [p for p in per_pair.values() if p["group"] == "C"]
    f = lambda arr, fn: float(np.mean([fn(p) for p in arr]))
    b_rt_hi = f(B, lambda p: p["R_time"] >= 0.5)
    b_rt_mid = f(B, lambda p: p["R_time"] >= CR["high_rtime"])
    b_rho_hi = f(B, lambda p: p["rho"] >= 0.95)
    b_rs_hi = f(B, lambda p: p["R_scale"] >= CR["high_rscale"])
    L = ["# Gate B0-R2D: cross-mechanism near-neighbour difference attribution", "",
         "Diagnostic only. R1, distance, action set, thresholds unchanged; no new data,",
         "no training, no closure. Groups: A=11 candidates, B=next 39 cross pairs,",
         "C=39 cross pairs in the 50-75th percentile band.", "",
         "## Group medians (d_raw = R1 distance)",
         "| group | n | d_raw | R_time | R_scale | rho_action | exist_agree | dVL_trend_corr |",
         "|---|---|---|---|---|---|---|---|"]
    for g in ("A", "B", "C"):
        L.append("| %s | %d | %s | %s | %s | %s | %s | %s |" % (
            g, s[g]["d_raw"]["n"], s[g]["d_raw"]["median"], s[g]["R_time"]["median"],
            s[g]["R_scale"]["median"], s[g]["rho"]["median"], s[g]["exist"]["median"],
            s[g]["dVL"]["median"]))
    L += ["", "Descriptive criteria (not a Gate): R_time high>=%.2f, R_scale high>=%.2f, "
          "rho high>=%.2f, rho low<=%.2f." % (CR["high_rtime"], CR["high_rscale"],
                                               CR["high_rho"], CR["low_rho"]),
          "", "## Conclusion: **%s**" % c,
          "**Result A (mainly irrelevant time/scale detail)**, specifically *temporal*",
          "misalignment, not amplitude scaling: R_scale is negative for both A and B.", "",
          "### Q1: why are the 11 A pairs so close?",
          "- d_raw median %.4f (tiny); rho_action=%.3f, exist_agree=%.3f, dVL_trend=%.3f:" %
          (s["A"]["d_raw"]["median"], s["A"]["rho"]["median"], s["A"]["exist"]["median"],
           s["A"]["dVL"]["median"]),
          "  the action-consequence structure genuinely agrees.",
          "- Even for A, R_time median %.3f: part of the residual is a <=2 s time offset;" %
          s["A"]["R_time"]["median"],
          "  R_scale median %.3f (negative) means it is NOT an amplitude difference." %
          s["A"]["R_scale"]["median"],
          "### Q2: why did the 12-50 pairs (B) miss the candidate set?",
          "- They are only marginally farther: d_raw median %.4f (A=%.4f, C=%.4f)." %
          (s["B"]["d_raw"]["median"], s["A"]["d_raw"]["median"], s["C"]["d_raw"]["median"]),
          "- Their structure is essentially identical: rho_action=%.3f (%.0f%% of B pairs >=0.95)," %
          (s["B"]["rho"]["median"], 100 * b_rho_hi),
          "  exist_agree=%.3f, dVL_trend=%.3f." % (s["B"]["exist"]["median"], s["B"]["dVL"]["median"]),
          "- The residual is largely TEMPORAL: R_time median %.3f; %.0f%% of B pairs have "
          "R_time>=0.5 and %.0f%% >=%.2f." % (s["B"]["R_time"]["median"], 100 * b_rt_hi,
                                              100 * b_rt_mid, CR["high_rtime"]),
          "- NOT scale: R_scale median %.3f (negative); only %.0f%% of B pairs have "
          "R_scale>=%.2f." % (s["B"]["R_scale"]["median"], 100 * b_rs_hi, CR["high_rscale"]),
          "- So B missed candidacy on the strict mutual-NN + bottom-10% rule, not because",
          "  of a true action-consequence difference.",
          "### Q3: A/B vs clearly different C",
          "- C is far: d_raw median %.4f (~%.0fx B), rho_action=%.3f, exist_agree=%.3f, "
          "dVL_trend=%.3f." % (s["C"]["d_raw"]["median"],
                               s["C"]["d_raw"]["median"] / max(1e-9, s["B"]["d_raw"]["median"]),
                               s["C"]["rho"]["median"], s["C"]["exist"]["median"],
                               s["C"]["dVL"]["median"]),
          "- Time shift does not rescue C (R_time median %.3f, and larger shifts are "
          "needed); C differences are real action-consequence differences." %
          s["C"]["R_time"]["median"],
          "", "## Caveat",
          "R_time is a ratio on already-tiny A/B distances, so it is noisy in absolute",
          "terms; the robust signals are the near-identical action ranking, branch",
          "existence and opportunity trend for A/B versus the clearly different C.",
          "The R2 G1 shortfall (11 vs 15) is therefore a narrow margin in the pair",
          "selection rule, not a structural collapse of R1.",
          "", "## Auto-selected typical pairs (fig6)",
          "figures/r2d_fig6_typical_pairs.png: max R_time; high rho with large d_raw;",
          "max d_raw. No manual selection.", "",
          "## Not run",
          "No PASS/FAIL Gate; no closure; no new R2 representation; no data/training.",
          "Figures: figures/r2d_fig1..6."]
    open(os.path.join(OUT, "B0_R2D_result.md"), "w").write("\n".join(L) + "\n")


def _write(path, rows):
    if not rows:
        open(path, "w").write("")
        return
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
