"""统一坐标系约定 + 84 维状态构造（CARLA / Waymo 共用一个入口）

canonical 约定：x 前、y 左、heading 逆时针为正（标准数学系，单位：米/弧度）

  · Waymo / GPUDrive：原始数据已是 canonical → 恒等
  · CARLA：左手系（y 右）、yaw 顺时针为正（度）→ y 取反、yaw 取反并转弧度

所有 84 维状态（以及规划器特征）都必须先转到 canonical 再计算，
这样在 CARLA 上训练/推理与在 Waymo 上完全等价。
"""
import math

import numpy as np

# ---- 84 维布局（与 idc_agent 一致）----
DIM_EGO, DIM_OTHERS, DIM_VALIDITY, DIM_REF_ERROR = 6, 32, 8, 18
DIM_TEMPORAL, DIM_VEH, DIM_EXTRA = 1, 1, 18
TOTAL_DIM = DIM_EGO + DIM_OTHERS + DIM_VALIDITY + DIM_REF_ERROR \
    + DIM_TEMPORAL + DIM_VEH + DIM_EXTRA          # 84
N_OTHER = 8
CORRIDOR_HALF_W = 2.0
SCALE_A_LAT, SCALE_TTC = 5.0, 10.0


def wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


# ---------------- 坐标转换 ----------------
def carla_to_canonical(x, y, yaw_deg):
    """CARLA 原始位姿 → canonical（y 取反、yaw 取反并转弧度）。"""
    return float(x), -float(y), -math.radians(float(yaw_deg))


def canonical_to_carla(x, y, h_rad):
    """canonical → CARLA 原始位姿（用于把状态写回 CARLA 检查）。"""
    return float(x), -float(y), -math.degrees(float(h_rad))


def waymo_to_canonical(x, y, yaw_rad):
    return float(x), float(y), float(yaw_rad)


def canonical_to_waymo(x, y, h_rad):
    return float(x), float(y), float(h_rad)


# ---------------- 参考误差 ----------------
def ref_error(pose, ref_pos, ref_heading, ref_speed, ego_speed):
    """[dp, dphi, dv]，dp 带符号（参考在左为正）。"""
    x, y, h = pose
    dx = float(ref_pos[0]) - x
    dy = float(ref_pos[1]) - y
    dp = math.hypot(dx, dy)
    cross = dy * math.cos(ref_heading) - dx * math.sin(ref_heading)
    dp *= math.copysign(1.0, cross) if cross != 0 else 1.0
    dphi = wrap(float(ref_heading) - h)
    dv = float(ego_speed) - float(ref_speed)
    return dp, dphi, dv


def neighbor_extras(pose, neighbors, v_ego=0.0):
    """8 辆周车 × [ttc/10, in_corridor]（canonical 下计算）。"""
    x, y, h = pose
    c, s = math.cos(-h), math.sin(-h)
    out = np.zeros((N_OTHER, 2), np.float32)
    for k, nb in enumerate(neighbors[:N_OTHER]):
        dx, dy = float(nb['x']) - x, float(nb['y']) - y
        rx = dx * c - dy * s
        ry = dx * s + dy * c
        d = math.hypot(dx, dy)
        if d < 1e-6:
            continue
        vx = float(nb.get('v', 0.0)) * math.cos(float(nb.get('h', 0.0)))
        vy = float(nb.get('v', 0.0)) * math.sin(float(nb.get('h', 0.0)))
        closing = -(vx * dx + vy * dy) / max(d, 1e-3) + float(v_ego)
        out[k, 0] = min(d / max(closing, 0.5), SCALE_TTC) / SCALE_TTC
        out[k, 1] = 1.0 if (abs(ry) <= CORRIDOR_HALF_W and rx > 0) else 0.0
    return out.reshape(-1)


def build_state84(pose, ego_speed, neighbors, ref_pos, ref_heading, ref_speed,
                  ref_idx=0, veh_len=5.286, a_lat=0.0, steer_prev=0.0,
                  lookahead=None, ahead=(0.0, 0.0, 0.0)):
    """canonical 输入 → 84 维状态。

    pose: (x, y, h) canonical
    neighbors: [{x, y, h, v}] canonical，按距离升序
    ref_pos/ref_heading/ref_speed: 当前参考点（canonical）
    lookahead: [(lat, dphi, road, spd)] × 3（t+5/10/15）；None 则用 0
    ahead: (curv_ahead, spd_ahead, road_ahead)
    """
    x, y, h = float(pose[0]), float(pose[1]), float(pose[2])
    ego = np.array([x, y, float(ego_speed), 0.0, h, 0.0], np.float32)

    oth = np.zeros((N_OTHER, 4), np.float32)
    val = np.zeros(N_OTHER, np.float32)
    for k, nb in enumerate(neighbors[:N_OTHER]):
        oth[k] = [float(nb['x']), float(nb['y']), float(nb['h']), float(nb['v'])]
        val[k] = 1.0

    dp, dphi, dv = ref_error(pose, ref_pos, ref_heading, ref_speed, ego_speed)
    la = []
    if lookahead:
        for (lat, dph, road, spd) in lookahead[:3]:
            la += [float(lat), float(dph), float(road), float(spd)]
    while len(la) < 12:
        la.append(0.0)
    la += [float(ahead[0]), float(ahead[1]), float(ahead[2])]
    ref_err = np.array([dp, dphi, dv] + la, np.float32)
    assert ref_err.shape[0] == DIM_REF_ERROR

    extras = np.concatenate([
        np.array([a_lat / SCALE_A_LAT, float(steer_prev)], np.float32),
        neighbor_extras(pose, neighbors, v_ego=ego_speed),
    ]).astype(np.float32)
    assert extras.shape[0] == DIM_EXTRA

    st = np.concatenate([ego, oth.reshape(-1), val, ref_err,
                         np.array([float(ref_idx)], np.float32),
                         extras,
                         np.array([float(veh_len)], np.float32)]).astype(np.float32)
    assert st.shape[0] == TOTAL_DIM, st.shape
    return st


