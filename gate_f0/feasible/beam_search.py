"""Gate F0 beam search over longitudinal accel primitives along one corridor.

States: (s, v). Feasibility is provided by a callable `feasible(state) -> bool`
(road validity + collision already encoded by caller). Waiting / low-speed states
are preserved through speed-bucket pruning.
"""
from .longitudinal_primitives import EgoState, step_accel


def beam_forward(init_s, init_v, accel_set, dt, n_steps, feasible,
                 v_max, width=100, buckets=(0, 2, 5, 8, 12, 1e9),
                 keep_per_bucket=20):
    """Return list[list[EgoState]]: frontier states after each step."""
    states = [EgoState(init_s, init_v)]
    if not feasible(states[0]):
        return [[] for _ in range(n_steps)]
    layers = []
    for _ in range(n_steps):
        expanded = []
        for st in states:
            for a in accel_set:
                ns = step_accel(st, a, dt, v_max)
                if feasible(ns):
                    expanded.append(ns)
        # speed-bucket pruning (preserve waiting/cruise/aggressive)
        kept = []
        buckets_b = list(buckets)
        for i in range(len(buckets_b) - 1):
            lo, hi = buckets_b[i], buckets_b[i + 1]
            cand = [s for s in expanded if lo <= s.v < hi]
            cand.sort(key=lambda s: -s.s)
            kept.extend(cand[:keep_per_bucket])
        # global width top-by-s fallback if fewer than width
        if len(kept) < width:
            extra = sorted(expanded, key=lambda s: -s.s)[: width - len(kept)]
            kept.extend(extra)
        # dedup coarse (same rounded s,v)
        seen = set()
        uniq = []
        for s in kept:
            k = (round(s.s, 2), round(s.v, 2))
            if k not in seen:
                seen.add(k)
                uniq.append(s)
        states = uniq
        layers.append([s.copy() for s in states])
    return layers


def max_progress(layers, horizons_steps):
    """Return P(H) for each horizon (max s at that step layer)."""
    out = []
    for hsteps in horizons_steps:
        if hsteps - 1 < len(layers) and layers[hsteps - 1]:
            out.append(max(s.s for s in layers[hsteps - 1]))
        else:
            out.append(None)
    return out
