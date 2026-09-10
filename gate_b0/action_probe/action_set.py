"""Gate B0 action set: the raw longitudinal primitives x lateral intent."""
import common

CFG = common.cfg()
ACTIONS = CFG["action"]["set"]
ACTION_IDS = [a["id"] for a in ACTIONS]
ACTION_BY_ID = {a["id"]: a for a in ACTIONS}
FORCED_STEPS = int(round(CFG["action"]["forced_s"] / CFG["data"]["dt"]))


def accel_set():
    return tuple(CFG["engine"]["accel"])
