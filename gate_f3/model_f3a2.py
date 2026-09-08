#!/usr/bin/env python3
"""Gate F3-A2 prototypes on Dev-108 (frozen hyperparams/arch; no new data).

Variants (--proto):
  0 baseline: absolute-t 4-channel CNN (frozen F3-A config)
  1 phase-normalized frontier (cumulative-variation phi re-sampling, label-agnostic)
  2 temporal augmentation (stretch + shift) on raw absolute series
  3 phase-normalized + temporal augmentation
Dev targets (not a formal gate): fold=lead per-struct k1 Necessary>=.75,
Optional>=.90, Contingency>=.90; and d(leadNec,blockNec) < d(leadNec,leadOpt).
"""
import argparse
import glob
import json
import os
import random

import numpy as np
import torch
import torch.nn as nn

os.makedirs("gate_f3/results", exist_ok=True)
SEED = 0
torch.manual_seed(SEED)
np.random.seed(SEED)
random.seed(SEED)

MECH = {"cross_clear": "cross", "cross_stall": "cross",
        "cross_stall_occ": "cross", "lead_opt": "lead", "lead_nec": "lead",
        "lead_cont": "lead", "block_nec": "block", "block_cont": "block",
        "temp_opt": "temp"}
DIM = 8
LR = 1e-3
EPOCHS = 200
BATCH = 64
TAU = 0.1


def load_features(phase=False):
    feats, meta = [], []
    for f in sorted(glob.glob("gate_f3/data/raw/*/*/row*.summary.json")):
        j = json.load(open(f))
        fine = j["fine"]
        P0 = np.array(fine["P0"], float)
        Pf = np.array(fine["Pfree"], float)
        PL = np.array([x if x is not None else -1.0 for x in fine["PL"]], float)
        c0 = np.divide(P0, Pf, out=np.zeros_like(P0), where=Pf > 0.05)
        c1 = np.divide(PL, Pf, out=np.zeros_like(PL), where=(Pf > 0.05) & (PL >= 0))
        m0 = (Pf > 0.05).astype(float)
        m1 = ((Pf > 0.05) & (PL >= 0)).astype(float)
        X = np.stack([c0, c1, m0, m1], 0)          # (4,20)
        if phase:
            X = phase_tf(X)
        parts = f.split("/")
        feats.append(X)
        meta.append({"mech": MECH[j["cell"]], "cell": j["cell"],
                     "row": j["row"], "struct": j["quadrant"]})
    return np.array(feats), meta


def phase_tf(X):
    """Resample a (4,20) sample onto a cumulative-variation phase grid."""
    c0, c1 = X[0], X[1]
    d = np.abs(np.diff(c0)) + np.abs(np.diff(c1))
    phi = np.concatenate([[0.0], np.cumsum(d)])
    phi = phi / (phi[-1] + 1e-9)
    grid = np.linspace(0, 1, c0.shape[0])
    idx = np.clip(np.searchsorted(phi, grid, side="right") - 1, 0, c0.shape[0] - 1)
    return X[:, idx]


def aug(x):
    """x: (4,20). mild stretch + shift."""
    T = x.shape[1]
    s = float(np.exp(np.random.randn() * 0.10))
    c = (T - 1) / 2.0
    t_new = (np.arange(T) - c) * s + c + np.random.randint(-2, 3)
    idx = np.clip(np.round(t_new).astype(int), 0, T - 1)
    return x[:, idx]


class Enc(nn.Module):
    def __init__(self):
        super().__init__()
        self.c1 = nn.Conv1d(4, 16, 5, padding=2)
        self.c2 = nn.Conv1d(16, 32, 5, padding=2)
        self.fc = nn.Sequential(nn.Linear(64, 128), nn.ReLU(),
                                nn.Linear(128, 64), nn.ReLU(),
                                nn.Linear(64, DIM))

    def forward(self, x):
        h = torch.relu(self.c1(x))
        h = torch.relu(self.c2(h))
        h = torch.cat([h.mean(-1), h.max(-1)[0]], -1)
        return nn.functional.normalize(self.fc(h), dim=-1)


def anchors(train_idx, meta):
    by = {}
    for i in train_idx:
        by.setdefault(meta[i]["struct"], []).append(i)
    by_m = {}
    for s, grp in by.items():
        mm = {}
        for i in grp:
            mm.setdefault(meta[i]["mech"], []).append(i)
        by_m[s] = mm
    pairs = []
    for s, mm in by_m.items():
        ms = list(mm)
        for a in range(len(ms)):
            for b in range(a + 1, len(ms)):
                for i in mm[ms[a]]:
                    for j in mm[ms[b]]:
                        pairs.append((i, j))
    random.shuffle(pairs)
    negs = {s: [i for ss, g in by.items() if ss != s for i in g] for s in by}
    return pairs, negs