def encode82(st):
    """对应 idc_agent._encode 的 v2 分支：84 → 82（去绝对 x,y，周车转自车系）。"""
    st = np.asarray(st, np.float32).reshape(-1)
    x, y, phi = st[0], st[1], st[4]
    c, s = math.cos(phi), math.sin(phi)
    o = st[6:38].reshape(N_OTHER, 4)
    out = np.zeros(82, np.float32)
    out[0:4] = [0.0, 0.0, st[2], 0.0]
    for k in range(N_OTHER):
        dx, dy = o[k, 0] - x, o[k, 1] - y
        out[4 + 4 * k: 8 + 4 * k] = [
            dx * c + dy * s, -dx * s + dy * c, wrap(o[k, 2] - phi), o[k, 3]]
    out[36:63] = st[38:65]     # validity8 + ref18 + temporal1
    out[63] = st[83]           # veh
    out[64:82] = st[65:83]     # extras 18
    return out


# ===================== State v3（紧凑摘要，+16 维 → 100）=====================
DIM_VRU = 5        # [最近距离/20, 相对速度/10, TTC/5, 是否在走廊, 数量/4]
DIM_LIGHT = 4      # [红, 黄, 绿, 到灯距离/50]
DIM_EGODYN = 3     # [steer_prev, a_lat/5, yaw_rate/2]
DIM_CMD = 3        # [左, 直, 右]
DIM_REMAIN = 1     # [剩余距离/200]
TOTAL_DIM_V3 = TOTAL_DIM + DIM_VRU + DIM_LIGHT + DIM_EGODYN + DIM_CMD + DIM_REMAIN


def vru_summary(pose, vrus, v_ego=0.0, horizon=40.0):
    """行人/自行车摘要（canonical 系）。vrus: [{x, y, vx, vy}]"""
    x, y, h = float(pose[0]), float(pose[1]), float(pose[2])
    c, s = math.cos(-h), math.sin(-h)
    out = np.zeros(DIM_VRU, np.float32)
    best = None
    cnt = 0
    for p in vrus or []:
        dx, dy = float(p['x']) - x, float(p['y']) - y
        rx = dx * c - dy * s
        ry = dx * s + dy * c
        d = math.hypot(dx, dy)
        if d > horizon:
            continue
        cnt += 1
        if rx <= 0.5 or abs(ry) > CORRIDOR_HALF_W + 0.5:
            continue
        closing = -(float(p.get('vx', 0.0)) * dx + float(p.get('vy', 0.0)) * dy) / max(d, 1e-3) + float(v_ego)
        ttc = d / max(closing, 0.5)
        in_corr = 1.0 if abs(ry) <= CORRIDOR_HALF_W else 0.0
        if best is None or d < best[0]:
            best = (d, closing, ttc, in_corr)
    if best is not None:
        out[:] = [best[0] / 20.0, best[1] / 10.0, min(best[2], 50.0) / 5.0,
                  best[3], min(cnt, 8) / 4.0]
    else:
        out[4] = min(cnt, 8) / 4.0
    return out


def light_features(dist, state):
    """交通灯：dist 到最近相关灯（米），state ∈ {'red','yellow','green','off',None}"""
    out = np.zeros(DIM_LIGHT, np.float32)
    if state is None:
        return out
    s = str(state).lower()
    out[0] = 1.0 if 'red' in s else 0.0
    out[1] = 1.0 if 'yellow' in s else 0.0
    out[2] = 1.0 if 'green' in s else 0.0
    out[3] = float(min(max(dist or 0.0, 0.0), 50.0)) / 50.0
    return out


def ego_dyn_features(steer_prev=0.0, a_lat=0.0, yaw_rate=0.0):
    return np.array([float(steer_prev), float(a_lat) / SCALE_A_LAT,
                     float(yaw_rate) / 2.0], np.float32)


def cmd_features(ego_heading, route_heading_at_preview):
    """导航指令：左/直/右 one-hot（canonical：正角为左）"""
    out = np.zeros(DIM_CMD, np.float32)
    d = wrap(float(route_heading_at_preview) - float(ego_heading))
    if d > 0.35:
        out[0] = 1.0
    elif d < -0.35:
        out[2] = 1.0
    else:
        out[1] = 1.0
    return out


def build_state_v3(base84, vru=None, light=None, ego_dyn=None, cmd=None,
                   remain=0.0):
    """现有 84 维 + 16 维摘要 → 100 维"""
    v = np.zeros(DIM_VRU, np.float32) if vru is None else np.asarray(vru, np.float32)
    l = np.zeros(DIM_LIGHT, np.float32) if light is None else np.asarray(light, np.float32)
    e = np.zeros(DIM_EGODYN, np.float32) if ego_dyn is None else np.asarray(ego_dyn, np.float32)
    c = np.zeros(DIM_CMD, np.float32) if cmd is None else np.asarray(cmd, np.float32)
    r = np.array([float(remain) / 200.0], np.float32)
    st = np.concatenate([np.asarray(base84, np.float32), v, l, e, c, r])
    assert st.shape[0] == TOTAL_DIM_V3, (st.shape, TOTAL_DIM_V3)
    return st.astype(np.float32)


def encode_v3(s):
    """100 → 98（base 82 + 新 16）"""
    s = np.asarray(s, np.float32)
    base = encode82(s[..., :TOTAL_DIM])
    return np.concatenate([base, s[..., TOTAL_DIM:TOTAL_DIM_V3]], -1).astype(np.float32)
