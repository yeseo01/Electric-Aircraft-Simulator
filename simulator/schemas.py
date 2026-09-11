# datatypes.py
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass
class ParamsPM:
    """
    point-mass 방정식에 필요한 최소 파라미터.
    - rho는 시뮬 루프에서 매 스텝 업데이트될 수 있음
    """
    g: float          # 중력가속도 [m/s^2]
    rho: float        # 공기 밀도 [kg/m^3]
    m: float          # 질량 [kg]
    S: float          # 날개면적 [m^2]
    dt: float         # 적분 timestep [s]


@dataclass
class State:
    """
    시뮬레이션 상태벡터:
      x,y,h : ENU 위치 [m]
      V     : 속도 크기 [m/s]
      beta  : heading [rad]
      gamma : flight-path angle [rad]
    """
    x: float
    y: float
    h: float
    V: float
    beta: float
    gamma: float

    def vec(self) -> np.ndarray:
        """RK 적분을 위한 ndarray 변환"""
        return np.array([self.x, self.y, self.h, self.V, self.beta, self.gamma], dtype=float)

    @staticmethod
    def from_vec(v: np.ndarray) -> "State":
        """ndarray -> State"""
        return State(
            x=float(v[0]),
            y=float(v[1]),
            h=float(v[2]),
            V=float(v[3]),
            beta=float(v[4]),
            gamma=float(v[5]),
            )


@dataclass
class GuidanceOut:
    """
    guidance 출력:
      h_d    : 목표 고도
      beta_d : 목표 진행 방향(헤딩)
      wp_idx : 현재 추종 waypoint 인덱스
      dist_to_wp : 현재 위치와 waypoint 수평거리
    """
    h_d: float
    beta_d: float
    wp_idx: int
    dist_to_wp: float


@dataclass
class FlightScenario:
    """
    시뮬레이터 실행 입력 묶음.

    첫 제품화 단계에서는 CSV 기반 시나리오를 기본값으로 사용한다.
    나중에 UI에서 초기 위치, 목적지, 위험요소를 입력받으면 이 구조를 확장한다.
    """
    name: str = "default"
    flight_csv_path: str | None = None


@dataclass
class TelemetryFrame:
    """
    화면/서버로 한 step씩 전달할 시뮬레이션 프레임.
    """
    timestamp: float
    x_m: float
    y_m: float
    altitude_m: float
    airspeed_mps: float
    heading_rad: float
    flight_path_angle_rad: float
    soc: float
    voltage_v: float
    current_a: float
    battery_temperature_c: float
    rpm: float
    thrust_n: float
    phase: str
