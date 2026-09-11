# powertrain/rpm_solve.py
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
    """
    RPM_SAFE에서 만들 수 있는 최대 샤프트 파워 P_cap을 계산한다.

    P(rpm) = rho * n^3 * D^5 * Cp(J(rpm))
    J(rpm) = V / (n*D), n=rpm/60

    목적:
      - P_cmd를 이 값으로 캡하면,
        rpm 역산(bisection)이 [RPM_SOLVE_MIN, RPM_SAFE]에서 bracket 되도록 보장하는 데 유리.
    """
    Vk = float(max(0.0, V_ms))
    rhok = float(max(1e-6, rho))
    Dp = float(Dp)

    n = max(1e-3, float(rpm_safe) / 60.0)

    J_raw = Vk / max(1e-6, n * Dp)
    J = float(np.clip(J_raw, float(J_min), float(J_max)))

    Cp = float(Cp_func(J))
    Cp = max(1e-6, Cp)

    return float(rhok * (n ** 3) * (Dp ** 5) * Cp)


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
    """
    목표 샤프트 파워 P_shaft_W를 만족하는 rpm을 bisection으로 역산한다.

    정의:
      P(rpm) = rho * n^3 * D^5 * Cp(J(rpm))
      J(rpm) = V / (n*D)

    입력:
      - rpm_lo ~ rpm_hi 구간에서 해를 찾는다 (보통 [RPM_SOLVE_MIN, RPM_SAFE])
      - P_cap_W: 안전 상한(예: MTOP), P_shaft_W가 너무 큰 경우 클립/진단용

    반환:
      - rpm 추정값
      - bracket_ok: True이면 P_lo <= P_target <= P_hi 를 만족(정상 bisection)
                   False이면 bracket 실패(해가 구간 밖), 가까운 끝점을 반환
    """
    Vk = float(max(0.0, V_ms))
    rhok = float(max(1e-6, rho))
    Dp = float(Dp)

    # 파워 입력 클립 (안전)
    Pk = float(np.clip(P_shaft_W, 0.0, float(P_cap_W)))

    # 저속/저파워에서는 최소 rpm 반환 (발산 방지)
    if Pk < 50.0 or Vk < 1.0:
        return float(rpm_lo), True

    def P_of_rpm(rpm: float) -> float:
        n = max(1e-3, float(rpm) / 60.0)
        J_raw = Vk / max(1e-6, n * Dp)
        J = float(np.clip(J_raw, float(J_min), float(J_max)))
        Cp = float(Cp_func(J))
        Cp = max(1e-6, Cp)
        return rhok * (n ** 3) * (Dp ** 5) * Cp

    lo = float(rpm_lo)
    hi = float(rpm_hi)

    P_lo = P_of_rpm(lo)
    P_hi = P_of_rpm(hi)

    # bracket 실패 시: 더 가까운 끝점을 반환
    if not (P_lo <= Pk <= P_hi):
        rpm_best = lo if abs(Pk - P_lo) < abs(Pk - P_hi) else hi
        return float(rpm_best), False

    for _ in range(int(iters)):
        mid = 0.5 * (lo + hi)
        P_mid = P_of_rpm(mid)

        if P_mid < Pk:
            lo = mid
        else:
            hi = mid

    return float(0.5 * (lo + hi)), True
