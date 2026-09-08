#!/usr/bin/env python3
"""Gate F3-A one-time run: mechanism-isolated supervised contrastive embedding.

FROZEN config (protocol section 9). Three folds (test mechanism cross/lead/
block) are trained and evaluated ONCE in a single sweep; no per-fold tuning.
Gates (section 5): G1 k1 floors overall>=.80, Necess>=.70, Optional>=.89,
Cont>=.95; G2 cross-mech-same distance < cross-mech-diff distance on Blind.
"""
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

T = [0.5 * (k + 1) for k in range(20)]
MECH = {"cross_clear": "cross", "cross_stall": "cross",
        "cross_stall_occ": "cross", "lead_opt": "lead", "lead_nec": "lead",
        "lead_cont": "lead", "block_nec": "block", "block_cont": "block",
        "temp_opt": "temp"}
DIM = 8
LR = 1e-3
EPOCHS = 200
BATCH = 64
TAU = 0.1
CONV = [(4, 16, 5), (16, 32, 5)]


def load_features():
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
        X = np.stack([c0, c1, m0, m1], 1)           # (20,4)
        parts = f.split("/")
        feats.append(X)
        meta.append({"mech": MECH[j["cell"]], "cell": j["cell"],
                     "row": j["row"], "struct": j["quadrant"]})
    return np.array(feats), meta


class Enc(nn.Module):
    def __init__(self):
        super().__init__()
        self.c1 = nn.Conv1d(4, 16, 5, padding=2)
        self.c2 = nn.Conv1d(16, 32, 5, padding=2)
        self.fc = nn.Sequential(nn.Linear(64, 128), nn.ReLU(),
                                nn.Linear(128, 64), nn.ReLU(),
                                nn.Linear(64, DIM))

    def forward(self, x):                       # x: (B,4,20)
        h = torch.relu(self.c1(x))
        h = torch.relu(self.c2(h))
        h = torch.cat([h.mean(-1), h.max(-1)[0]], -1)   # (B,64)
        r = self.fc(h)
        return nn.functional.normalize(r, dim=-1)


def make_batches(train_idx, Xall, meta, seed=0):
    rng = random.Random(seed)
    by = {}
    for i in train_idx:
        s = meta[i]["struct"]
        by.setdefault(s, []).append(i)
    # positive anchors: pairs across mechanisms within same structure
    anchors = []
    for s, grp in by.items():
        by_m = {}
        for i in grp:
            by_m.setdefault(meta[i]["mech"], []).append(i)
        ms = list(by_m)
        for a in range(len(ms)):
            for b in range(a + 1, len(ms)):
                for i in by_m[ms[a]]:
                    for j in by_m[ms[b]]:
                        anchors.append((i, j))
    rng.shuffle(anchors)
    negs = {}
    for s, grp in by.items():
        others = [i for ss, g in by.items() if ss != s for i in g]
        negs[s] = others
    batches = []
    for k in range(0, len(anchors), BATCH):
        batches.append(anchors[k:k + BATCH])
    return batches, negs


def run_fold(model, X, meta, train_idx, blind_idx, seed):
    Xt = torch.tensor(X[train_idx].transpose(0, 2, 1), dtype=torch.float32)
    Xb = torch.tensor(X[blind_idx].transpose(0, 2, 1), dtype=torch.float32)
    # train-only z-score (frozen transform)
    mu = Xt.mean(dim=(0, 2), keepdim=True)
    sd = Xt.std(dim=(0, 2), keepdim=True) + 1e-6
    Xt = (Xt - mu) / sd
    Xb = (Xb - mu) / sd
    model = Enc()
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
    for ep in range(EPOCHS):
        batches, negs = make_batches(train_idx, None, meta, seed + ep)
        model.train()
        tot = 0.0
        for pair_b in batches:
            if len(pair_b) < 2:
                continue
            ai = [p[0] for p in pair_b]
            pi = [p[1] for p in pair_b]
            neg_choice = []
            for p in pair_b:
                s = meta[p[0]]["struct"]
                pool = negs[s]
                neg_choice.append(pool[random.Random(seed + ep + p[0]).randrange(len(pool))])
            a_idx = [train_idx.index(i) for i in ai]
            p_idx = [train_idx.index(i) for i in pi]
            n_idx = [train_idx.index(i) for i in neg_choice]
            ea = model(Xt[a_idx])
            ep_ = model(Xt[p_idx])
            en = model(Xt[n_idx])
            logits = (ea * ep_).sum(-1) / TAU                      # (B,)
            neg_all = torch.stack([(ea[k] * en[k]).sum(-1) / TAU for k in range(len(ea))])
            denom = torch.logsumexp(torch.stack([logits, neg_all], 1), 1)
            loss = -(logits - denom).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += loss.item()
    model.eval()
    with torch.no_grad():
        Rb = model(Xb)
        Rt = model(Xt)
    return Rb.numpy(), Rt.numpy(), train_idx


