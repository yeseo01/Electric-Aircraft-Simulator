"""Battery equivalent-circuit, thermal, and cold-correction model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
from scipy.interpolate import interp1d


@dataclass(frozen=True)
class BatteryParams:
    """Parameters for the 1RC ECM, thermal model, and cold correction."""

    V_nom: float
    Q_total_Ah: float

    # Electrical baseline
    R_ohm: float
    R1: float
    tau1: float

    # Thermal baseline
    R_eff: float
    A: float
    B: float
    Bias_T: float

    # Cold correction
    T_ref: float
    cold_trigger_temp: float
    cold_full_span: float

    kR_ohm_cold: float
    kR1_cold: float
    kR_eff_cold: float

    cool_scale_cold: float
    alpha_sink_cold: float


def make_battery_params_from_dict(d: Dict[str, float]) -> BatteryParams:
    """Convert the battery parameter dictionary into ``BatteryParams``."""
    return BatteryParams(
        V_nom=float(d["V_nom"]),
        Q_total_Ah=float(d["Q_total_Ah"]),

        R_ohm=float(d["R_ohm"]),
        R1=float(d["R1"]),
        tau1=float(d["tau1"]),

        R_eff=float(d["R_eff"]),
        A=float(d["A"]),
        B=float(d["B"]),
        Bias_T=float(d["Bias_T"]),

        T_ref=float(d["T_ref"]),
        cold_trigger_temp=float(d["cold_trigger_temp"]),
        cold_full_span=float(d["cold_full_span"]),

        kR_ohm_cold=float(d["kR_ohm_cold"]),
        kR1_cold=float(d["kR1_cold"]),
        kR_eff_cold=float(d["kR_eff_cold"]),

        cool_scale_cold=float(d["cool_scale_cold"]),
        alpha_sink_cold=float(d["alpha_sink_cold"]),
    )


class OCVMap:
    """Linear interpolation map from state of charge to open-circuit voltage."""

    def __init__(
        self,
        soc_points: np.ndarray,
        ocv_points: np.ndarray,
    ) -> None:
        soc = np.asarray(soc_points, dtype=float)
        ocv = np.asarray(ocv_points, dtype=float)

        order = np.argsort(soc)
        soc = soc[order]
        ocv = ocv[order]

        # Enforce a monotonically nondecreasing OCV curve.
        ocv = np.maximum.accumulate(ocv)

        self.soc_min = float(np.min(soc))
        self.soc_max = float(np.max(soc))
        self._interp = interp1d(
            soc,
            ocv,
            kind="linear",
            fill_value="extrapolate",
        )

    def __call__(self, soc01: float) -> float:
        s = float(
            np.clip(
                float(soc01),
                self.soc_min,
                self.soc_max,
            )
        )
        return float(self._interp(s))


DEFAULT_SOC_POINTS = np.array(
    [0.39, 0.44, 0.46, 0.54, 0.56, 0.62, 0.68, 0.73, 0.89, 0.98, 1.00],
    dtype=float,
)

DEFAULT_OCV_POINTS = np.array(
    [353.3, 357.55, 359.4, 364.9, 367.1, 368.7, 373.4, 377.8, 389.75, 397.9, 398.78],
    dtype=float,
)


class BatteryECM:
    """1RC equivalent-circuit battery model with thermal and cold corrections.

    State variables:
        - SOC
        - Temperature
        - Polarization voltage ``Vp``

    Terminal voltage:

        Vdc = OCV(SOC) - I * R0 - Vp

    Polarization dynamics:

        dVp/dt = -Vp / tau1 + (R1 / tau1) * I

    Thermal dynamics:

        dT/dt = A * (I^2 * R_eff_k) - B_eff * (T - T_sink)

    ``step_power`` computes battery current from the requested electrical
    power and advances the electrical and thermal states by one time step.
    """

    def __init__(
        self,
        params: BatteryParams,
        ocv_map: OCVMap | None = None,
    ) -> None:
        self.p = params
        self.Q_total_C = float(params.Q_total_Ah) * 3600.0
        self.ocv_map = (
            ocv_map
            if ocv_map is not None
            else OCVMap(DEFAULT_SOC_POINTS, DEFAULT_OCV_POINTS)
        )

    def _cold_factor(self, cold_metric_ref: float) -> float:
        T_trig = float(self.p.cold_trigger_temp)
        T_span = float(max(1e-6, self.p.cold_full_span))
        cf = (T_trig - float(cold_metric_ref)) / T_span
        return float(np.clip(cf, 0.0, 1.0))

    def _effective_params(
        self,
        temp_c: float,
        cold_factor: float,
    ) -> Tuple[float, float, float, float]:
        T_ref = float(self.p.T_ref)

        temp_gain_ohm = (
            1.0
            + cold_factor
            * float(self.p.kR_ohm_cold)
            * (T_ref - temp_c)
        )
        temp_gain_r1 = (
            1.0
            + cold_factor
            * float(self.p.kR1_cold)
            * (T_ref - temp_c)
        )
        temp_gain_eff = (
            1.0
            + cold_factor
            * float(self.p.kR_eff_cold)
            * (T_ref - temp_c)
        )

        temp_gain_ohm = float(np.clip(temp_gain_ohm, 1.0, 2.0))
        temp_gain_r1 = float(np.clip(temp_gain_r1, 1.0, 2.0))
        temp_gain_eff = float(np.clip(temp_gain_eff, 1.0, 2.0))

        R0 = float(self.p.R_ohm) * temp_gain_ohm
        R1 = float(self.p.R1) * temp_gain_r1
        R_eff_k = float(self.p.R_eff) * temp_gain_eff

        B_eff = float(self.p.B) * (
            1.0
            - cold_factor
            * (1.0 - float(self.p.cool_scale_cold))
        )

        return R0, R1, R_eff_k, B_eff

    def step_power(
        self,
        soc_k: float,
        temp_c: float,
        vp_k: float,
        P_elec_demand_W: float,
        T_amb_C: float,
        dt: float,
        init_temp_ref: float,
        cold_metric_ref: float,
    ) -> Tuple[float, float, float, float, float, float]:
        """Advance the battery model by one simulation step.

        Args:
            soc_k: Current state of charge.
            temp_c: Current battery temperature [°C].
            vp_k: Current polarization voltage.
            P_elec_demand_W: Requested electrical power [W].
            T_amb_C: Ambient temperature [°C].
            dt: Simulation time step [s].
            init_temp_ref: Initial battery-pack temperature.
            cold_metric_ref: Reference temperature used for cold correction.

        Returns:
            Tuple containing ``soc_next``, ``temp_next_c``, ``vp_next``,
            terminal voltage, battery current, and delivered electrical power.
        """
        dt = float(max(1e-6, dt))
        soc_k = float(np.clip(float(soc_k), 0.0, 1.0))
        temp_c = float(temp_c)
        vp_k = float(vp_k)
        Tamb = float(T_amb_C)

        Pk = float(max(0.0, P_elec_demand_W))
        ocv = float(self.ocv_map(soc_k))

        cold_factor = self._cold_factor(cold_metric_ref)
        R0, R1, R_eff_k, B_eff = self._effective_params(
            temp_c,
            cold_factor,
        )

        # Effective open-circuit voltage after polarization voltage.
        ocv_eff = float(max(1.0, ocv - vp_k))
        R0 = float(max(1e-9, R0))

        # Maximum electrical power available in this step.
        P_max = (ocv_eff * ocv_eff) / (4.0 * R0)
        P_deliv = float(min(Pk, P_max))

        # Solve R0 * I^2 - ocv_eff * I + P = 0.
        disc = ocv_eff * ocv_eff - 4.0 * R0 * P_deliv
        disc = float(max(0.0, disc))

        # Select the smaller current root.
        I_batt = (
            ocv_eff
            - float(np.sqrt(disc))
        ) / (2.0 * R0)
        I_batt = float(max(0.0, I_batt))

        # Terminal voltage.
        Vdc = ocv - I_batt * R0 - vp_k
        Vdc = float(max(1.0, Vdc))

        # State-of-charge update.
        soc_next = soc_k - (I_batt * dt) / self.Q_total_C
        soc_next = float(np.clip(soc_next, 0.0, 1.0))

        # Polarization-voltage update.
        tau1 = float(max(1e-6, self.p.tau1))
        vp_next = (
            vp_k
            + (
                -vp_k / tau1
                + (R1 / tau1) * I_batt
            )
            * dt
        )

        # Effective thermal sink temperature.
        alpha_sink = (
            1.0
            - cold_factor
            * (1.0 - float(self.p.alpha_sink_cold))
        )
        t_sink = (
            alpha_sink * Tamb
            + (1.0 - alpha_sink) * float(init_temp_ref)
            + float(self.p.Bias_T)
        )

        # Thermal-state update.
        q_gen = (I_batt ** 2) * R_eff_k
        q_cool = temp_c - t_sink
        temp_next_c = (
            temp_c
            + (
                float(self.p.A) * q_gen
                - B_eff * q_cool
            )
            * dt
        )

        return (
            float(soc_next),
            float(temp_next_c),
            float(vp_next),
            float(Vdc),
            float(I_batt),
            float(P_deliv),
        )
