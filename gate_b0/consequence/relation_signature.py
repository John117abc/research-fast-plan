"""Gate B0 relation signature helpers (R0 = 8 x {M,V})."""
from action_probe.action_set import ACTION_IDS


def mv_vectors(sig):
    return list(sig["M"]), list(sig["V"])


def signature_row(state, sig):
    row = {"state_id": state["state_id"], "coarse_mechanism": state["coarse_mechanism"],
           "fine_mechanism": state["fine_mechanism"],
           "param_group_id": state["param_group_id"]}
    for i, aid in enumerate(ACTION_IDS):
        row["M_%s" % aid] = int(sig["M"][i])
        row["V_%s" % aid] = round(float(sig["V"][i]), 4)
    row["datarow_valid"] = 1
    row["health_reason"] = ""
    return row
