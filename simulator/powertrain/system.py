from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from ..config import SimConfig
from .battery import BatteryECM, make_battery_params_from_dict
from .motor import shaft_to_elec_power, elec_to_shaft_power
from .prop import PropellerModel
from .rpm_solve import power_cap_at_rpm_safe, solve_rpm_from_power_bisect_scalar


@dataclass
class PowertrainState:
    """
    powertrain 내부 상태(배터리) - 시뮬 루프에서 들고 다니는 상태
    """
    soc: float
    temp_c: float
    vp_v: float


@dataclass
class PowertrainOutput:
    """
    powertrain step 결과(로그용 포함)
    """
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
    """
    배터리 + 모터(효율) + 프로펠러 + rpm 역산을 한 덩어리로 묶은 시스템.

    입력:
      - P_shaft_cmd_W : "원하는" 샤프트 파워 명령(컨트롤러 출력)
      - V_ms, alt_abs_m : 현재 비행 상태(추진/밀도/advance ratio에 영향)
      - Tamb_C : 배터리 열 싱크 온도(외기)

    출력:
      - thrust_N : EOM에 넣을 추력
      - (battery state update 포함)
    """

    def __init__(
        self,
        cfg: SimConfig,
        rho_func: Callable[[float, float], float],  # (t_now, alt_abs_m)->rho
        prop: PropellerModel,
        batt: Optional[BatteryECM] = None,
    ):

        self.cfg = cfg
        self.rho_func = rho_func
        self.prop = prop
        self.batt = batt if batt is not None else BatteryECM(
            params=make_battery_params_from_dict(cfg.PARAMS),
        )

        # prop surrogate 내부 보간함수 접근용
        self.Cp_func = prop.Cp_func
        self.Dp = prop.Dp
        self.J_min = prop.J_min
        self.J_max = prop.J_max

        # 시뮬 시작 시점 기준 cold severity reference
        self._cold_ref_initialized = False
        self._init_temp_ref_C = float(cfg.INIT_TEMP_C)
        self._cold_metric_ref_C = float(cfg.INIT_TEMP_C)

    def _maybe_init_cold_refs(self, Tamb_C: float):
        if not self._cold_ref_initialized:
            self._init_temp_ref_C = float(self.cfg.INIT_TEMP_C)
            self._cold_metric_ref_C = float(min(self._init_temp_ref_C, float(Tamb_C)))
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

        cfg = self.cfg
        self._maybe_init_cold_refs(Tamb_C)

        p_max_use = float(cfg.P_MAX_W if P_max_W is None else P_max_W)
        p_max_use = float(np.clip(p_max_use, cfg.P_MIN_W, cfg.P_MTOP_W))

        # ------------------------------------------------------------
        # (1) 요구 샤프트 파워 명령 clip
        # ------------------------------------------------------------
        P_shaft_cmd_W = float(np.clip(P_shaft_cmd_W, cfg.P_MIN_W, p_max_use))

        # ------------------------------------------------------------
        # (2) 샤프트 파워 -> 전기 파워 요구
        # ------------------------------------------------------------
        P_elec_demand_W = shaft_to_elec_power(P_shaft_cmd_W, cfg.EFF_MOTOR_INV)

        # ------------------------------------------------------------
        # (3) 배터리 step: 기존 방식 유지
        #     요구 전기파워 -> 실제 공급 전기파워 / 전류 / 상태업데이트
        # ------------------------------------------------------------
        soc_next, temp_next, vp_next, Vdc, I_batt, P_elec_deliv = self.batt.step_power(
            soc_k=st.soc,
            temp_k=st.temp_c,
            vp_k=st.vp_v,
            P_elec_demand_W=P_elec_demand_W,
            T_amb_C=float(Tamb_C),
            dt=float(cfg.DT_SIM),
            init_temp_ref=float(self._init_temp_ref_C),
            cold_metric_ref=float(self._cold_metric_ref_C),
        )

        # ------------------------------------------------------------
        # (4) 배터리 출력 전기파워 -> 실제 샤프트 파워
        # ------------------------------------------------------------
        P_shaft_deliv_W = elec_to_shaft_power(P_elec_deliv, cfg.EFF_MOTOR_INV)

        # ------------------------------------------------------------
        # (5) 현재 rho 계산
        # ------------------------------------------------------------
        rho_now = float(self.rho_func(float(t_now), float(alt_abs_m)))

        # ------------------------------------------------------------
        # (6) RPM_SAFE에서 가능한 최대 파워로 캡
        # ------------------------------------------------------------
        P_cap_rpm = power_cap_at_rpm_safe(
            V_ms=float(V_ms),
            rho=rho_now,
            Cp_func=self.Cp_func,
            Dp=self.Dp,
            J_min=self.J_min,
            J_max=self.J_max,
            rpm_safe=float(cfg.RPM_SAFE),
        )
        P_shaft_used = float(np.clip(P_shaft_deliv_W, 0.0, min(P_cap_rpm, cfg.P_MTOP_W)))

        # ------------------------------------------------------------
        # (7) P_shaft_used를 만족하는 rpm 역산 (bisection)
        # ------------------------------------------------------------
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
        rpm = float(np.clip(rpm, 0.0, cfg.RPM_SAFE))

        # ------------------------------------------------------------
        # (8) rpm에서 (P_prop, Thrust, J) 계산
        # ------------------------------------------------------------
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
