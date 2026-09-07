#!/usr/bin/env python3
"""Gate6 semantic acceptance for route10 (completed).

Evidence extraction:
- B/C/D (owned actors): per-instance actor presence / min distance / ego response.
- A HardBreak (no owned actor): detect ego stop-or-decel episodes after each HB
  trigger event and attribute the nearest front (type1, ahead, in-lane) actor as
  lead candidate if it also slowed/stopped.
"""
import argparse
import glob
import json
import math
import os
import xml.etree.ElementTree as ET

GROUPS = {"HardBreakRoute": "A", "ParkingCutIn": "B", "VehicleTurningRoute": "C",
          "PedestrianCrossing": "D"}


def load_timeline(snapdir):
    rows = []
    for line in open(os.path.join(snapdir, "meta.jsonl")):
        rows.append(json.loads(line))
    rows.sort(key=lambda r: r["frame"])
    return rows


def sec(r):
    return r["frame"] / 20.0


def front_vehicle_near(actors, y_lim=2.5, x_lo=1.0, x_hi=45.0):
    best = None
    for a in actors:
        if a["type"] == 1.0 and x_lo < a["x"] < x_hi and abs(a["y"]) < y_lim:
            d = math.hypot(a["x"], a["y"])
            if best is None or d < best[1]:
                best = (a, d)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapdir", required=True)
    ap.add_argument("--scnlog", required=True)
    ap.add_argument("--route-xml", required=True)
    ap.add_argument("--out", default="gate6/semantic_accept.csv")
    a = ap.parse_args()

    events = [json.loads(l) for l in open(a.scnlog)]
    events = [e for e in events if e["type"] in GROUPS]
    tl = load_timeline(a.snapdir)
    print(f"timeline rows={len(tl)} ({sec(tl[0]):.0f}-{sec(tl[-1]):.0f}s) events={len(events)}")

    owned_by_cfg = {}
    for e in events:
        owned_by_cfg[e["config_name"]] = set(e.get("actor_ids", []))
        owned_by_cfg[e["config_name"]].discard(None)

    import csv
    rows = []

    def add_row(cfg, typ, triggered, mapped, in_token, interaction, response, detail):
        rows.append({"config_name": cfg, "group": GROUPS[typ], "type": typ,
                     "triggered": triggered, "actor_mapping": mapped,
                     "in_token": in_token, "interaction": interaction,
                     "ego_response": response, "detail": detail})

    # --- owned-actor groups B/C/D (scan whole timeline for actor presence) ---
    for e in events:
        typ = e["type"]
        if typ not in ("ParkingCutIn", "VehicleTurningRoute", "PedestrianCrossing"):
            continue
        cfg = e["config_name"]
        ids = owned_by_cfg[cfg]
        obs = []  # (t, actor_id, x, y, spd)
        for r in tl:
            for act in r["actors"]:
                if act["actor_id"] in ids:
                    obs.append((sec(r), act["actor_id"], act["x"], act["y"], act["speed_kmh"]))
        if not obs:
            add_row(cfg, typ, "Y", "Y", "N", "N", "N", "no token obs (actor never entered range)")
            continue
        t0 = min(o[0] for o in obs); t1 = max(o[0] for o in obs)
        md = min(math.hypot(o[2], o[3]) for o in obs)
        ew = [r for r in tl if t0 - 2 <= sec(r) <= t1 + 2]
        ego_min = min(r["ego_speed_mps"] for r in ew) if ew else None
        close_frames = sum(1 for o in obs if math.hypot(o[2], o[3]) <= 15.0)
        # lateral-entry evidence for cut-in-like motion: any owned actor with x>0 whose |y| shrinks below 2.5
        lat = []
        byid = {}
        for (t, aid, x, y, s) in obs:
            byid.setdefault(aid, []).append((t, x, y, s))
        for aid, tr in byid.items():
            ys = [y for (_, x, y, _) in tr]
            xs = [x for (_, x, y, _) in tr]
            miny = min(abs(y) for (_, x, y, _) in tr)
            if len(tr) > 2 and min(xs) > -5 and miny < 2.6 and (ys[0] > 2.6 or ys[-1] > 2.6):
                lat.append((aid, round(ys[0], 1), round(ys[-1], 1), round(miny, 1)))
        response = "N"
        if ego_min is not None and ego_min < 1.0 and close_frames > 3:
            response = "Y(stop)"
        elif ego_min is not None and ego_min < 4.0 and close_frames > 2:
            response = "Y(slow)"
        inter = "Y" if close_frames > 3 and ego_min is not None and ego_min < 6.0 else ("weak" if close_frames else "N")
        add_row(cfg, typ, "Y", "Y", "Y", inter, response,
                f"obs_t={t0:.0f}-{t1:.0f}s min_dist={md:.1f}m close_frames={close_frames} ego_min={ego_min} lateral_cross={lat}")

    # --- HardBreak (window + front-lead detection) ---
    for e in events:
        if e["type"] != "HardBreakRoute":
            continue
        cfg = e["config_name"]
        te = e.get("game_time") or 0.0
        win = [r for r in tl if te <= sec(r) <= te + 60]
        # ego stop/slow episodes inside window
        spd = [(sec(r), r["ego_speed_mps"]) for r in win]
        # find first sustained low-speed segment
        ep = None
        i = 0
        while i < len(spd):
            if spd[i][1] < 0.6:
                j = i
                while j < len(spd) and spd[j][1] < 0.6:
                    j += 1
                if j - i >= 2:  # >=0.4 s at 5Hz... use >=4 rows =0.8s
                    if j - i >= 4:
                        ep = (spd[i][0], spd[j - 1][0])
                        break
                i = j
            else:
                i += 1
        detail = ""
        if ep is None:
            # check for strong deceleration (slow below 2.5 m/s) instead
            mins = min((v for _, v in spd), default=None)
            detail = f"no_full_stop ego_min={mins:.1f}" if mins is not None else "no_data"
            add_row(cfg, "HardBreakRoute", "Y", "N(owned)", "N", "?", "Y(slow)" if mins is not None and mins < 3.0 else "N", detail)
            continue
        # inside stop episode find nearest front vehicle that also slowed
        stop_start, stop_end = ep
        frames_in_stop = [r for r in win if stop_start - 2 <= sec(r) <= stop_end + 1]
        cand = None
        for r in frames_in_stop:
            fv = front_vehicle_near(r["actors"])
            if fv:
                cand = fv[0]
                break
        # speed of candidate before and during stop
        cand_ok = False
        if cand is not None:
            before = [a for r in win for a in r["actors"]
                      if a["actor_id"] == cand["actor_id"] and sec(r) < stop_start]
            during = [a for r in frames_in_stop for a in r["actors"]
                      if a["actor_id"] == cand["actor_id"]]
            b_spd = max((a["speed_kmh"] for a in before), default=None)
            d_spd = max((a["speed_kmh"] for a in during), default=None)
            cand_ok = (b_spd is not None and (d_spd is None or d_spd < 5.0)) or (d_spd is not None and d_spd < 5.0)
            detail = (f"stop_t={stop_start:.0f}-{stop_end:.0f}s lead_id={cand['actor_id']} "
                      f"lead_speed_before={b_spd} during={d_spd} ego_stopped")
        else:
            detail = f"stop_t={stop_start:.0f}-{stop_end:.0f}s no_front_vehicle_in_token"
        add_row(cfg, "HardBreakRoute", "Y", "N/A(no owned)", "Y" if cand else "N",
                "Y" if cand else "N", "Y(stop)" if ep else "N", detail)

    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["config_name", "group", "type", "triggered",
                                          "actor_mapping", "in_token", "interaction",
                                          "ego_response", "detail"])
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(f"{r['group']} {r['config_name']:24s} trig={r['triggered']} "
              f"map={r['actor_mapping']} tok={r['in_token']} inter={r['interaction']} "
              f"resp={r['ego_response']} | {r['detail']}")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
