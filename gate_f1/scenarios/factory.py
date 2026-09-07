"""Gate F1 scene factory: builds CARLA props + motion laws for the 8 scenarios.

Scene exposes:
  v_target, record_seconds
  props : list of dict {actor, kind, meta}
  step(amap, trel) : reposition props (deterministic; trel since t0)
  front_s(amap, ego_s, trel) : nearest obstacle-ahead distance for ego speed cap
"""
import math

import yaml

import geo
from carla_env import spawn_vehicle, spawn_walker

PARAMS = yaml.safe_load(open("gate_f1/config/parameter_table.yaml"))
GROUPS = {g["id"]: g for g in PARAMS["groups"]}
QOFF = PARAMS["queue_c0_offsets"]
F2EX = yaml.safe_load(open("gate_f1/config/f2_expansion.yaml"))

CROSS_SPEED = 1.6


def _cross_window(g):
    """Bracketing window (PROTOCOL.md): occupancy start before fastest reach."""
    d, v = g["d_conflict"], g["v_target"]
    Te = d / v
    tacc = (12.0 - v) / 1.5
    dacc = v * tacc + 0.75 * tacc * tacc
    tmin = (-v + math.sqrt(v * v + 3.0 * d)) / 1.5 if dacc >= d else tacc + (d - dacc) / 12.0
    return tmin, Te, [tmin - 1.0, max(Te + 1.0, tmin + 2.5)]


class Scene:
    name = ""
    v_target = 8.0
    record_seconds = 12.0
    props = []
    meta = {}

    def step(self, amap, trel):
        import carla as _c
        for p in self.props:
            tf = p.get("tf", None)
            if tf is not None and p.get("move", False) is not True:
                p["actor"].set_transform(tf)
                p["actor"].set_target_velocity(_c.Vector3D(0, 0, 0))

    def front_s(self, amap, ego_s, trel):
        return None

    def props_actors(self):
        return [p["actor"] for p in self.props]

    def destroy(self):
        seen = set()
        for p in self.props:
            a = p["actor"]
            if a.id in seen or not a.is_alive:
                continue
            seen.add(a.id)
            try:
                a.destroy()
            except Exception:
                pass


def _spawn_try(world, amap, kind, s, axis="c0", yaw_off=0.0):
    """Try spawns around station s (+-lateral/station jitter); return actor + (s,yaw)
    of the FIRST success. Caller re-anchors to its intended pose afterwards."""
    import carla as _c
    if axis == "cl":
        cands = [(s, 0.0), (s, 1.0), (s, -1.0), (s + 2, 0.0), (s - 2, 0.0)]
        for ss, loff in cands:
            x, y, zz, yaw = geo.cl_seg_point(amap, ss + loff)
            a = spawn_vehicle(world, None if kind == "anycar" else kind,
                              x, y, zz, yaw + yaw_off)
            if a is not None:
                return a, (x, y, zz, yaw + yaw_off)
        # broad fallback along actual CL centerline in safe window
        for ss in range(16, 82, 4):
            x, y, zz, yaw = geo.cl_seg_point(amap, float(ss))
            a = spawn_vehicle(world, None if kind == "anycar" else kind,
                              x, y, zz, yaw + yaw_off)
            if a is not None:
                return a, (x, y, zz, yaw + yaw_off)
        return None, None
    cands = [(s, 0.0), (s, 1.0), (s, -1.0), (s, 1.7), (s, -1.7),
             (s + 1, 0.0), (s - 1, 0.0), (s + 2, 0.0), (s - 2, 0.0)]
    for ss, loff in cands:
        x, y, zz, yaw = geo.seg_point(amap, ss, loff)
        if kind == "walker":
            a = spawn_walker(world, x, y, zz)
        else:
            a = spawn_vehicle(world, None if kind == "anycar" else kind,
                              x, y, zz, yaw + yaw_off)
        if a is not None:
            return a, (x, y, zz, yaw + yaw_off)
    # broad fallback: any free station on this axis in the safe window
    for ss in range(16, 82, 4):
        if axis == "cl":
            continue
        x, y, zz, yaw = geo.seg_point(amap, float(ss), 0.0)
        if kind == "walker":
            a = spawn_walker(world, x, y, zz)
        else:
            a = spawn_vehicle(world, None if kind == "anycar" else kind,
                              x, y, zz, yaw + yaw_off)
        if a is not None:
            return a, (x, y, zz, yaw + yaw_off)
    return None, None


