"""Flight-control and power-control utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..config import SimConfig
from ..schemas import ParamsPM, State
from .utils import clamp, deg2rad, wrap_to_pi


def control_mu(
    st: State,
    beta_d: float,
    p: ParamsPM,
    cfg: SimConfig,
) -> float:
    """Compute the bank-angle command from heading error.

    The wrapped heading error is converted to a bank-angle command using
    a first-order heading-response approximation:

        mu_cmd = (V / (g * TAU_HEADING)) * e_beta

    The resulting command is limited by ``MU_MAX_DEG``.
    """
    e_beta = wrap_to_pi(float(beta_d) - float(st.beta))
    mu_cmd = (
        float(st.V)
        / (p.g * float(cfg.TAU_HEADING))
        * e_beta
    )

    mu_max = deg2rad(float(cfg.MU_MAX_DEG))
    return float(clamp(mu_cmd, -mu_max, mu_max))


def control_gamma_cmd(
    st: State,
    h_d: float,
    cfg: SimConfig,
) -> float:
    """Compute the flight-path-angle command from altitude error.

    The altitude error is converted to a flight-path-angle command:

        gamma_cmd = GAMMA_KP * (h_d - h)

    The command is limited by ``GAMMA_MAX_DEG`` and is subsequently
    tracked by the lift-coefficient scheduling logic.
    """
    h_err = float(h_d) - float(st.h)

    gamma_max = deg2rad(float(cfg.GAMMA_MAX_DEG))
    gamma_cmd = float(cfg.GAMMA_KP) * h_err

    return float(clamp(gamma_cmd, -gamma_max, gamma_max))


@dataclass
class PowerController:
    """Airspeed-error-based shaft-power controller with low-pass filtering.

    The controller computes a raw shaft-power command from target-airspeed
    error and then applies a first-order low-pass filter.

    ``P_f`` stores the filter state between simulation steps.
    """

    cfg: SimConfig
    P_f: Optional[float] = None

    def __post_init__(self) -> None:
        if self.P_f is None:
            self.P_f = float(self.cfg.P_BASE_W)

    def __call__(
        self,
        t_now: float,
        V_ms: float,
        alt_abs_m: float,
        V_ref_ms: Optional[float] = None,
        KP_P_override: Optional[float] = None,
        P_base_W_override: Optional[float] = None,
    ) -> float:
        """Compute the filtered shaft-power command.

        The control law is:

            P_raw = P_base + KP * (V_ref - V)
            P_f = (1 - a) * P_f + a * P_raw

        where ``a = DT_SIM / TAU_P`` and is clipped to [0, 1].

        ``t_now`` and ``alt_abs_m`` are retained as part of the controller
        interface but are not used by the current control law.
        """
        cfg = self.cfg

        # Apply phase-specific overrides when provided.
        V_ref = float(
            cfg.V_REF_MS if V_ref_ms is None else V_ref_ms
        )
        KP_P_val = float(
            cfg.KP_P if KP_P_override is None else KP_P_override
        )
        P_base = float(
            cfg.P_BASE_W
            if P_base_W_override is None
            else P_base_W_override
        )

        # Compute the raw speed-controller power command.
        P_raw = P_base + KP_P_val * (V_ref - float(V_ms))
        P_raw = float(
            clamp(
                P_raw,
                float(cfg.P_MIN_W),
                float(cfg.P_MAX_W),
            )
        )

        # Apply the first-order low-pass filter.
        a = float(cfg.DT_SIM) / max(
            1e-6,
            float(cfg.TAU_P),
        )
        a = float(clamp(a, 0.0, 1.0))

        self.P_f = (
            (1.0 - a) * float(self.P_f)
            + a * P_raw
        )
        return float(self.P_f)
