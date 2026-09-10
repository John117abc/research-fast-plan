"""Gate B0 relation distance on R0 signatures."""
from action_probe.action_set import ACTION_IDS


def delta(mi, vi, mj, vj):
    if mi == 0 and mj == 0:
        return 0.0
    if mi != mj:
        return 1.0
    return abs(float(vi) - float(vj))


def action_deltas(sig_i, sig_j):
    out = []
    for k in range(len(ACTION_IDS)):
        out.append(delta(sig_i["M"][k], sig_i["V"][k],
                         sig_j["M"][k], sig_j["V"][k]))
    return out


def d_mean(sig_i, sig_j):
    ds = action_deltas(sig_i, sig_j)
    return sum(ds) / len(ds)


def d_max(sig_i, sig_j):
    return max(action_deltas(sig_i, sig_j))
