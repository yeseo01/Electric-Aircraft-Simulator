# utils.py
from math import pi


# ============================================================
# Angle utilities
# ============================================================

def wrap_to_pi(angle: float) -> float:
    """
    각도를 [-pi, pi] 범위로 래핑한다.
    예: 3.5π -> -0.5π
    """
    return (angle + pi) % (2 * pi) - pi


def deg2rad(deg: float) -> float:
    """
    degree -> radian 변환
    """
    return deg * pi / 180.0


# ============================================================
# Numeric utilities
# ============================================================

def clamp(x: float, lo: float, hi: float) -> float:
    """
    스칼라 값을 [lo, hi] 범위로 제한한다.
    """
    return max(lo, min(hi, x))
