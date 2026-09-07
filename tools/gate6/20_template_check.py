#!/usr/bin/env python3
"""Gate6 6.12C: does S_shape carry structure beyond low-order temporal templates?

Per state, per intervention block k: fit dx_k(t) with
  T1: a*t            (1 param)
  T2: a*t + b*t^2    (2 params)
Report fraction of dx energy explained; then build template-based shape proxies
(normalized fitted curves, and [a,b] coefficient features) and test how well they
reproduce the Equal-Intervention candidate ranking on Primary cross pairs.
"""
import csv
import itertools
import os
import statistics
from collections import defaultdict

import numpy as np

BLOCKS = ["I1", "I2", "I3", "I4", "I5"]
EPS = 1e-9
T = np.arange(8, dtype=float)  # waypoint index 0..7
B2 = np.stack([T, T ** 2], axis=1)  # for quadratic


def load():
    st = {}
    for r in csv.DictReader(open("gate6/selected_states_v3.csv")):
        if r["primary_mechanistic"] != "1":
            continue
        d = dict(np.load(os.path.join("gate6/signatures", f"{r['state_id']}.npz")))
        w0 = d["W0"]
        dxs = [d[k][:, 0] - w0[:, 0] for k in BLOCKS]
        st[r["state_id"]] = {"dx": dxs, "grp": r["scenario_group"],
                             "uid": r["unique_instance_id"],
                             "snap": (r["unique_instance_id"].split("|")[0], r["frame"])}
    return st


def fit_energy(dx):
    """Return dict with explained fraction (1-resid/dx) for T1 and T2."""
    dx = np.asarray(dx, dtype=float)
    e = np.dot(dx, dx)
    res = {"e": e}
    if e < 1e-12:
        res["T1"], res["T2"] = 0.0, 0.0
        res["coef1"], res["coef2"] = 0.0, np.zeros(2)
        return res
    a = np.dot(T, dx) / (np.dot(T, T) + EPS)
    res["T1"] = 1.0 - np.dot(dx - a * T, dx - a * T) / e
    coef, *_ = np.linalg.lstsq(B2, dx, rcond=None)
    fit2 = B2 @ coef
    res["T2"] = 1.0 - np.dot(dx - fit2, dx - fit2) / e
    res["coef1"] = a
    res["coef2"] = coef
    return res


def cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + EPS))


def main():
    st = load()
    ids = list(st)
    pairs = [(a, b) for a, b in itertools.combinations(ids, 2)
             if st[a]["grp"] != st[b]["grp"] and st[a]["uid"] != st[b]["uid"]
             and st[a]["snap"] != st[b]["snap"]]

    # fit per state & build proxies
    exp = defaultdict(list)
    prox = {}
    for sid in ids:
        dxs = st[sid]["dx"]
        fs = [fit_energy(x) for x in dxs]
        for k, f in enumerate(fs):
            exp[k].append(f["T1"])
        # shape proxies: normalized fitted curve per block
        shp = []
        c1, c2 = [], []
        for k, f in enumerate(fs):
            if f["e"] < 1e-12:
                shp.append(np.zeros(8))
            else:
                t1 = f["coef1"] * T
                shp.append(t1 / (np.linalg.norm(t1) + EPS))
            c1.append(f["coef1"])
            c2.append(f["coef2"])
        prox[sid] = {"t1": np.concatenate(shp),
                     "c1": np.array(c1), "c2": np.concatenate(c2)}

    # explained-energy summary (T1/T2 over all blocks & states, primary)
    t1e = [v for vs in exp.values() for v in vs]
    print(f"primary states={len(ids)}  blocks_total={len(t1e)}")
    print("explained fraction  linear(a*t): median=%.3f  frac>=0.9=%.2f  frac>=0.8=%.2f" % (
        statistics.median(t1e), sum(1 for x in t1e if x >= 0.9) / len(t1e),
        sum(1 for x in t1e if x >= 0.8) / len(t1e)))
    # quadratic explained
    t2e = []
    for sid in ids:
        for f in [fit_energy(x) for x in st[sid]["dx"]]:
            t2e.append(f["T2"])
    print("explained fraction  quad(a*t+b*t^2): median=%.3f  frac>=0.9=%.2f" % (
        statistics.median(t2e), sum(1 for x in t2e if x >= 0.9) / len(t2e)))

    # ranking reproduction
    def scores(metric):
        return np.array([cos(prox[a][metric], prox[b][metric]) for a, b in pairs])

    ref_scores = scores("t1")  # S_shape == template-fit-normalized per block? not identical; compare S_shape ref separately
    # actual S_shape
    shape_scores = []
    for a, b in pairs:
        def sshape(sid):
            x = st[sid]["dx"]
            return np.concatenate([x[i] / (np.linalg.norm(x[i]) + EPS) for i in range(5)])
        shape_scores.append(cos(sshape(a), sshape(b)))
    shape_scores = np.array(shape_scores)

    # Equal-Intervention candidate pair set (our production)
    eq = set()
    for c in csv.DictReader(open("gate6/pair_cross_primary_confounds.csv")):
        eq.add(tuple(sorted((c["state_A"], c["state_B"]))))
    pair_keys = [tuple(sorted((a, b))) for a, b in pairs]

    def top(v, n):
        return np.argsort(-v)[:n]

    print("\nreproduction vs S_shape ranking:")
    for metric in ("t1", "c1", "c2"):
        s = scores(metric)
        ov20 = len(set(top(shape_scores, 20)) & set(top(s, 20)))
        ov50 = len(set(top(shape_scores, 50)) & set(top(s, 50)))
        corr = np.corrcoef(shape_scores, s)[0, 1]
        A = shape_scores >= 0.90; B = s >= 0.90
        jac = (A & B).sum() / ((A | B).sum() + EPS)
        print(f"{metric:6s}: corr={corr:.3f} Top20∩={ov20}/20 Top50∩={ov50}/50 Jaccard(shape>=.9)={jac:.3f}")

    print("\nreproduction vs Equal-Intervention candidates (68):")
    for metric in ("t1", "c1", "c2"):
        s = scores(metric)
        cand = {k for k, v in zip(pair_keys, s) if v >= 0.90}
        jac = len(eq & cand) / (len(eq | cand) + EPS)
        prec = len(eq & cand) / (len(cand) + EPS)
        print(f"{metric:6s}: candidate>=.9={len(cand):4d} Jaccard_vs_EQ={jac:.3f} "
              f"frac_of_EQ_found={len(eq & cand)}/{len(eq)}")


if __name__ == "__main__":
    main()
