"""Gate F0 simple deterministic Lane-PID ego controller (no PlanT).

Longitudinal: PID on target speed (throttle/brake).
Lateral: look-ahead heading PD toward the current corridor centerline points
(KEEP along C0, CHANGE_LEFT along a quintic offset path).
"""
import math

import carla


def wrap_pi(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


class LanePIDEgo:
    def __init__(self, kp_steer=1.2, kd_steer=0.3, kp_v=0.6,
                 lookahead_m=6.0, max_accel=3.0, max_brake=6.0):
        self.kp_s, self.kd_s = kp_steer, kd_steer
        self.kp_v = kp_v
        self.lookahead = lookahead_m
        self.max_accel = max_accel
        self.max_brake = max_brake
        self._prev_yaw = None

    def steer(self, ego_t, path_pts):
        """Return steering from heading error to the nearest look-ahead path point."""
        x, y = ego_t.location.x, ego_t.location.y
        yaw = math.radians(ego_t.rotation.yaw)
        fwd = (math.cos(yaw), math.sin(yaw))
        best, best_d = None, None
        for p in path_pts:
            dx, dy = p[0] - x, p[1] - y
            # project onto forward axis to pick ahead points
            proj = dx * fwd[0] + dy * fwd[1]
            if proj < 0:
                continue
            d = math.hypot(dx, dy)
            if best_d is None or d < best_d:
                # bias selection to points near lookahead (fallback nearest ahead)
                score = abs(d - self.lookahead)
                if best is None or score < best:
                    best, best_d, best_score = (math.atan2(dy, dx), d, score)
        if best is None:
            # no ahead point: hold current heading
            err = 0.0
        else:
            err = wrap_pi(best - yaw)
        d_yaw = 0.0
        if self._prev_yaw is not None:
            d_yaw = wrap_pi(yaw - self._prev_yaw)
        self._prev_yaw = yaw
        steer = self.kp_s * err - self.kd_s * d_yaw
        return max(-1.0, min(1.0, steer))

    def longitudinal(self, v_now, target_speed):
        e = target_speed - v_now
        a = self.kp_v * e
        control = carla.VehicleControl()
        if a >= 0:
            control.throttle = min(1.0, a / self.max_accel)
            control.brake = 0.0
        else:
            control.brake = min(1.0, -a / self.max_brake)
            control.throttle = 0.0
        return control

    def step(self, ego_transform, v_now, target_speed, path_pts):
        control = self.longitudinal(v_now, target_speed)
        control.steer = self.steer(ego_transform, path_pts)
        return control
