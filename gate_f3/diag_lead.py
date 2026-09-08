#!/usr/bin/env python3
"""F3-A lead-fold diagnostics (no model/gate change): confusion, distance to
structure boundary, Necessary formation transients, embedding geometry.
"""
import glob
import json
import os

import numpy as np

import model_f3a as M  # noqa:  (reuses frozen load/features/Enc/run_fold)

os.makedirs("gate_f3/results", exist_ok=True)
EPS = 0.1


def gvals(cell_row):
    p = f"gate_f3/data/raw/*/*/row{cell_row[1]}.summary.json"
    return None  # replaced below


def main():
    X, meta = M.load_features()
    idx = list(range(len(meta)))
    T = "lead"
    blind = [i for i in idx if meta[i]["mech"] == T]
    train = [i for i in idx if meta[i]["mech"] != T]
    Rb, Rt, _ = M.run_fold(None, X, meta, train, blind, 1)
    mq = [meta[i] for i in blind]
    mt = [meta[i] for i in train]
    D = ((Rt[None] - Rb[:, None]) ** 2).sum(-1)          # (36,72)
    nn = D.argmin(1)
    pred = [mt[k]["struct"] for k in nn]
    true = [mq[k]["struct"] for k in range(len(Rb))]
    structs = ["LateralOptional", "LateralNecessary", "Contingency/Wait"]
    print("=== 1) lead-fold confusion (rows=true, cols=pred NN-in-train) ===")
    print("         Opt   Nec   Cont")
    C = np.zeros((3, 3), int)
    for k in range(len(Rb)):
        C[structs.index(true[k]), structs.index(pred[k])] += 1
    for i, s in enumerate(structs):
        print(f"{s[:7]:7s} {C[i,0]:5d} {C[i,1]:5d} {C[i,2]:5d}   "
              f"(n_true={int(C[i].sum())})")

    # ---- 2) distance to structure boundary: |G0-eps|, |GL-eps| ----
    labels = {}
    for f in sorted(glob.glob("gate_f3/data/raw/*/*/row*.summary.json")):
        j = json.load(open(f))
        labels[(j["cell"], j["row"])] = (j["quadrant"], j["G0"], j["GL"])
    rows = []
    for k in range(len(Rb)):
        cell_row = (meta[blind[k]]["cell"], meta[blind[k]]["row"])
        _, g0, gl = labels[cell_row]
        rows.append({"i": k, "true": true[k], "pred": pred[k],
                     "ok": true[k] == pred[k], "g0": g0,
                     "gl": gl if gl is not None else -1.0})
    print("\n=== 2) boundary distance (correct vs error; eps=0.1) ===")
    for s in structs:
        ok = [r for r in rows if r["true"] == s and r["ok"]]
        err = [r for r in rows if r["true"] == s and not r["ok"]]
        if not err:
            continue
        def dg0(x): return abs(x["g0"] - EPS)
        def dgl(x): return abs(x["gl"] - EPS)
        print(f" {s[:7]:7s} correct n={len(ok)} mean|G0-eps|={np.mean([dg0(r) for r in ok]):.2f} "
              f"mean|GL-eps|={np.mean([dgl(r) for r in ok]):.2f} | "
              f"error n={len(err)} mean|G0-eps|={np.mean([dg0(r) for r in err]):.2f} "
              f"mean|GL-eps|={np.mean([dgl(r) for r in err]):.2f}")
        for r in err:
            print(f"    err {s[:7]}->{r['pred'][:9]:9s} G0={r['g0']:.2f} GL={r['gl']:.2f}")

    # ---- 3) Necessary formation: P0/Pfree curves block_nec vs lead_nec ----
    print("\n=== 3) Necessary formation transients (mean P0/Pfree by t) ===")
    curve = {}
    for f in sorted(glob.glob("gate_f3/data/raw/*/*/row*.summary.json")):
        j = json.load(open(f))
        fine = j["fine"]
        P0 = np.array(fine["P0"])
        Pf = np.array(fine["Pfree"])
        c0 = np.divide(P0, Pf, out=np.zeros_like(P0), where=Pf > 0.05)
        curve.setdefault(j["cell"], []).append(c0)
    for cell in ("block_nec", "lead_nec", "cross_stall"):
        a = np.array(curve[cell])
        m, s = a.mean(0), a.std(0)
        print(f" {cell:11s} mean_c0(t): " +
              " ".join(f"{x:.1f}" for x in m[::2]))

    # ---- 4) embedding geometry for Necessary sources ----
    print("\n=== 4) embedding: is stopped-lead Necess nearer other lead or other Necess? ===")
    # group indices within Rb (lead blind) by structure, and in Rt by cell
    def group_rt(cellname):
        return [k for k in range(len(train)) if mt[k]["cell"] == cellname]
    gi = {"lead_opt": [], "lead_nec": [], "lead_cont": []}
    for k in range(len(Rb)):
        gi[mq[k]["cell"]].append(k)
    b_nec = group_rt("block_nec")
    targets = {"lead_opt(blind)": gi["lead_opt"], "lead_cont(blind)": gi["lead_cont"],
               "block_nec(train)": b_nec, "cross_stall(train)":
                   [k for k in range(len(train)) if mt[k]["cell"] == "cross_stall"]}
    for cellq, qidx in (("lead_nec", gi["lead_nec"]),):
        print(f" query {cellq} n={len(qidx)}: mean embed-dist to ...")
        for name, tidx in targets.items():
            if not tidx:
                continue
            arr_b = Rb[tidx] if max(tidx) < len(Rb) else None
            if name.endswith("(blind)"):
                d = ((Rb[qidx][:, None] - Rb[tidx][None]) ** 2).sum(-1)
            else:
                d = ((Rb[qidx][:, None] - Rt[tidx][None]) ** 2).sum(-1)
            print(f"   -> {name:18s} {d.mean():.3f}")
    np.save("gate_f3/results/leadfold_Rb.npy", Rb)
    np.save("gate_f3/results/leadfold_Rt.npy", Rt)
    json.dump({"blind_cell_row": [meta[blind[k]]["cell"] + "_" + str(meta[blind[k]]["row"])
                                   for k in range(len(Rb))],
               "train_cell_row": [meta[train[k]]["cell"] + "_" + str(meta[train[k]]["row"])
                                  for k in range(len(Rt))]},
              open("gate_f3/results/leadfold_ids.json", "w"))


if __name__ == "__main__":
    main()
