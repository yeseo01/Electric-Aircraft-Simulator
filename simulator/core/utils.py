"""Small numerical and angle utility functions."""

from math import pi


def wrap_to_pi(angle: float) -> float:
    """Wrap an angle to the interval [-pi, pi)."""
    return (angle + pi) % (2 * pi) - pi


def deg2rad(deg: float) -> float:
    """Convert degrees to radians."""
    return deg * pi / 180.0


def clamp(x: float, lo: float, hi: float) -> float:
    """Clamp a scalar value to the interval [lo, hi]."""
    return max(lo, min(hi, x))
