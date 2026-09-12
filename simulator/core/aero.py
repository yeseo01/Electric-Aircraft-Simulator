# aero.py
from __future__ import annotations
from typing import Tuple
from math import cos
import numpy as np

from ..config import SimConfig
from ..schemas import State, ParamsPM


def aero_from_CL(
    V: float,
    rho: float,
    p: ParamsPM,
    CL: float,
    thrust_N: float,
    cfg: SimConfig,
) -> Tuple[float, float, float, float]:

    """
    단순 공력:
      CD = CD0 + K*CL^2
      L  = q S CL
      D  = q S CD

    입력:
      - V: 속도 [m/s]
      - rho: 공기 밀도 [kg/m^3]
      - p: point-mass params (S 사용)
      - CL: 양력계수
      - thrust_N: 추진 블록에서 계산된 추력 [N]
      - cfg: SimConfig (CD0, K 등 사용)

    출력:
      - L [N], D [N], T [N], CD [-]
    """
    V = float(max(1e-3, V))
    rho = float(max(1e-6, rho))

    q = 0.5 * rho * V * V
    CD  = float(max(1e-4, cfg.CD0 + cfg.K * (CL ** 2)))

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
    
    """
    gamma가 gamma_cmd를 1차로 따라가게 만들기 위해 필요한 CL을 스케줄링한다.

    아이디어:
      - 원하는 gamma_dot: (gamma_cmd - gamma) / TAU_GAMMA
      - point-mass (단순) 관계:
          gamma_dot = (L cos(mu))/(mV) - (g/V) cos(gamma)

      -> gamma_dot를 gamma_dot_cmd에 맞추도록 L_req 역산
      -> CL_req = L_req / (q S)

    주의:
      - 엄밀한 trim이 아니라 안정적인 추종을 위한 제어용 스케줄링
      - CL은 cfg.CL_MIN/CL_MAX로 제한
    """
    V = float(max(1e-3, st.V))
    rho = float(max(1e-6, p.rho))
    q = 0.5 * rho * V * V

    tau = float(max(1e-3, cfg.TAU_GAMMA))
    gamma_dot_cmd = (float(gamma_cmd) - float(st.gamma)) / tau

    cos_mu = max(1e-3, cos(float(mu)))

    # L_req = mV( gamma_dot_cmd + (g/V)cos(gamma) ) / cos(mu)
    L_req = p.m * V * (gamma_dot_cmd + (p.g / V) * cos(float(st.gamma))) / cos_mu

    denom = max(1e-6, q * p.S)
    CL_req = float(L_req / denom)
    CL_req = float(np.clip(CL_req, cfg.CL_MIN, cfg.CL_MAX))

    CD_req = float(cfg.CD0 + cfg.K * (CL_req ** 2))
    return CL_req, CD_req