def _static_prop(world, amap, actor_kind, s, axis="c0", yaw_off=0.0, z=None):
    a, _ = _spawn_try(world, amap, actor_kind, s, axis=axis, yaw_off=yaw_off)
    if a is None:
        raise RuntimeError(f"spawn failed {actor_kind} axis={axis} s={s}")
    # anchor at the DESIRED pose regardless of spawn drift: reset every tick
    import carla as _c
    if axis == "cl":
        x, y, zz, yaw = geo.cl_seg_point(amap, s)
    else:
        x, y, zz, yaw = geo.seg_point(amap, s, 0.0)
    z = z if z is not None else zz
    des = _c.Transform(_c.Location(x=x, y=y, z=z),
                       _c.Rotation(yaw=yaw + yaw_off))
    a.set_transform(des)
    a.set_target_velocity(_c.Vector3D(0, 0, 0))
    return {"actor": a, "tf": des, "kind": actor_kind, "axis": axis,
            "s": s, "move": True if actor_kind in ("vehicle.audi.tt", "walker")
            else False}


def _crossing(world, amap, g, kind):
    """A1/A2: crosser sweeps lat lat0 -> +6 at CROSS_SPEED across d_conflict."""
    tmin, Te, win = _cross_window(g)
    s_c = Scene()
    s_c.v_target = g["v_target"]
    s_c._win = win
    d = g["d_conflict"]
    import carla as _c
    lat_cands = (-6.0, -7.0, 6.0, -8.0, -4.0) if kind == "walker" else (-2.5, -4.0, 2.5)
    s_spawn_cands = (d, d + 5.0, d - 5.0, 30.0, 40.0, 50.0)
    a, x, y, z, lat0 = None, None, None, None, None
    for s_sp in s_spawn_cands:
        for lat0 in lat_cands:
            if kind == "walker":
                a, _ = _spawn_try(world, amap, "walker", s_sp, axis="c0")
                if a is None:
                    continue
                x, y = geo.world_from_local(s_sp, lat0)
                wp = amap.get_waypoint(_c.Location(x=x, y=y), project_to_road=True,
                                       lane_type=_c.LaneType.Driving)
                z = wp.transform.location.z if wp else 0.2
                break
            else:
                a, _ = _spawn_try(world, amap, "anycar", s_sp, axis="c0")
                if a is None:
                    continue
                x, y = geo.world_from_local(s_sp, lat0)
                wp = amap.get_waypoint(_c.Location(x=x, y=y), project_to_road=True,
                                       lane_type=_c.LaneType.Driving)
                z = wp.transform.location.z if wp else 0.2
                break
        if a is not None:
            break
    if a is None:
        raise RuntimeError(f"crosser spawn failed {kind}")
    # anchor immediately at the conflict shoulder; law teleports every tick
    t_start = tmin - (0.0 - lat0) / CROSS_SPEED
    xc, yc = geo.world_from_local(d, lat0)
    a.set_transform(_c.Transform(_c.Location(x=xc, y=yc, z=a.get_location().z),
                                 _c.Rotation(yaw=geo.heading_deg() +
                                 (90.0 if kind != "walker" else 0.0))))
    a.set_target_velocity(_c.Vector3D(0, 0, 0))
    p = {"actor": a, "tf": _c.Transform(_c.Location(x=xc, y=yc, z=a.get_location().z),
                                        _c.Rotation(yaw=geo.heading_deg() +
                                        (90.0 if kind != "walker" else 0.0))),
         "kind": kind, "axis": "c0", "s": d, "move": True,
         "t0_lat": lat0, "x0": x, "y0": y,
         "t_start": t_start,  # center reaches lat0 at tmin
         "t_done": (6.0 - lat0) / CROSS_SPEED + t_start}
    s_c.props = [p]

    def step(amap, trel):
        q = p
        if trel < q["t_start"]:
            lat = q["t0_lat"]
        elif trel >= q["t_done"]:
            lat = 6.0
        else:
            lat = q["t0_lat"] + CROSS_SPEED * (trel - q["t_start"])
        x, y = geo.world_from_local(d, lat)
        rot = q["actor"].get_transform().rotation
        yaw = geo.heading_deg() + (90.0 if kind != "walker" else 0.0)
        q["actor"].set_transform(_c.Transform(
            _c.Location(x=x, y=y, z=q["actor"].get_location().z),
            _c.Rotation(yaw=yaw)))
        q["actor"].set_target_velocity(_c.Vector3D(0, 0, 0))
    s_c.step = step
    s_c.meta = {"win": win, "d_conflict": d, "tmin": tmin}

    def arm(ego_s, v_e):
        """Re-arm crossing to ego's actual state at t0 (remaining distance)."""
        dr = max(d - ego_s, 5.0)
        # earliest reachable arrival under engine accel 1.5 from v_e
        tacc = (12.0 - v_e) / 1.5
        dacc = v_e * tacc + 0.75 * tacc * tacc
        tmin_r = (-v_e + math.sqrt(v_e * v_e + 3.0 * dr)) / 1.5 if dacc >= dr \
            else tacc + (dr - dacc) / 12.0
        p["t_start"] = max(-2.0, tmin_r - (0.0 - p["t0_lat"]) / CROSS_SPEED)
        p["t_done"] = (6.0 - p["t0_lat"]) / CROSS_SPEED + p["t_start"]
        p["_tmin_r"] = tmin_r
        s_c.meta["tmin_armed"] = round(tmin_r, 2)
    s_c.arm = arm
    return s_c


