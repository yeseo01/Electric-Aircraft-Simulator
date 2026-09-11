# atmosphere.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Union
import numpy as np

NumberOrArray = Union[float, int, np.ndarray]


@dataclass(frozen=True)
class ISAParams:
    """
    ISA(International Standard Atmosphere) 대류권(0~11km) 근사 파라미터
    """
    g0: float = 9.80665          # 중력가속도 [m/s^2]
    R_air: float = 287.05287     # 공기 기체상수 [J/(kg*K)]
    p0_std: float = 101325.0     # 해수면 표준 기압 [Pa]
    T0_std: float = 288.15       # 해수면 표준 온도 [K]
    L: float = 0.0065            # 온도감율 [K/m] (대류권)


def isa_pressure_from_alt(h_m: NumberOrArray, isa: ISAParams = ISAParams()) -> NumberOrArray:
    """
    ISA(대류권) 근사로 고도 -> 정압 p 계산. (스칼라/배열 겸용)

    입력:
      - h_m: 고도 [m] (0~11km 클립)
    출력:
      - p: 정압 [Pa] (입력 타입에 맞게 스칼라 또는 np.ndarray)
    """
    h = np.clip(np.asarray(h_m, dtype=float), 0.0, 11000.0)
    expo = isa.g0 / (isa.R_air * isa.L)
    p = isa.p0_std * (1.0 - isa.L * h / isa.T0_std) ** expo
    return float(p) if np.ndim(p) == 0 else p


def compute_rho(alt_m: NumberOrArray,
                oat_c: NumberOrArray,
                isa: ISAParams = ISAParams(),
                T_clip_K: tuple[float, float] = (200.0, 330.0)) -> NumberOrArray:
    """
    밀도 rho 계산: rho = p(alt) / (R * T)  (스칼라/배열 겸용)

    - p(alt): ISA(대류권) 근사
    - T: OAT(외기온도) 사용 (K로 변환 후 clip)

    입력:
      - alt_m: 절대고도 [m]
      - oat_c: 외기온도 [°C]
    출력:
      - rho: 공기밀도 [kg/m^3] (입력 타입에 맞게 스칼라 또는 np.ndarray)

    주의:
      alt_m과 oat_c가 배열이면, numpy broadcasting 규칙에 따라 계산됨.
    """
    p = isa_pressure_from_alt(alt_m, isa=isa)

    T = np.asarray(oat_c, dtype=float) + 273.15
    T = np.clip(T, T_clip_K[0], T_clip_K[1])

    # p가 스칼라면 float, 배열이면 ndarray일 수 있으니 numpy로 통일해 계산
    rho = np.asarray(p, dtype=float) / (isa.R_air * T)
    return float(rho) if np.ndim(rho) == 0 else rho