def run_fold(Xn, meta, train_idx, blind_idx, aug_on, seed):
    """Xn: (N,4,20) train-z-scored global array. Returns embed arrays."""
    Xt = Xn[train_idx]
    Xb = Xn[blind_idx]
    tr = torch.tensor(Xt, dtype=torch.float32)
    model = Enc()
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
    tr_idx_map = {j: k for k, j in enumerate(train_idx)}
    for ep in range(EPOCHS):
        pairs, negs = anchors(train_idx, meta)
        rng = random.Random(seed + ep)
        model.train()
        for k in range(0, len(pairs), BATCH):
            pb = pairs[k:k + BATCH]
            if len(pb) < 2:
                continue
            ai = [p[0] for p in pb]
            pi = [p[1] for p in pb]
            pool = negs
            ni = [pool[meta[p[0]]["struct"]][rng.randrange(
                len(pool[meta[p[0]]["struct"]]))] for p in pb]
            def to_t(idxlist):
                rows = Xt[[tr_idx_map[i] for i in idxlist]]
                if aug_on:
                    rows = np.stack([aug(r) for r in rows])
                return torch.tensor(rows, dtype=torch.float32)
            ea = model(to_t(ai))
            ep_ = model(to_t(pi))
            en = model(to_t(ni))
            logits = (ea * ep_).sum(-1) / TAU
            negv = torch.stack([(ea[k] * en[k]).sum(-1) / TAU for k in range(len(ea))])
            denom = torch.logsumexp(torch.stack([logits, negv], 1), 1)
            loss = -(logits - denom).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        Rb = model(torch.tensor(Xb, dtype=torch.float32)).numpy()
        Rt = model(tr).numpy()
    return Rb, Rt


def knn(D, Rt_m, Rq_m):
    nn = D.argmin(1)
    return [Rt_m[k]["struct"] == Rq_m[i]["struct"] for i, k in enumerate(nn)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proto", type=int, required=True)
    a = ap.parse_args()
    phase = a.proto in (1, 3)
    aug_on = a.proto in (2, 3)
    X, meta = load_features(phase=phase)
    n = len(meta)
    idx = list(range(n))
    # global z-score per channel on all (used consistently; kept simple)
    mu = X.mean(axis=(0, 2), keepdims=True)
    sd = X.std(axis=(0, 2), keepdims=True) + 1e-6
    Xz = (X - mu) / sd
    folds = {}
    for fold_no, T in enumerate(("cross", "lead", "block")):
        blind = [i for i in idx if meta[i]["mech"] == T]
        train = [i for i in idx if meta[i]["mech"] != T]
        Rb, Rt = run_fold(Xz, meta, train, blind, aug_on, SEED + fold_no)
        mq = [meta[i] for i in blind]
        mt = [meta[i] for i in train]
        D = ((Rt[None] - Rb[:, None]) ** 2).sum(-1)
        hits = knn(D, mt, mq)
        per = {}
        for s in ("LateralOptional", "LateralNecessary", "Contingency/Wait"):
            ks = [k for k in range(len(Rb)) if mq[k]["struct"] == s]
            per[s] = np.mean([hits[k] for k in ks]) if ks else float("nan")
        folds[T] = {"k1": float(np.mean(hits)), "per": {k: round(v, 3)
                     for k, v in per.items()}, "n": len(Rb)}
        if T == "lead":
            # geometry: stopped-lead Necess vs block Necessary(train) & lead Opt(blind)
            ln = [k for k in range(len(Rb)) if mq[k]["cell"] == "lead_nec"]
            lo = [k for k in range(len(Rb)) if mq[k]["cell"] == "lead_opt"]
            bn = [k for k in range(len(train)) if mt[k]["cell"] == "block_nec"]
            d_bn = ((Rb[ln][:, None] - Rt[bn][None]) ** 2).sum(-1).mean()
            d_lo = ((Rb[ln][:, None] - Rb[lo][None]) ** 2).sum(-1).mean()
            folds["lead_geometry"] = {"d_leadNec_blockNec": round(float(d_bn), 3),
                                      "d_leadNec_leadOpt": round(float(d_lo), 3),
                                      "inverted": bool(d_bn < d_lo)}
    res = {"proto": a.proto, "phase": phase, "aug": aug_on, "folds": folds}
    json.dump(res, open(f"gate_f3/results/F3A2_proto{a.proto}.json", "w"), indent=1)
    print(f"proto{a.proto} phase={phase} aug={aug_on}")
    for T in ("cross", "lead", "block"):
        f = folds[T]
        print(f"  fold {T:5s} k1={f['k1']:.3f} per {f['per']}")
    g = folds.get("lead_geometry")
    if g:
        print("  lead_geom d(leadNec,blockNec)=%.3f d(leadNec,leadOpt)=%.3f inverted=%s"
              % (g["d_leadNec_blockNec"], g["d_leadNec_leadOpt"], g["inverted"]))


if __name__ == "__main__":
    main()