def _static_blocker(world, amap, g, name, axis="c0"):
    s_c = Scene()
    s_c.name = name
    s_c.v_target = g["v_target"]
    L = g["L_block"]
    s_c.props = [_static_prop(world, amap, "anycar", L, axis=axis)]
    s_c.meta = {"L_block": L}
    return s_c


def _stopped_queue(world, amap, g, name, axis="c0"):
    s_c = Scene()
    s_c.name = name
    s_c.v_target = g["v_target"]
    L = g["L_block"]
    for off in QOFF:
        s_c.props.append(_static_prop(world, amap, "anycar", L + off, axis=axis))
    s_c.meta = {"L_block": L}
    return s_c


def _slow_lead(world, amap, g, name):
    s_c = Scene()
    s_c.name = name
    s_c.v_target = g["v_target"]
    s_c.s0 = g["s0_lead"]
    s_c.vlead = g["v_lead"]
    p = _static_prop(world, amap, "anycar", s_c.s0, axis="c0")
    s_c.props = [p]
    s_c.meta = {"v_lead": s_c.vlead, "s0_lead": s_c.s0}

    def step(amap, trel):
        s = min(s_c.s0 + s_c.vlead * trel, 150.0)
        idx = max(0, min(int(round(s)), len(geo.SEG["c0"]) - 1))
        x, y = geo.SEG["c0"][idx]
        wp = amap.get_waypoint(__import__("carla").Location(x=x, y=y),
                               project_to_road=True,
                               lane_type=__import__("carla").LaneType.Driving)
        z = wp.transform.location.z if wp else p["actor"].get_location().z
        p["actor"].set_transform(__import__("carla").Transform(
            __import__("carla").Location(x=x, y=y, z=z),
            __import__("carla").Rotation(yaw=geo.heading_deg())))
        p["actor"].set_target_velocity(__import__("carla").Vector3D(0, 0, 0))
    s_c.step = step
    return s_c


