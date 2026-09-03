import math
import numpy as np

EPS = 1e-6
HORIZON = 4.0       # s，第一轮代理值
DIST_SCALE = 50.0   # m，与 PlanT 默认目标范围量级保持一致
SPEED_SCALE = 20.0  # m/s，归一化尺度


def _half_diagonal_from_wh(width: float, length: float) -> float:
    """由完整宽/长计算外接圆半径。"""
    return 0.5 * float(np.hypot(width, length))


def relationize_exact_row(row, ego_speed_mps, ego_extent, horizon=HORIZON):
    """
    将 PlanT 原始 object row 转为关系 row。

    输入 row：
        训练阶段：
        [type, x, y, yaw_deg, speed_kmh, width, length, id]

        在线推理：
        [type, x, y, yaw_deg, speed_kmh, width, length]

    ego_extent：CARLA BoundingBox.extent 风格：
        [half_length_x, half_width_y, half_height_z]

    输出列数和输入保持一致：
        [type,
         m_now_norm,
         m_min_norm,
         closing_norm,
         tcpa_norm,
         cos_bearing,
         sin_bearing,
         (optional id)]
    """
    if len(row) not in (7, 8):
        raise ValueError(f"Expected row with 7 or 8 columns, got {len(row)}")

    type_id = row[0]

    x = float(row[1])
    y = float(row[2])
    yaw_rad = np.deg2rad(float(row[3]))
    obj_speed_mps = float(row[4]) / 3.6
    width = float(row[5])
    length = float(row[6])

    # PlanT / CARLA 自车局部坐标：x 轴朝车头前方。
    p = np.array([x, y], dtype=np.float64)

    v_obj = obj_speed_mps * np.array(
        [np.cos(yaw_rad), np.sin(yaw_rad)],
        dtype=np.float64,
    )
    v_ego = np.array([float(ego_speed_mps), 0.0], dtype=np.float64)
    v_rel = v_obj - v_ego

    # CARLA extent 本身是半尺寸，所以自车外接圆半径直接 hypot(extent_x, extent_y)
    ego_radius = float(
        np.hypot(float(ego_extent[0]), float(ego_extent[1]))
    )
    obj_radius = _half_diagonal_from_wh(width, length)
    r_sum = ego_radius + obj_radius

    d_now = float(np.linalg.norm(p))
    m_now = d_now - r_sum

    # Constant-velocity closest point of approach
    vv = float(v_rel @ v_rel)
    if vv < EPS:
        tcpa = 0.0
    else:
        tcpa = float(
            np.clip(
                -float(p @ v_rel) / (vv + EPS),
                0.0,
                horizon,
            )
        )

    p_cpa = p + v_rel * tcpa
    m_min = float(np.linalg.norm(p_cpa) - r_sum)

    if d_now < EPS:
        closing = 0.0
    else:
        closing = float(-float(p @ v_rel) / (d_now + EPS))

    bearing = math.atan2(y, x)

    features = [
        float(np.clip(m_now / DIST_SCALE, -2.0, 2.0)),
        float(np.clip(m_min / DIST_SCALE, -2.0, 2.0)),
        float(np.clip(closing / SPEED_SCALE, -2.0, 2.0)),
        float(np.clip(tcpa / max(horizon, EPS), 0.0, 1.0)),
        float(np.cos(bearing)),
        float(np.sin(bearing)),
    ]

    output = [type_id, *features]

    # 训练数据里还有 object id；必须保留到原 forecasting target 完成匹配以后。
    if len(row) == 8:
        output.append(row[-1])

    return output


def filter_planner_tokens(data_car, remove_stop_sign_token=False):
    """Gate 4.6: shared train/online filter removing type=4 stop-sign tokens.

    Only affects the planner input rows; never touches CARLA GT, forecasting
    targets, or any other token type.
    """
    if not remove_stop_sign_token:
        return data_car
    return [row for row in data_car if int(round(float(row[0]))) != 4]
