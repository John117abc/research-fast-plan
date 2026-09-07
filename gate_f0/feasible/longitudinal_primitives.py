"""Gate F0 longitudinal ego dynamics (corridor-local coordinate)."""
from dataclasses import dataclass


@dataclass
class EgoState:
    s: float      # longitudinal progress along corridor centerline (m)
    v: float      # forward speed (m/s)

    def copy(self):
        return EgoState(self.s, self.v)


def step_accel(st, a, dt, v_max):
    """Return EgoState after applying constant accel `a` for dt (kinematic)."""
    v1 = st.v + a * dt
    v1 = min(max(v1, 0.0), v_max)
    s1 = st.s + st.v * dt + 0.5 * a * dt * dt
    return EgoState(s1, v1)