def _d1(world, amap, g, name):
    s_c = Scene()
    s_c.name = name
    s_c.v_target = g["v_target"]
    L = g["L_block"]
    s_c.props = [_static_prop(world, amap, "anycar", L, axis="c0")]
    D1 = PARAMS["d1"]
    for st in D1["cl_stations"]:
        p = _static_prop(world, amap, "anycar", st, axis="cl")
        p["stream_v"] = D1["cl_speed"]
        p["stream_s0"] = st
        s_c.props.append(p)
    s_c.meta = {"L_block": L, "cl_speed": D1["cl_speed"]}

    def step(amap, trel):
        import carla as _c
        p0 = s_c.props[0]
        p0["actor"].set_transform(p0["tf"])
        p0["actor"].set_target_velocity(_c.Vector3D(0, 0, 0))
        for p in s_c.props[1:]:
            s = min(p["stream_s0"] + p["stream_v"] * trel, 200.0)
            idx = max(0, min(int(round(s)), len(geo.SEG["cl"]) - 1))
            x, y = geo.SEG["cl"][idx]
            p["actor"].set_transform(_c.Transform(
                _c.Location(x=x, y=y, z=p["actor"].get_location().z),
                _c.Rotation(yaw=geo.heading_deg())))
            p["actor"].set_target_velocity(_c.Vector3D(0, 0, 0))
    s_c.step = step
    return s_c


def _d2(world, amap, g, name):
    s_c = Scene()
    s_c.name = name
    s_c.v_target = g["v_target"]
    L = g["L_block"]
    for off in QOFF:
        s_c.props.append(_static_prop(world, amap, "anycar", L + off, axis="c0"))
        s_c.props.append(_static_prop(world, amap, "anycar", L + off, axis="cl"))
    s_c.meta = {"L_block": L}
    return s_c


def _move_on_c0(amap, actor, s, yaw=None):
    """Teleport vehicle to station s on c0 (clamped to segment)."""
    import carla as _c
    s = min(float(s), float(len(geo.SEG["c0"]) - 2))
    idx = max(0, int(round(s)))
    x, y = geo.SEG["c0"][idx]
    wp = amap.get_waypoint(_c.Location(x=x, y=y), project_to_road=True,
                           lane_type=_c.LaneType.Driving)
    z = wp.transform.location.z if wp else 0.3
    actor.set_transform(_c.Transform(_c.Location(x=x, y=y, z=z),
                                     _c.Rotation(yaw=yaw or geo.heading_deg())))
    actor.set_target_velocity(_c.Vector3D(0, 0, 0))


def _cl_static_queue(world, amap, scene, start=10, step=14, n=9):
    """Anchor a static CL queue [start .. start+step*(n-1)] onto a scene;
    wraps scene.step so the queue is re-anchored every tick."""
    import carla as _c
    qs = []
    for k in range(n):
        st = start + step * k
        q = _static_prop(world, amap, "anycar", st, axis="cl")
        qs.append(q)
    scene.props.extend(qs)
    scene._clq = qs
    base = scene.step

    def step(amap, trel):
        base(amap, trel)
        for q in qs:
            q["actor"].set_transform(q["tf"])
            q["actor"].set_target_velocity(_c.Vector3D(0, 0, 0))
    scene.step = step
    return scene


def _lead_stop(world, amap, row, name, left_occ, left_mode="moving"):
    """G1/G2: lead cruises v0 for tc s, brakes at a to a full stop, stays
    stopped. left_occ=True adds CL traffic (moving platoon or static queue)."""
    import carla as _c
    s_c = Scene()
    s_c.name = name
    s_c.v_target = row["ego_v"]
    s0, v0, tc, a = row["s0"], row["v0"], row["tc"], row["a"]
    p = _static_prop(world, amap, "anycar", s0, axis="c0")
    s_c.props = [p]
    s_c.meta = {"lead": {"s0": s0, "v0": v0, "tc": tc, "a": a}}
    moving = left_occ and left_mode == "moving"
    if moving:
        D1 = PARAMS["d1"]
        for st in D1["cl_stations"]:
            q = _static_prop(world, amap, "anycar", st, axis="cl")
            q["stream_v"] = D1["cl_speed"]
            q["stream_s0"] = st
            s_c.props.append(q)

    def s_lead(trel):
        if trel <= tc:
            return s0 + v0 * trel
        tb = trel - tc
        tstop = v0 / a
        if tb >= tstop:
            return s0 + v0 * tc + v0 * v0 / (2 * a)
        return s0 + v0 * tc + v0 * tb - 0.5 * a * tb * tb

    def step(amap, trel):
        # stopped-lead props[0] follows law; CL platoon (if any) moves slow
        _move_on_c0(amap, s_c.props[0]["actor"], s_lead(trel))
        if moving:
            for q in s_c.props[1:]:
                s = min(q["stream_s0"] + q["stream_v"] * trel, 200.0)
                idx = max(0, min(int(round(s)), len(geo.SEG["cl"]) - 1))
                x, y = geo.SEG["cl"][idx]
                q["actor"].set_transform(_c.Transform(
                    _c.Location(x=x, y=y, z=q["actor"].get_location().z),
                    _c.Rotation(yaw=geo.heading_deg())))
                q["actor"].set_target_velocity(_c.Vector3D(0, 0, 0))
    s_c.step = step
    if left_occ and left_mode == "queue":
        _cl_static_queue(world, amap, s_c)
    return s_c


