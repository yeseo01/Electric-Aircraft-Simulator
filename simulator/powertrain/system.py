"""Integrated battery, motor, propeller, and RPM-solver powertrain model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from ..config import SimConfig
from .battery import BatteryECM, make_battery_params_from_dict
from .motor import elec_to_shaft_power, shaft_to_elec_power
from .prop import PropellerModel
from .rpm_solve import (
    power_cap_at_rpm_safe,
    solve_rpm_from_power_bisect_scalar,
)


@dataclass
class PowertrainState:
    """Internal battery state carried between powertrain simulation steps."""

    soc: float
    temp_c: float
    vp_v: float


@dataclass
class PowertrainOutput:
    """Outputs produced by one powertrain simulation step."""

    # Propulsion outputs
    thrust_N: float
    rpm: float
    P_prop_W: float
    J: float
    bracket_ok: bool

    # Power signals
    P_shaft_cmd_W: float
    P_elec_demand_W: float
    P_elec_deliv_W: float
    P_shaft_deliv_W: float

    # Battery outputs
    Vdc_V: float
    I_batt_A: float
    soc_next: float
    temp_next_c: float
    vp_next_v: float


class Powertrain:
    """Couple the battery, motor-efficiency, propeller, and RPM models.

    The system receives a requested shaft-power command together with
    the current flight and ambient conditions. It advances the battery
    state, determines deliverable shaft power, solves for propeller RPM,
    and returns the resulting thrust and powertrain state.

    The internal motor, battery, propeller, and RPM-solver models are
    delegated to their respective components.
    """

    def __init__(
        self,
        cfg: SimConfig,
        rho_func: Callable[[float, float], float],
        prop: PropellerModel,
        batt: Optional[BatteryECM] = None,
    ) -> None:
        self.cfg = cfg
        self.rho_func = rho_func
        self.prop = prop
        self.batt = batt if batt is not None else BatteryECM(
            params=make_battery_params_from_dict(cfg.PARAMS),
        )

        # Expose propeller-surrogate parameters used by the RPM solver.
        self.Cp_func = prop.Cp_func
        self.Dp = prop.Dp
        self.J_min = prop.J_min
        self.J_max = prop.J_max

        # Cold-condition references are initialized at the start of simulation.
        self._cold_ref_initialized = False
        self._init_temp_ref_C = float(cfg.INIT_TEMP_C)
        self._cold_metric_ref_C = float(cfg.INIT_TEMP_C)

    def _maybe_init_cold_refs(self, Tamb_C: float) -> None:
        """Initialize cold-condition reference temperatures once."""
        if not self._cold_ref_initialized:
            self._init_temp_ref_C = float(self.cfg.INIT_TEMP_C)
            self._cold_metric_ref_C = float(
                min(
                    self._init_temp_ref_C,
                    float(Tamb_C),
                )
            )
            self._cold_ref_initialized = True

    def step(
        self,
        t_now: float,
        V_ms: float,
        alt_abs_m: float,
        Tamb_C: float,
        P_shaft_cmd_W: float,
        st: PowertrainState,
        P_max_W: float | None = None,
    ) -> PowertrainOutput:
        """Advance the coupled powertrain model by one simulation step."""
        cfg = self.cfg
        self._maybe_init_cold_refs(Tamb_C)

        p_max_use = float(
            cfg.P_MAX_W
            if P_max_W is None
            else P_max_W
        )
        p_max_use = float(
            np.clip(
                p_max_use,
                cfg.P_MIN_W,
                cfg.P_MTOP_W,
            )
        )

        # Clamp the requested shaft-power command.
        P_shaft_cmd_W = float(
            np.clip(
                P_shaft_cmd_W,
                cfg.P_MIN_W,
                p_max_use,
            )
        )

        # Convert requested shaft power to electrical-power demand.
        P_elec_demand_W = shaft_to_elec_power(
            P_shaft_cmd_W,
            cfg.EFF_MOTOR_INV,
        )

        # Advance the battery model using the requested electrical power.
        (
            soc_next,
            temp_next,
            vp_next,
            Vdc,
            I_batt,
            P_elec_deliv,
        ) = self.batt.step_power(
            soc_k=st.soc,
            temp_k=st.temp_c,
            vp_k=st.vp_v,
            P_elec_demand_W=P_elec_demand_W,
            T_amb_C=float(Tamb_C),
            dt=float(cfg.DT_SIM),
            init_temp_ref=float(self._init_temp_ref_C),
            cold_metric_ref=float(self._cold_metric_ref_C),
        )

        # Convert delivered electrical power back to delivered shaft power.
        P_shaft_deliv_W = elec_to_shaft_power(
            P_elec_deliv,
            cfg.EFF_MOTOR_INV,
        )

        # Evaluate air density at the current simulation state.
        rho_now = float(
            self.rho_func(
                float(t_now),
                float(alt_abs_m),
            )
        )

        # Limit shaft power to the amount supported at the safe RPM bound.
        P_cap_rpm = power_cap_at_rpm_safe(
            V_ms=float(V_ms),
            rho=rho_now,
            Cp_func=self.Cp_func,
            Dp=self.Dp,
            J_min=self.J_min,
            J_max=self.J_max,
            rpm_safe=float(cfg.RPM_SAFE),
        )
        P_shaft_used = float(
            np.clip(
                P_shaft_deliv_W,
                0.0,
                min(P_cap_rpm, cfg.P_MTOP_W),
            )
        )

        # Solve for the RPM corresponding to the usable shaft power.
        rpm, ok = solve_rpm_from_power_bisect_scalar(
            V_ms=float(V_ms),
            rho=rho_now,
            P_shaft_W=P_shaft_used,
            Cp_func=self.Cp_func,
            Dp=self.Dp,
            J_min=self.J_min,
            J_max=self.J_max,
            rpm_lo=float(cfg.RPM_SOLVE_MIN),
            rpm_hi=float(cfg.RPM_SAFE),
            P_cap_W=float(cfg.P_MTOP_W),
            iters=28,
        )
        rpm = float(
            np.clip(
                rpm,
                0.0,
                cfg.RPM_SAFE,
            )
        )

        # Evaluate propeller power, thrust, and advance ratio at the solved RPM.
        P_prop_W, thrust_N, J = self.prop.evaluate(
            rpm=rpm,
            V_ms=float(V_ms),
            rho=rho_now,
        )

        return PowertrainOutput(
            thrust_N=float(thrust_N),
            rpm=float(rpm),
            P_prop_W=float(P_prop_W),
            J=float(J),
            bracket_ok=bool(ok),

            P_shaft_cmd_W=float(P_shaft_cmd_W),
            P_elec_demand_W=float(P_elec_demand_W),
            P_elec_deliv_W=float(P_elec_deliv),
            P_shaft_deliv_W=float(P_shaft_deliv_W),

            Vdc_V=float(Vdc),
            I_batt_A=float(I_batt),
            soc_next=float(soc_next),
            temp_next_c=float(temp_next),
            vp_next_v=float(vp_next),
        )
