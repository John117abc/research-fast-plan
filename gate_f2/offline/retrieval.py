#!/usr/bin/env python3
"""Gate F2 - leave-family-out retrieval on the full feasible frontier.

Dataset: 80 F1 samples (gate_f1/results/*/run*.summary.json).
Vector  Z = [P0/Pfree (t=0.5..10), PL/Pfree or 0 (dead corridor)]  -> 40 dims.
Families: literal scene (8) and mechanism (cross/blocked/lead).
Metrics: (a) same/diff-structure distance inequality, (b) leave-family-out
k-NN structure hit-rate vs pool baseline. (G0,GL) only used as labels.
"""
import glob
import json
import math
import os
import sys

import numpy as np

T = [0.5 * (k + 1) for k in range(20)]
SCENES = ["A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2"]
MECH = {"A1": "cross", "A2": "cross", "B1": "blocked", "B2": "blocked",
        "C1": "lead", "C2": "lead", "D1": "blocked", "D2": "blocked",
        "G1": "lead", "G2": "lead", "G3": "temp"}


def load():
    pts = []
    for f in sorted(glob.glob("gate_f1/results/*/run*.summary.json")):
        j = json.load(open(f))
        scene, group = j["scene"], j["group"]
        fine = j["fine"]
        P0 = np.array(fine["P0"], float)
        Pf = np.array(fine["Pfree"], float)
        PL = np.array([x if x is not None else 0.0 for x in fine["PL"]], float)
        nP0 = np.divide(P0, Pf, out=np.zeros_like(P0), where=Pf > 0)
        nPL = np.divide(PL, Pf, out=np.zeros_like(PL), where=Pf > 0)
        Z = np.concatenate([nP0, nPL])
        pts.append({"scene": scene, "group": group, "Z": Z,
                    "struct": j["quadrant"], "mech": MECH[scene]})
    return pts


def main():
    pts = load()
    n = len(pts)
    Z = np.stack([p["Z"] for p in pts])
    mu, sd = Z.mean(0), Z.std(0) + 1e-9
    Zz = (Z - mu) / sd
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            D[i, j] = np.linalg.norm(Zz[i] - Zz[j])
    out = {"n": n}

    def pair_stats(fam_key, tag):
        same_f = []   # diff scene (family), same structure
        diff_s = []   # same family, different structure
        same_s = []   # same family, same structure (control)
        for i in range(n):
            for j in range(i + 1, n):
                ffi, ffj = pts[i][fam_key], pts[j][fam_key]
                si, sj = pts[i]["struct"], pts[j]["struct"]
                if ffi != ffj and si == sj:
                    same_f.append(D[i, j])
                elif ffi == ffj and si != sj:
                    diff_s.append(D[i, j])
                elif ffi == ffj and si == sj:
                    same_s.append(D[i, j])
        return same_f, diff_s, same_s

    res = {}
    for key, tag in (("scene", "literal-scene"), ("mech", "mechanism")):
        same_f, diff_s, same_s = pair_stats(key, tag)
        m_same = float(np.mean(same_f)) if same_f else float("nan")
        m_diff = float(np.mean(diff_s)) if diff_s else float("nan")
        m_ctrl = float(np.mean(same_s)) if same_s else float("nan")
        res[tag] = {"n_same_f": len(same_f), "n_diff_s": len(diff_s),
                    "n_ctrl": len(same_s),
                    "mean_d_same_struct_diff_scene": round(m_same, 4),
                    "mean_d_diff_struct_same_scene": round(m_diff, 4),
                    "mean_d_same_struct_same_scene(ctrl)": round(m_ctrl, 4),
                    "claim_holds": bool(m_same < m_diff)}
        print(f"[{tag}] d(diff-scene same-struct)={m_same:.3f}  vs  "
              f"d(same-scene diff-struct)={m_diff:.3f}  | ctrl {m_ctrl:.3f} "
              f"| claim {m_same < m_diff}  (n {len(same_f)}/{len(diff_s)})")

    # leave-family-out kNN structure hit-rate
    for fam_key, tag in (("scene", "leave-scene"), ("mech", "leave-mechanism")):
        for kk in (1, 5):
            hits, tot = 0, 0
            per = {}
            for i in range(n):
                fam = pts[i][fam_key]
                cand = [j for j in range(n) if pts[j][fam_key] != fam]
                cand.sort(key=lambda j: D[i, j])
                qs = pts[i]["struct"]
                s_hit = sum(1 for j in cand[:kk] if pts[j]["struct"] == qs)
                hits += s_hit
                tot += kk
                per.setdefault(qs, [0, 0])
                per[qs][0] += s_hit
                per[qs][1] += kk
            hr = hits / tot if tot else float("nan")
            per_s = {k: round(v[0] / v[1], 3) for k, v in per.items()}
            print(f"{tag} kNN k={kk}: structure hit-rate = {hr:.3f} "
                  f"per-struct {per_s}")
    # baseline pool structure distribution
    from collections import Counter
    cnt = Counter(p["struct"] for p in pts)
    print("pool structure prior:", dict(cnt))
    json.dump({"distance_pairs": res}, open("gate_f2/results/retrieval_metrics.json", "w"),
              indent=1)
    np.save("gate_f2/results/Z.npy", Zz)
    with open("gate_f2/results/points.json", "w") as f:
        json.dump([{"scene": p["scene"], "group": p["group"], "struct": p["struct"]}
                   for p in pts], f)


if __name__ == "__main__":
    os.makedirs("gate_f2/results", exist_ok=True)
    main()