def _temp_occupant(world, amap, row, name):
    """G3: occupant holds on C0 until t_leave then drives away ahead."""
    s_c = Scene()
    s_c.name = name
    s_c.v_target = row["ego_v"]
    occ, tl, av = row["occ_s"], row["t_leave"], row["away_v"]
    p = _static_prop(world, amap, "anycar", occ, axis="c0")
    s_c.props = [p]
    s_c.meta = {"occupant": {"occ_s": occ, "t_leave": tl, "away_v": av}}

    def step(amap, trel):
        if trel < tl:
            s = occ
        else:
            s = occ + av * (trel - tl)
        _move_on_c0(amap, p["actor"], s)
    s_c.step = step
    return s_c


def _cl_platoon(world, amap, s_c):
    """add CL slow platoon (stations 30..78 @1.5 m/s) to a scene."""
    import carla as _c
    D1 = PARAMS["d1"]
    for st in D1["cl_stations"]:
        q = _static_prop(world, amap, "anycar", st, axis="cl")
        q["stream_v"] = D1["cl_speed"]
        q["stream_s0"] = st
        s_c.props.append(q)
    base = s_c.step
    def step(amap, trel):
        base(amap, trel)
        for q in s_c.props[1:]:
            if q.get("stream_s0") is None:
                continue
            s = min(q["stream_s0"] + q["stream_v"] * trel, 200.0)
            idx = max(0, min(int(round(s)), len(geo.SEG["cl"]) - 1))
            x, y = geo.SEG["cl"][idx]
            q["actor"].set_transform(_c.Transform(
                _c.Location(x=x, y=y, z=q["actor"].get_location().z),
                _c.Rotation(yaw=geo.heading_deg())))
            q["actor"].set_target_velocity(_c.Vector3D(0, 0, 0))
    s_c.step = step
    return s_c


def _cross_stall(world, amap, g, kind, left_occ=False):
    """F3 cross-stall: occupant performs a REAL crossing from off-corridor into
    the current lane, then PERSISTS in-lane for the horizon (current corridor
    stays closed); never initialized as a static blocker. left_occ adds the CL
    platoon -> Contingency."""
    import carla as _c
    s_c = Scene()
    s_c.v_target = g["v_target"]
    d = g["d_conflict"]
    lat0 = -6.0 if kind == "walker" else -2.5
    a, x, y, z = None, None, None, None
    for s_sp in (d, d - 5.0, 30.0, 40.0):
        for loff in (-6.0, -7.0, 6.0, -8.0, -4.0) if kind == "walker" else (-2.5, -4.0, 2.5):
            xx, yy = geo.world_from_local(s_sp, loff)
            wp = amap.get_waypoint(_c.Location(x=xx, y=yy), project_to_road=True,
                                   lane_type=_c.LaneType.Driving)
            zz = wp.transform.location.z if wp else 0.2
            if kind == "walker":
                a = spawn_walker(world, xx, yy, zz)
            else:
                a = spawn_vehicle(world, None, xx, yy, zz,
                                  geo.heading_deg() + 90.0)
            if a is not None:
                x, y, z, lat0 = xx, yy, zz, loff
                break
        if a is not None:
            break
    if a is None:
        raise RuntimeError("cross_stall spawn failed")
    # crossing starts immediately at t0 (early closure), enter to in-lane lat
    xc, yc = geo.world_from_local(d, lat0)
    a.set_transform(_c.Transform(_c.Location(x=xc, y=yc, z=z),
                                 _c.Rotation(yaw=geo.heading_deg() +
                                 (90.0 if kind != "walker" else 0.0))))
    a.set_target_velocity(_c.Vector3D(0, 0, 0))
    t_stall = (0.5 - lat0) / CROSS_SPEED      # time to reach in-lane hold lat
    p = {"actor": a, "kind": kind, "s": d, "t_stall": t_stall,
         "t0_lat": lat0, "move": True, "hold_lat": 0.5}
    s_c.props = [p]
    s_c.meta = {"d_conflict": d, "cross_stall": True, "left_occ": left_occ}

    def step(amap, trel):
        if trel < t_stall:
            lat = lat0 + CROSS_SPEED * trel
        else:
            lat = p["hold_lat"]               # persists in-lane for horizon
        x, y = geo.world_from_local(d, lat)
        q = p["actor"]
        q.set_transform(_c.Transform(_c.Location(x=x, y=y, z=q.get_location().z),
                                     _c.Rotation(yaw=geo.heading_deg() +
                                     (90.0 if kind != "walker" else 0.0))))
        q.set_target_velocity(_c.Vector3D(0, 0, 0))
    s_c.step = step
    if left_occ:
        _cl_static_queue(world, amap, s_c)
    return s_c


