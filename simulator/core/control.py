# control.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from ..config import SimConfig
from ..schemas import State, ParamsPM
from .utils import wrap_to_pi, clamp, deg2rad


def control_mu(st: State, beta_d: float, p: ParamsPM, cfg: SimConfig) -> float:
    """
    heading 제어:
      - heading error -> bank(mu)로 변환
      - 1차 응답 형태 (느슨한 모델)

    mu_cmd = (V / (g * TAU_HEADING)) * e_beta
    """
    e_beta = wrap_to_pi(float(beta_d) - float(st.beta))
    mu_cmd = (float(st.V) / (p.g * float(cfg.TAU_HEADING))) * e_beta

    mu_max = deg2rad(float(cfg.MU_MAX_DEG))
    mu = float(clamp(mu_cmd, -mu_max, mu_max))
    return mu


def control_gamma_cmd(st: State, h_d: float, cfg: SimConfig) -> float:
    """
    고도 제어:
      - 고도 오차 -> gamma_cmd
      - gamma_cmd는 이후 CL 스케줄링에서 따라가도록 한다.

    gamma_cmd = clamp(GAMMA_KP * (h_d - h), ±gamma_max)
    """
    h_err = float(h_d) - float(st.h)

    gamma_max = deg2rad(float(cfg.GAMMA_MAX_DEG))
    gamma_cmd = float(cfg.GAMMA_KP) * h_err
    gamma_cmd = float(clamp(gamma_cmd, -gamma_max, gamma_max))
    return gamma_cmd


@dataclass
class PowerController:
    """
    속도 오차 기반 파워 컨트롤러 (LPF 포함)

    - 입력: (t_now, V_ms, alt_abs_m)
    - 출력: P_cmd_raw_shaft [W] (배터리 제한 전, clip 전/후는 선택)

    내부 상태:
      - P_f : LPF 상태
    """
    cfg: SimConfig
    P_f: Optional[float] = None  # LPF state

    def __post_init__(self):
        # 초기 LPF 상태를 기본 파워로
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
        """
        속도 오차 → 파워 명령 생성 + LPF

        P_raw = P_BASE + KP*(V_ref - V)
        P_f = (1-a)*P_f + a*P_raw, a = DT/TAU_P
        """
        cfg = self.cfg

        # (1) phase별 override가 있으면 적용
        V_ref = float(cfg.V_REF_MS if V_ref_ms is None else V_ref_ms)
        KP_P_val = float(cfg.KP_P if KP_P_override is None else KP_P_override)
        P_base = float(cfg.P_BASE_W if P_base_W_override is None else P_base_W_override)

        # (2) speed controller
        P_raw = P_base + KP_P_val * (V_ref - float(V_ms))
        P_raw = float(clamp(P_raw, float(cfg.P_MIN_W), float(cfg.P_MAX_W)))

        # (3) LPF 
        a = float(cfg.DT_SIM) / max(1e-6, float(cfg.TAU_P))
        a = float(clamp(a, 0.0, 1.0))

        self.P_f = (1.0 - a) * float(self.P_f) + a * P_raw
        return float(self.P_f)
