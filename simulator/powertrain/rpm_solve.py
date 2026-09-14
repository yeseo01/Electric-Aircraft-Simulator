"""Utilities for shaft-power limits and RPM inversion."""

from __future__ import annotations

from typing import Callable, Tuple

import numpy as np


def power_cap_at_rpm_safe(
    V_ms: float,
    rho: float,
    Cp_func: Callable[[float], float],
    Dp: float,
    J_min: float,
    J_max: float,
    rpm_safe: float,
) -> float:
    """Compute the shaft-power limit available at the safe RPM bound.

    The propeller-power relation is:

        P(rpm) = rho * n^3 * D^5 * Cp(J(rpm))
        J(rpm) = V / (n * D)
        n = rpm / 60

    Capping the requested shaft power at this value helps keep the
    inverse RPM solve bracketed within the configured RPM interval.
    """
    Vk = float(max(0.0, V_ms))
    rhok = float(max(1e-6, rho))
    Dp = float(Dp)

    n = max(1e-3, float(rpm_safe) / 60.0)

    J_raw = Vk / max(1e-6, n * Dp)
    J = float(
        np.clip(
            J_raw,
            float(J_min),
            float(J_max),
        )
    )

    Cp = float(Cp_func(J))
    Cp = max(1e-6, Cp)

    return float(rhok * (n**3) * (Dp**5) * Cp)


def solve_rpm_from_power_bisect_scalar(
    V_ms: float,
    rho: float,
    P_shaft_W: float,
    Cp_func: Callable[[float], float],
    Dp: float,
    J_min: float,
    J_max: float,
    rpm_lo: float,
    rpm_hi: float,
    P_cap_W: float,
    iters: int = 28,
) -> Tuple[float, bool]:
    """Solve for RPM corresponding to a target shaft power by bisection.

    The power relation is:

        P(rpm) = rho * n^3 * D^5 * Cp(J(rpm))
        J(rpm) = V / (n * D)

    The solution is searched over ``[rpm_lo, rpm_hi]``. ``P_cap_W``
    limits the requested shaft power before solving.

    Returns:
        A tuple containing the estimated RPM and ``bracket_ok`` flag.
        ``bracket_ok`` is ``True`` when the target power lies between
        the powers evaluated at the two RPM bounds. If the target is
        outside the bracket, the nearer endpoint is returned with
        ``bracket_ok=False``.
    """
    Vk = float(max(0.0, V_ms))
    rhok = float(max(1e-6, rho))
    Dp = float(Dp)

    # Clamp the requested shaft power to the configured safety bound.
    Pk = float(
        np.clip(
            P_shaft_W,
            0.0,
            float(P_cap_W),
        )
    )

    # Return the minimum RPM at very low power or airspeed.
    if Pk < 50.0 or Vk < 1.0:
        return float(rpm_lo), True

    def P_of_rpm(rpm: float) -> float:
        n = max(1e-3, float(rpm) / 60.0)
        J_raw = Vk / max(1e-6, n * Dp)
        J = float(
            np.clip(
                J_raw,
                float(J_min),
                float(J_max),
            )
        )
        Cp = float(Cp_func(J))
        Cp = max(1e-6, Cp)

        return rhok * (n**3) * (Dp**5) * Cp

    lo = float(rpm_lo)
    hi = float(rpm_hi)

    P_lo = P_of_rpm(lo)
    P_hi = P_of_rpm(hi)

    # If the target is outside the bracket, return the nearer endpoint.
    if not (P_lo <= Pk <= P_hi):
        rpm_best = (
            lo
            if abs(Pk - P_lo) < abs(Pk - P_hi)
            else hi
        )
        return float(rpm_best), False

    for _ in range(int(iters)):
        mid = 0.5 * (lo + hi)
        P_mid = P_of_rpm(mid)

        if P_mid < Pk:
            lo = mid
        else:
            hi = mid

    return float(0.5 * (lo + hi)), True
