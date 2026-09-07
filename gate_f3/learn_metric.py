#!/usr/bin/env python3
"""Gate F3 - low-rank linear metric learning to merge mechanism variants of
the same future structure. Frozen Z (40-dim, z-scored) + labels from F2.
Evaluation = F2 gates under leave-one-literal-scene-out CV.
"""
import glob
import json
import os

import numpy as np

os.makedirs("gate_f3/results", exist_ok=True)

R = 6          # rank of A
LR = 0.05
L2 = 1e-3
ITERS = 2000
SEED = 0
rng = np.random.RandomState(SEED)

pts = []
for f in sorted(glob.glob("gate_f1/results/*/run*.summary.json")):
    j = json.load(open(f))
    fine = j["fine"]
    P0 = np.array(fine["P0"], float)
    Pf = np.array(fine["Pfree"], float)
    PL = np.array([x if x is not None else 0.0 for x in fine["PL"]], float)
    n0 = np.divide(P0, Pf, out=np.zeros_like(P0), where=Pf > 0)
    nL = np.divide(PL, Pf, out=np.zeros_like(PL), where=Pf > 0)
    pts.append({"scene": j["scene"], "struct": j["quadrant"], "Z": np.concatenate([n0, nL])})

n = len(pts)
Z = np.stack([p["Z"] for p in pts])
mu, sd = Z.mean(0), Z.std(0) + 1e-9
Z = (Z - mu) / sd
MECH = {"A1": "cross", "A2": "cross", "B1": "blocked", "B2": "blocked",
        "C1": "lead", "C2": "lead", "D1": "blocked", "D2": "blocked",
        "G1": "lead", "G2": "lead", "G3": "temp"}
mech = [MECH[p["scene"]] for p in pts]
struct = [p["struct"] for p in pts]
scene = [p["scene"] for p in pts]
STRUCTS = sorted(set(struct))
print(f"n={n} structs={struct.__len__()} prior=",
      {s: round(struct.count(s) / n, 3) for s in STRUCTS})


def md(M):
    dif = Z[:, None, :] - Z[None, :, :]
    return np.einsum('ija,ab,ijb->ij', dif, M, dif)


def triplets(exclude_scene=None):
    """pos: i,j diff mech same struct; neg: i,j same mech diff struct;
    exclude any pair touching exclude_scene."""
    pos, neg = [], []
    for i in range(n):
        for j in range(i + 1, n):
            if exclude_scene and (scene[i] == exclude_scene or scene[j] == exclude_scene):
                continue
            if mech[i] != mech[j] and struct[i] == struct[j]:
                pos.append((i, j))
            elif mech[i] == mech[j] and struct[i] != struct[j]:
                neg.append((i, j))
    return pos, neg


def fit_metric(exclude_scene=None):
    # anchor triplets: (a, p, n) with mech(a)!=mech(p), struct equal,
    # and mech(a)==mech(n), struct(a)!=struct(n); pairs touching exclude_scene
    # are dropped.
    trips = []
    for a in range(n):
        if exclude_scene and scene[a] == exclude_scene:
            continue
        pos = [(i, j) for i, j in ((a, j) for j in range(n))
               if i != j and mech[i] != mech[j] and struct[i] == struct[j]]
        neg = [(i, j) for i, j in ((a, j) for j in range(n))
               if i != j and mech[i] == mech[j] and struct[i] != struct[j]]
        for (_, p) in pos:
            for (_, nn) in neg:
                trips.append((a, p, nn))
    A = rng.randn(40, R) * 0.2
    if not trips:
        return A
    T = np.array(trips, int)
    # stratify anchors by struct so rare classes drive the fit
    by_s = {s: [] for s in STRUCTS}
    for t in T:
        by_s[struct[t[0]]].append(t)
    pools = {s: np.array(x) if x else np.zeros((0, 3), int) for s, x in by_s.items()}
    avail = [s for s in STRUCTS if len(pools[s]) > 0]
    v = np.zeros_like(A)
    B = 128
    for it in range(ITERS):
        sel = []
        for _ in range(B):
            s = avail[rng.randint(len(avail))]
            k = rng.randint(len(pools[s]))
            sel.append(pools[s][k])
        sel = np.array(sel)
        a = sel[:, 0]; p = sel[:, 1]; nn = sel[:, 2]
        dap = ((Z[a] - Z[p]) ** 2).sum(1)  # feature squared diffs (B,)
        dan = ((Z[a] - Z[nn]) ** 2).sum(1)
        Gp = (Z[a] - Z[p])
        Gn = (Z[a] - Z[nn])
        hinge = dap - dan + 1.0
        act = hinge > 0
        g = np.zeros_like(A)
        if act.any():
            Gpa = (Z[a[act]] - Z[p[act]])
            Gna = (Z[a[act]] - Z[nn[act]])
            M = Gpa.T @ Gpa - Gna.T @ Gna
            g = 2.0 * M @ A
        g /= B
        g += L2 * A
        v = 0.9 * v + 0.1 * g * g
        A -= LR * g / (np.sqrt(v) + 1e-8)
        fn = np.linalg.norm(A)
        if fn > 0:
            A *= np.sqrt(40) / fn
    return A


