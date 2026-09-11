# guidance.py
from __future__ import annotations
from math import atan2, sqrt
import numpy as np

from ..config import SimConfig
from ..schemas import State, GuidanceOut
from .utils import clamp


def compute_bearing_beta(x: float, y: float, x_wp: float, y_wp: float) -> float:
    """
    현재 위치 (x,y) -> waypoint (x_wp, y_wp) 방향의 heading(beta) [rad]
    """
    return atan2(y_wp - y, x_wp - x)


def guidance_waypoints(
    st: State,
    wps: np.ndarray,
    wp_idx: int,
    cfg: SimConfig,
    t: float,
    t_wps: np.ndarray,
    ) -> GuidanceOut:
    """
    waypoint 추종 규칙:
    - waypoint index는 시간 기반으로 advance
    - 수평 목표는 현재 목표 waypoint를 직접 조준

    입력:
      - st: 현재 상태
      - wps: (M,3) waypoint array [x, y, h]
      - wp_idx: 현재 추종 인덱스
      - cfg: 설정
      - t: 현재 시뮬레이션 시간 [s]
      - t_wps: 각 waypoint가 대응되는 로그 시간(0-start) [s]

    출력:
      - GuidanceOut(h_d, beta_d, wp_idx, dist_to_wp)
    """
    M = int(wps.shape[0])
    wp_idx = int(clamp(wp_idx, 0, M - 1))

    # (1) waypoint index advance
    # 현재 시뮬레이션 시간 t가 다음 waypoint 시간 이상이면 waypoint index를 증가시킨다.
    if wp_idx < M - 1 and float(t) >= float(t_wps[wp_idx + 1]):
        wp_idx += 1

    # (2) 현재 목표 waypoint
    x_wp = float(wps[wp_idx, 0])
    y_wp = float(wps[wp_idx, 1])
    h_wp = float(wps[wp_idx, 2])

    # (3) 목표 헤딩/고도
    beta_d = compute_bearing_beta(st.x, st.y, x_wp, y_wp)
    # 수평 waypoint 추종과 분리해서 고도 목표는 항상 시간기반으로 생성
    h_d = float(np.interp(float(t), np.asarray(t_wps, dtype=float), np.asarray(wps[:, 2], dtype=float)))

    # (4) 종료/진단용 거리(3D)
    dx = x_wp - st.x
    dy = y_wp - st.y
    dz = h_d - st.h
    dist_to_wp = sqrt(dx * dx + dy * dy + dz * dz)

    return GuidanceOut(h_d=h_d, beta_d=beta_d, wp_idx=wp_idx, dist_to_wp=float(dist_to_wp))
