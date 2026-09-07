#!/usr/bin/env python3
"""Gate6 6.12A degeneracy check:
- R_long = Ex/(Ex+Ey) per state (dx vs dy energy over all I blocks)
- candidate sets: Full(dx+dy), Longitudinal(dx), Lateral(dy), Progress(P5)
  (equal-intervention block-normalized for direction; mag>=0.5 kept for Full/Long/Lat)
- overlaps & cos-correlations over the Primary cross-pair universe.
"""
import csv
import itertools
import os
from collections import defaultdict

import numpy as np

BLOCKS = ["I1", "I2", "I3", "I4", "I5"]
EPS = 1e-9


def load():
    out = {}
    for r in csv.DictReader(open("gate6/selected_states_v3.csv")):
        if r["primary_mechanistic"] != "1":
            continue
        d = dict(np.load(os.path.join("gate6/signatures", f"{r['state_id']}.npz")))
        w0 = d["W0"]
        dx, dy = [], []
        for k in BLOCKS:
            dW = d[k] - w0  # (8,2)
            dx.append(dW[:, 0])
            dy.append(dW[:, 1])
        dx = np.concatenate(dx)  # (40,)
        dy = np.concatenate(dy)
        # per-block norms for equal-intervention
        def block_norms(vec2d):
            return [np.linalg.norm(vec2d[i] + EPS) for i in range(5)]
        dxb = np.concatenate([dx[i * 8:(i + 1) * 8] / (np.linalg.norm(dx[i * 8:(i + 1) * 8]) + EPS) for i in range(5)])
        dyb = np.concatenate([dy[i * 8:(i + 1) * 8] / (np.linalg.norm(dy[i * 8:(i + 1) * 8]) + EPS) for i in range(5)])
        dxyb = np.concatenate([np.concatenate([dx[i * 8:(i + 1) * 8], dy[i * 8:(i + 1) * 8]]) /
                               (np.linalg.norm(np.concatenate([dx[i * 8:(i + 1) * 8], dy[i * 8:(i + 1) * 8]])) + EPS)
                               for i in range(5)])
        # progress 5-dim: dX of last waypoint per block
        p5 = np.array([dx[i * 8 + 7] for i in range(5)], dtype=float)
        out[r["state_id"]] = {
            "R_long": float((dx ** 2).sum() / ((dx ** 2).sum() + (dy ** 2).sum() + EPS)),
            "dx": dx, "dy": dy,
            "s_x": dxb, "s_y": dyb, "s_xy": dxyb, "p5": p5,
            "grp": r["scenario_group"], "uid": r["unique_instance_id"],
            "snap": (r["unique_instance_id"].split("|")[0], r["frame"]),
        }
    return out


def cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + EPS))


def main():
    st = load()
    print("primary states:", len(st))
    rl = [v["R_long"] for v in st.values()]
    print("R_long all primary: median=%.3f  frac>0.8=%.3f  frac>0.9=%.3f" % (
        sorted(rl)[len(rl) // 2], sum(1 for x in rl if x > 0.8) / len(rl),
        sum(1 for x in rl if x > 0.9) / len(rl)))
    grp = defaultdict(list)
    for v in st.values():
        grp[v["grp"]].append(v["R_long"])
    for g in ("A_HardBreak", "B_ParkingCutIn", "C_VehicleTurning", "D_PedestrianCrossing"):
        gg = sorted(grp[g])
        print(f"  {g:22s} n={len(gg):3d} R_long median={gg[len(gg)//2]:.3f} frac>0.8={sum(1 for x in gg if x>0.8)/len(gg):.2f}")

    ids = list(st)
    pairs = []
    for a, b in itertools.combinations(ids, 2):
        if st[a]["grp"] == st[b]["grp"] or st[a]["uid"] == st[b]["uid"] or st[a]["snap"] == st[b]["snap"]:
            continue
        pairs.append((a, b))

    def candset(field, mag_use=True):
        cs = []
        for a, b in pairs:
            cd = cos(st[a][field], st[b][field])
            if field == "p5":
                mag = 1.0
            else:
                mag = cos(st[a]["p5"] * 0 + 1, np.zeros(5)) if False else 1.0
            cs.append((a, b, cd))
        return cs

    # compute cos for each method over pairs
    res = defaultdict(list)
    for a, b in pairs:
        for key in ("s_xy", "s_x", "s_y", "p5"):
            res[key].append(cos(st[a][key], st[b][key]))
    import statistics
    names = {"s_xy": "Full", "s_x": "Longitudinal", "s_y": "Lateral", "p5": "Progress(5D)"}
    full_cos = np.array(res["s_xy"])
    for key in ("s_xy", "s_x", "s_y", "p5"):
        c = np.array(res[key])
        thr = (c >= 0.90).sum()
        print(f"\n{names[key]:16s} primary cross pairs={len(c)}  cos>=0.90 count={thr} "
              f"({thr/len(c):.1%})  median cos={statistics.median(c):.3f}")
        if key != "s_xy":
            corr = np.corrcoef(full_cos, c)[0, 1]
            print(f"    Pearson corr with Full cos = {corr:.3f}")

    # candidate sets by cos>=0.90 (Full also needs mag>=0.5 not applied here for fair geometry compare)
    def top(c_arr, n=20):
        idx = np.argsort(-c_arr)
        return idx[:n]

    def jaccard_idx(idxA, idxB):
        return len(set(idxA.tolist()) & set(idxB.tolist())) / len(set(idxA.tolist()) | set(idxB.tolist()))

    csets = {k: np.array(res[k]) for k in names}
    for key, nm in names.items():
        if key == "s_xy":
            continue
        ov20 = len(set(top(csets["s_xy"], 20).tolist()) & set(top(csets[key], 20).tolist()))
        ov50 = len(set(top(csets["s_xy"], 50).tolist()) & set(top(csets[key], 50).tolist()))
        full_gt = np.array(res["s_xy"]) >= 0.90
        oth_gt = csets[key] >= 0.90
        jac = (full_gt & oth_gt).sum() / ((full_gt | oth_gt).sum() + EPS)
        prec = (full_gt & oth_gt).sum() / (full_gt.sum() + EPS)
        print(f"{nm:16s}: FullTop20∩thisTop20={ov20}/20  Top50∩={ov50}/50  "
              f"Jaccard(>=0.90)={jac:.3f}  precision of this->Full={prec:.3f}")

    # long & progress magnitudes: how many Full-top20 appear in Progress top20/top50
    ptop20 = set(top(csets["p5"], 20).tolist()); ptop50 = set(top(csets["p5"], 50).tolist())
    ftop20 = set(top(csets["s_xy"], 20).tolist()); ftop50 = set(top(csets["s_xy"], 50).tolist())
    print("\nFull Top20 overlap with Progress Top20:", len(ftop20 & ptop20), "/20",
          " with Progress Top50:", len(ftop20 & ptop50))
    print("Full Top50 overlap with Progress Top50:", len(ftop50 & ptop50), "/50")


if __name__ == "__main__":
    main()