def eval_gates(A_fit, test_scene=None):
    """Report gate numbers with M = A^T A over the FULL set (for CV we report
    the test-scene query hit against other scenes; global stats printed too)."""
    if A_fit is None:
        A_fit = np.zeros((40, R))
        M = np.eye(40)
    else:
        M = A_fit @ A_fit.T
    D = md(M)
    out = {}
    for def_mech in (False, True):
        same_f, diff_s = [], []
        for i in range(n):
            for j in range(i + 1, n):
                ffi, ffj = (mech[i], mech[j]) if def_mech else (scene[i], scene[j])
                si, sj = struct[i], struct[j]
                if ffi != ffj and si == sj:
                    same_f.append(D[i, j])
                elif ffi == ffj and si != sj:
                    diff_s.append(D[i, j])
        out["mech" if def_mech else "scene"] = {
            "d_same": float(np.mean(same_f)), "d_diff": float(np.mean(diff_s)),
            "holds": bool(np.mean(same_f) < np.mean(diff_s))}
    # leave-mechanism-out kNN structure hit (all points), per struct
    hits, tot = 0, 0
    per = {}
    for i in range(n):
        cand = [j for j in range(n) if mech[j] != mech[i]]
        cand.sort(key=lambda j: D[i, j])
        qs = struct[i]
        for j in cand[:1]:
            hits += struct[j] == qs
            tot += 1
            per.setdefault(qs, [0, 0])
            per[qs][0] += struct[j] == qs
            per[qs][1] += 1
    out["lmo_k1"] = hits / tot
    out["lmo_per"] = {k: round(v[0] / v[1], 3) for k, v in per.items()}
    return out, D


def main():
    baseline, D_e = eval_gates(None)
    print("Euclidean baseline:", {k: v for k, v in baseline.items()})
    # leave-one-literal-scene-out CV: metric trained without pairs touching the
    # test scene; measure that scene's leave-mechanism structure hit vs others.
    fold_hit = {}
    fold_ok = {"scene": [], "mech": []}
    for ts in sorted(set(scene)):
        A = fit_metric(exclude_scene=ts)
        M = A @ A.T
        D = md(M)
        qs = [i for i in range(n) if scene[i] == ts]
        h = 0
        for i in qs:
            cand = [j for j in range(n) if mech[j] != mech[i] and scene[j] != ts]
            cand.sort(key=lambda j: D[i, j])
            h += cand and struct[cand[0]] == struct[i]
        fold_hit[ts] = round(h / len(qs), 2) if qs else None
        st, df = [], []
        for i in range(n):
            for j in range(i + 1, n):
                if scene[i] == ts or scene[j] == ts:
                    continue
                if scene[i] != scene[j] and struct[i] == struct[j]:
                    st.append(D[i, j])
                elif mech[i] == mech[j] and struct[i] != struct[j]:
                    df.append(D[i, j])
        fold_ok["scene"].append(float(np.mean(st)) < float(np.mean(df)))
        fold_ok["mech"].append(float(np.mean(st)) < float(np.mean(df)))
    print("CV per-fold leave-mech k1 hit:", fold_hit)
    ok_mean = np.mean(fold_ok["mech"])
    print("CV gate-1 (scene-diff-same-struct < same-mech-diff-struct) folds:",
          np.mean(fold_ok["mech"]), " fraction of folds holding")
    # final global-fit metric for reporting/figures
    A_final = fit_metric()
    np.save("gate_f3/results/A.npy", A_final)
    out, Df = eval_gates(A_final)
    print("Learned global metric:", {k: v for k, v in out.items()})
    json.dump({"baseline_euclid": baseline, "learned_global": out,
               "cv_fold_hit": fold_hit, "cv_gate1_frac": ok_mean},
              open("gate_f3/results/metric_results.json", "w"), indent=1)
    print("wrote metric_results.json")


if __name__ == "__main__":
    main()
