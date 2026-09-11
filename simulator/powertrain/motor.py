# powertrain/motor.py
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class MotorModel:
    """
    모터+인버터(ESC 포함 가능) 효율 모델.

    - 여기서는 가장 단순하게 "상수 효율"로 모델링한다.
    - eta: (0, 1] 범위의 효율
    """
    eta: float = 0.92  # 모터+인버터 효율 (전기 -> 샤프트)

    def __post_init__(self):
        if not (0.0 < float(self.eta) <= 1.0):
            raise ValueError(f"MotorModel.eta must be in (0, 1]. got {self.eta}")


def elec_to_shaft_power(P_elec_W: float, eta: float, clamp_nonneg: bool = True) -> float:
    """
    전기 파워 -> 샤프트 파워 변환

    P_shaft = eta * P_elec

    입력:
      - P_elec_W: 배터리/인버터에서 모터로 들어가는 전기 파워 [W]
      - eta: 효율 (0,1]
      - clamp_nonneg: 음수 방지(기본 True)

    출력:
      - P_shaft_W: 축(프로펠러 축)에 전달되는 기계 파워 [W]
    """
    eta = float(eta)
    if eta <= 0.0:
        # 효율이 비정상일 때 안전하게 0 출력
        return 0.0

    P_shaft = eta * float(P_elec_W)
    return max(0.0, P_shaft) if clamp_nonneg else P_shaft


def shaft_to_elec_power(P_shaft_W: float, eta: float, clamp_nonneg: bool = True, eps: float = 1e-6) -> float:
    """
    샤프트 파워 -> 필요한 전기 파워(요구)로 변환

    P_elec = P_shaft / eta

    입력:
      - P_shaft_W: 원하는 축 파워 [W]
      - eta: 효율 (0,1]
      - clamp_nonneg: 음수 방지(기본 True)
      - eps: 0 division 방지용 최소값

    출력:
      - P_elec_W: 배터리에서 요구되는 전기 파워 [W]
    """
    eta = float(eta)
    if eta <= 0.0:
        # 효율이 비정상이면 요구 전기를 크게 만들지 않도록 안전하게 0 처리
        return 0.0

    P_elec = float(P_shaft_W) / max(eps, eta)
    return max(0.0, P_elec) if clamp_nonneg else P_elec
