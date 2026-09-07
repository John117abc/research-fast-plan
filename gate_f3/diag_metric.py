#!/usr/bin/env python3
"""Gate F3-alt: gentle diagonal feature metric w=exp(b), b fit by L-BFGS on
log-ratio of cross-mech same-struct vs same-mech diff-struct distances, L2
keeps it near Euclidean. Evaluation with the F2 gates (quadratic form)."""
import glob
import json
import os

import numpy as np
from scipy.optimize import minimize

os.makedirs("gate_f3/results", exist_ok=True)
rng = np.random.RandomState(0)

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

sq = ((Z[:, None, :] - Z[None, :, :]) ** 2)   # (n,n,40) feature diffs squared

pos, neg = [], []
for i in range(n):
    for j in range(i + 1, n):
        if mech[i] != mech[j] and struct[i] == struct[j]:
            pos.append((i, j))
        elif mech[i] == mech[j] and struct[i] != struct[j]:
            neg.append((i, j))
pos = np.array(pos)
neg = np.array(neg)
Xp = sq[pos[:, 0], pos[:, 1]]            # |pos| x 40
Xn = sq[neg[:, 0], neg[:, 1]]
LAM = 2e-3
w_prior = np.ones(40)


def fobj(b):
    w = np.exp(b)
    mp = (Xp @ w).mean()
    mn = (Xn @ w).mean()
    return np.log(mp / max(mn, 1e-12)) + LAM * np.mean((np.exp(b) - w_prior) ** 2)


def gobj(b):
    w = np.exp(b)
    mp = (Xp @ w).mean()
    mn = (Xn @ w).mean()
    grad = np.exp(b) * ((Xp.mean(0) / mp) - (Xn.mean(0) / mn))
    grad += 2 * LAM * np.exp(b) * (np.exp(b) - w_prior)
    return grad


res = minimize(fobj, np.zeros(40), jac=gobj, method="L-BFGS-B")
w = np.exp(res.x)
print("opt converged:", res.success, "loss", round(res.fun, 3))


def gates(w):
    M = np.diag(w)
    dif = Z[:, None, :] - Z[None, :, :]
    D = np.einsum('ija,ab,ijb->ij', dif, M, dif)
    same_f, diff_s = [], []
    for i in range(n):
        for j in range(i + 1, n):
            if mech[i] != mech[j] and struct[i] == struct[j]:
                same_f.append(D[i, j])
            elif mech[i] == mech[j] and struct[i] != struct[j]:
                diff_s.append(D[i, j])
    hits, tot = 0, 0
    per = {}
    for i in range(n):
        cand = [j for j in range(n) if mech[j] != mech[i]]
        cand.sort(key=lambda j: D[i, j])
        qs = struct[i]
        hits += struct[cand[0]] == qs
        tot += 1
        per.setdefault(qs, [0, 0])
        per[qs][0] += struct[cand[0]] == qs
        per[qs][1] += 1
    return {"d_same_mech_cross": float(np.mean(same_f)),
            "d_diff_same_mech": float(np.mean(diff_s)),
            "gate1_holds": bool(np.mean(same_f) < np.mean(diff_s)),
            "lmo_k1": hits / tot,
            "lmo_per": {k: round(v[0] / v[1], 3) for k, v in per.items()}}


base = gates(np.ones(40))
learned = gates(w)
print("Euclidean :", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in base.items()})
print("Diagonal  :", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in learned.items()})
np.save("gate_f3/results/diag_w.npy", w)
json.dump({"euclid": base, "diag": learned,
           "w_range": [float(w.min()), float(w.max())]},
          open("gate_f3/results/diag_results.json", "w"), indent=1)
print("saved diag_results.json")