def knn_gate(Rb, Rq_meta, Rt, Rt_meta):
    # each blind sample's nearest train neighbor; pool excludes its mech already
    D = ((Rt[None] - Rb[:, None]) ** 2).sum(-1)      # (nB,nTr)
    k1 = D.argmin(1)
    hits = [Rt_meta[int(k1[i])]["struct"] == Rq_meta[i]["struct"] for i in range(len(Rb))]
    return np.mean(hits), hits


def main():
    X, meta = load_features()
    print("features", X.shape)
    n = len(meta)
    idx = list(range(n))
    folds = {}
    all_hits = []
    all_struct = []
    pair_same, pair_diff = [], []
    for fold_no, T in enumerate(("cross", "lead", "block")):
        blind = [i for i in idx if meta[i]["mech"] == T]
        train = [i for i in idx if meta[i]["mech"] != T]
        Rb, Rt, tr = run_fold(None, X, meta, train, blind, SEED + fold_no)
        mq = [meta[i] for i in blind]
        mt = [meta[i] for i in train]
        hr, hits = knn_gate(Rb, mq, Rt, mt)
        # cross-mech same/diff distance to train neighbors
        D = ((Rt[None] - Rb[:, None]) ** 2).sum(-1)
        sd_same, sd_diff = [], []
        for i in range(len(Rb)):
            qs = mq[i]["struct"]
            same = [k for k in range(len(mt)) if mt[k]["struct"] == qs]
            diff = [k for k in range(len(mt)) if mt[k]["struct"] != qs]
            if same:
                sd_same.append(D[i][same].min())
            if diff:
                sd_diff.append(D[i][diff].min())
        pair_same.extend(sd_same)
        pair_diff.extend(sd_diff)
        all_hits.extend(hits)
        all_struct.extend([mq[i]["struct"] for i in range(len(Rb))])
        folds[T] = {"n_blind": len(Rb), "k1": float(hr)}
        print(f"fold test={T}: blind k1 = {hr:.3f}")
    overall = np.mean(all_hits)
    per = {}
    for s in ("LateralOptional", "LateralNecessary", "Contingency/Wait"):
        idxs = [k for k in range(len(all_hits)) if all_struct[k] == s]
        per[s] = np.mean([all_hits[k] for k in idxs]) if idxs else float("nan")
    g2 = bool(np.mean(pair_same) < np.mean(pair_diff))
    res = {"folds": folds, "k1_overall": float(overall), "k1_per_struct": per,
           "g2_cross_mech_dist": {"same": float(np.mean(pair_same)),
                                  "diff": float(np.mean(pair_diff)),
                                  "holds": g2}}
    json.dump(res, open("gate_f3/results/F3A_result.json", "w"), indent=1)
    print("G1 overall k1 =", round(overall, 3), "per-struct",
          {k: round(v, 3) for k, v in per.items()})
    print("G2 mean dist cross-mech same %.3f vs diff %.3f holds=%s"
          % (np.mean(pair_same), np.mean(pair_diff), g2))


if __name__ == "__main__":
    main()