def make_f3(world, amap, spec):
    """F3 dataset row -> scene. spec keys: cell in
    {'cross_clear','cross_stall','lead_opt','lead_nec','lead_cont',
     'block_nec','block_cont','temp_opt'}, kind ('walker'/'vehicle'),
    ego_v, d_conflict, s0, v_lead, v0, tc, a, occ_s, t_leave, away_v,
    left_occ."""
    cell = spec["cell"]
    if cell in ("cross_clear", "cross_stall", "cross_stall_occ"):
        kind = "walker" if spec.get("kind") == "ped" else "vehicle"
        g = {"v_target": spec["ego_v"], "d_conflict": spec["d_conflict"]}
        if cell == "cross_clear":
            return _crossing(world, amap, g, kind)
        return _cross_stall(world, amap, g, kind,
                            left_occ=(cell == "cross_stall_occ"))
    if cell == "lead_opt":
        return _slow_lead(world, amap,
                          {"v_target": spec["ego_v"], "s0_lead": spec["s0"],
                           "v_lead": spec["v_lead"]}, "C")
    if cell in ("lead_nec", "lead_cont"):
        return _lead_stop(world, amap, spec, spec["cell"],
                          left_occ=(cell == "lead_cont"),
                          left_mode="queue" if cell == "lead_cont" else "moving")
    if cell == "block_nec":
        return _static_blocker(world, amap,
                               {"v_target": spec["ego_v"], "L_block": spec["L"]}, "B")
    if cell == "block_cont":
        s = _static_blocker(world, amap,
                            {"v_target": spec["ego_v"], "L_block": spec["L"]}, "B")
        return _cl_static_queue(world, amap, s)
    if cell == "temp_opt":
        return _temp_occupant(world, amap, spec, "T")
    raise KeyError(cell)


def make(name, world, amap, group_id):
    g = GROUPS[group_id]
    if name == "A1":
        s = _crossing(world, amap, g, "walker")
    elif name == "A2":
        s = _crossing(world, amap, g, "vehicle")
    elif name == "B1":
        s = _static_blocker(world, amap, g, name)
    elif name == "B2":
        s = _stopped_queue(world, amap, g, name)
    elif name == "C1":
        s = _slow_lead(world, amap, g, name)
    elif name == "C2":
        s = _slow_lead(world, amap, g, name)   # two-wheeler fallback = slow vehicle
    elif name == "D1":
        s = _d1(world, amap, g, name)
    elif name == "D2":
        s = _d2(world, amap, g, name)
    elif name == "G1":
        row = F2EX["g1"][group_id - 1]
        s = _lead_stop(world, amap, row, name, left_occ=False)
    elif name == "G2":
        row = F2EX["g2"][group_id - 1]
        s = _lead_stop(world, amap, row, name, left_occ=True)
    elif name == "G3":
        row = F2EX["g3"][group_id - 1]
        s = _temp_occupant(world, amap, row, name)
    else:
        raise KeyError(name)
    s.name = name
    s.group = group_id
    return s
