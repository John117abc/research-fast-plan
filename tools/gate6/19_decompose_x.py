#!/usr/bin/env python3
"""Decompose what Full-x (S_x) carries beyond endpoint progress.

per state (5 blocks, T=8):
  dx_k = dW_k[:,0]                  (8,)
  S_x_raw = concat_k dx_k           (40,)
  M_x     = [||dx_k||]_k            (5,)  magnitudes / sensitivity profile
  S_shape = concat_k dx_k/||dx_k||  (40,) longitudinal temporal shape
  P5      = [dx_k[-1]]_k            (5,)  endpoint progress

Report cosine-rank reproduction of Ranking(S_x_raw) by each baseline on the
Primary cross-pair universe.
"""
import csv
import itertools
import os
import statistics
from collections import defaultdict

import numpy as np

BLOCKS = ["I1", "I2", "I3", "I4", "I5"]
EPS = 1e-12


def load():
    out = {}
    for r in csv.DictReader(open("gate6/selected_states_v3.csv")):
        if r["primary_mechanistic"] != "1":
            continue
        d = dict(np.load(os.path.join("gate6/signatures", f"{r['state_id']}.npz")))
        w0 = d["W0"]
        dx = [d[k][:, 0] - w0[:, 0] for k in BLOCKS]
        Sx = np.concatenate(dx)
        Mx = np.array([np.linalg.norm(x) for x in dx], dtype=float)
        Sh = np.concatenate([x / (np.linalg.norm(x) + EPS) for x in dx])
        P5 = np.array([x[-1] for x in dx], dtype=float)
        out[r["state_id"]] = {"Sx": Sx, "Mx": Mx, "Sh": Sh, "P5": P5,
                              "grp": r["scenario_group"], "uid": r["unique_instance_id"],
                              "snap": (r["unique_instance_id"].split("|")[0], r["frame"])}
    return out


def cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + EPS))


def main():
    st = load()
    ids = list(st)
    pairs = [(a, b) for a, b in itertools.combinations(ids, 2)
             if st[a]["grp"] != st[b]["grp"] and st[a]["uid"] != st[b]["uid"]
             and st[a]["snap"] != st[b]["snap"]]
    vals = {k: [] for k in ("Sx", "Mx", "Sh", "P5")}
    for a, b in pairs:
        for k in vals:
            vals[k].append(cos(st[a][k], st[b][k]))
    arr = {k: np.array(v) for k, v in vals.items()}
    names = {"Sx": "Full-x(raw)", "Mx": "Magnitudes(M5)", "Sh": "Shape(40d)", "P5": "EndpointProgress"}

    def top(v, n):
        return np.argsort(-v)[:n]

    print(f"Primary states={len(ids)} cross pairs={len(pairs)}")
    for k in names:
        c = arr[k]
        print(f"{names[k]:16s} median cos={statistics.median(c):.3f}  cos>=0.90={(c >= 0.90).sum()} "
              f"({(c >= 0.90).mean():.1%})")
    ref = arr["Sx"]
    print("\nReproduction of Ranking(S_x_raw):")
    for k in ("Mx", "Sh", "P5"):
        c = arr[k]
        ov20 = len(set(top(ref, 20)) & set(top(c, 20)))
        ov50 = len(set(top(ref, 50)) & set(top(c, 50)))
        corr = np.corrcoef(ref, c)[0, 1]
        # among Full candidates (>=0.9) what fraction are also this>=0.9 and vice versa
        A = ref >= 0.90
        B = c >= 0.90
        jac = (A & B).sum() / ((A | B).sum() + EPS)
        print(f"{names[k]:16s} corr={corr:.3f}  Top20∩={ov20}/20  Top50∩={ov50}/50  "
              f"Jaccard(cand>=.9)={jac:.3f}")
    # extra: does Raw Sx ≈ equal-block shape metric used in our pipeline? compare with Sh
    print("\nnote: pipeline Equal-Intervention longitudinal (our 'Longitudinal') == Shape(40d) by construction.")


if __name__ == "__main__":
    main()
