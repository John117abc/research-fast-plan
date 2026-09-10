"""Gate B0 successor state T(X,u) and its relation signature R0(T(X,u))."""
import common  # noqa: E402
from action_probe.action_set import FORCED_STEPS  # noqa: E402
from action_probe import constrained_rollout as cr  # noqa: E402
from consequence import action_consequence as ac  # noqa: E402


def successor_context(entry, slots_abs, ego_abs_s):
    """Rebase occupancy at t0+1s and return (v,m,tau,slots_win,ego_abs_s')."""
    if entry.get("successor") is None:
        return None
    s, v, m, tau = entry["successor"]
    win = slots_abs[FORCED_STEPS: FORCED_STEPS + cr.N + 1]
    return float(v), int(m), float(tau), win, ego_abs_s + s


def successor_signature(entry, slots_abs, ego_abs_s, occupancy=True):
    ctx = successor_context(entry, slots_abs, ego_abs_s)
    if ctx is None:
        return None
    v, m, tau, win, e = ctx
    return ac.compute_signature(v, m, tau, win, e, occupancy=occupancy)
