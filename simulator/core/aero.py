"""Aerodynamic-force calculations and lift-coefficient scheduling."""

from __future__ import annotations

from math import cos
from typing import Tuple

import numpy as np

from ..config import SimConfig
from ..schemas import ParamsPM, State


def aero_from_CL(
    V: float,
    rho: float,
    p: ParamsPM,
    CL: float,
    thrust_N: float,
    cfg: SimConfig,
) -> Tuple[float, float, float, float]:
    """Compute aerodynamic forces from a specified lift coefficient.

    The aerodynamic model uses a simple parabolic drag polar:

        CD = CD0 + K * CL^2
        L = q * S * CL
        D = q * S * CD

    where ``q`` is dynamic pressure.

    Returns:
        Lift [N], drag [N], thrust [N], and drag coefficient [-].
    """
    V = float(max(1e-3, V))
    rho = float(max(1e-6, rho))

    q = 0.5 * rho * V * V
    CD = float(max(1e-4, cfg.CD0 + cfg.K * (CL ** 2)))

    L = q * p.S * float(CL)
    D = q * p.S * CD
    T = float(max(0.0, thrust_N))

    return float(L), float(D), float(T), float(CD)


def schedule_CL_for_gamma(
    st: State,
    mu: float,
    gamma_cmd: float,
    p: ParamsPM,
    cfg: SimConfig,
) -> Tuple[float, float]:
    """Schedule lift coefficient to track a flight-path-angle command.

    A first-order tracking target is used:

        gamma_dot_cmd = (gamma_cmd - gamma) / TAU_GAMMA

    With the point-mass relation

        gamma_dot = L * cos(mu) / (m * V) - g * cos(gamma) / V

    the required lift is solved and converted to ``CL``. The resulting
    coefficient is limited to ``CL_MIN`` and ``CL_MAX``.

    This is a control-oriented scheduling approximation rather than a
    full aerodynamic trim solution.
    """
    V = float(max(1e-3, st.V))
    rho = float(max(1e-6, p.rho))
    q = 0.5 * rho * V * V

    tau = float(max(1e-3, cfg.TAU_GAMMA))
    gamma_dot_cmd = (
        float(gamma_cmd) - float(st.gamma)
    ) / tau

    cos_mu = max(1e-3, cos(float(mu)))

    L_req = (
        p.m
        * V
        * (
            gamma_dot_cmd
            + (p.g / V) * cos(float(st.gamma))
        )
        / cos_mu
    )

    denom = max(1e-6, q * p.S)
    CL_req = float(L_req / denom)
    CL_req = float(
        np.clip(
            CL_req,
            cfg.CL_MIN,
            cfg.CL_MAX,
        )
    )

    CD_req = float(
        cfg.CD0 + cfg.K * (CL_req ** 2)
    )

    return CL_req, CD_req
