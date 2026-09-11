# io_flight.py
from __future__ import annotations
from typing import Dict, Tuple
import numpy as np
import pandas as pd

from ..config import SimConfig
from .frames import lla_series_to_enu


def load_flight_csv(path: str) -> Dict[str, np.ndarray]:
    """
    비행 로그 CSV에서 필요한 컬럼을 로드한다.
    - 여기서는 아래 컬럼들이 "무조건 존재"한다고 가정한다.
    - 하나라도 없으면 KeyError로 즉시 실패(데이터 문제를 빨리 발견할 수 있음).

    필수 컬럼:
      time(ms), LAT, LNG, PRESSURE_ALT,
      OAT, motor power, motor rpm, IAS,
      bat 1 soc, bat 1 voltage, bat 1 current, bat 1 avg cell temp
    """
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()

    head_cut = 0  # 앞에서 버릴 행 개수
    tail_cut = 0     # 뒤에서 버릴 행 개수 (0이면 자르지 않음)

    if tail_cut > 0:
        df = df.iloc[head_cut:-tail_cut].reset_index(drop=True)
    else:
        df = df.iloc[head_cut:].reset_index(drop=True)

    required = [
        "time(ms)", "LAT", "LNG", "PRESSURE_ALT",
        "OAT", "motor power", "motor rpm", "IAS",
        "bat 1 soc", "bat 1 voltage", "bat 1 current", "bat 2 current","bat 1 avg cell temp",
        ]

    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"CSV에 필수 컬럼이 없습니다: {missing}")

    # time(ms) -> seconds
    t = np.asarray(df["time(ms)"], dtype=float) * 1e-3

    out: Dict[str, np.ndarray] = {
        "t": t,
        "lat": np.asarray(df["LAT"], dtype=float),
        "lon": np.asarray(df["LNG"], dtype=float),
        "alt": np.asarray(df["PRESSURE_ALT"], dtype=float),

        "OAT": np.asarray(df["OAT"], dtype=float),

        # motor power는 kW -> W 변환
        "P_meas_W": np.asarray(df["motor power"], dtype=float) * 1000.0,
        "RPM_log": np.asarray(df["motor rpm"], dtype=float),
        "IAS": np.asarray(df["IAS"], dtype=float),

        "bat_soc_pct": np.asarray(df["bat 1 soc"], dtype=float),
        "bat_v": np.asarray(df["bat 1 voltage"], dtype=float),
        "bat_i": np.asarray(df["bat 1 current"]+df["bat 2 current"], dtype=float),
        "bat_t": np.asarray(df["bat 1 avg cell temp"], dtype=float),
        }

    # 선택 컬럼: phase (있는 경우에만 사용)
    if "phase" in df.columns:
        # 문자열 phase를 그대로 보관 (구간별 다운샘플 등에 활용)
        out["phase"] = df["phase"].astype(str).to_numpy()

    return out



def make_waypoints_from_csv(
    t: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    alt: np.ndarray,
    downsample_sec: float,
    phase: np.ndarray | None = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
    
    """
    로그를 시간 기준으로 downsample하여 waypoint를 생성한다.
    - 기본 간격: downsample_sec
    - phase(ground_roll, climb, cruise, desent)에 따라 간격을 달리 적용

    절차:
      1) time을 0-start로 shift
      2) phase별 간격에 맞춰 index 선택
      3) 선택된 LLA를 ENU로 변환
      4) wps = [x_e, y_n, h_u] 반환 (u는 시작점 대비 상대 up)

    반환:
      - wps: (N,3) ENU waypoint [m]
      - t_d: 다운샘플된 waypoint 시간 [s]
    """
    t = np.asarray(t, dtype=float)
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    alt = np.asarray(alt, dtype=float)

    phase_arr = None
    if phase is not None:
        phase_arr = np.asarray(phase)
        if len(phase_arr) != len(t):
            raise ValueError("phase 길이는 t와 같아야 합니다.")

    # 0-start
    t0 = float(t[0])
    tt = t - t0

    base_dt = float(downsample_sec)
    low_ias_dt = 3.0 * base_dt

    # phase별 기본 간격 설정 (ground_roll, climb, cruise, desent 네 구간 전제)
    def phase_dt(p: str) -> float:
        p = (p or "").lower().strip()
        if p == "ground_roll":
            # 지상 이동은 더 듬성듬성 (기본의 3배)
            return low_ias_dt
        if p == "climb":
            return base_dt
        if p == "cruise":
            return base_dt
        if p == "descent":
            return base_dt
        # 혹시 다른 값이 들어오면 기본 간격 사용
        return base_dt

    # 다운샘플 인덱스 선택 (항상 균일 간격: phase와 무관)
    idx = [0]
    last_t = float(tt[0])
    for i in range(1, len(tt)):
        if float(tt[i]) - last_t >= base_dt:
            idx.append(i)
            last_t = float(tt[i])

    # 마지막 점 포함
    if idx[-1] != len(tt) - 1:
        idx.append(len(tt) - 1)

    idx = np.asarray(idx, dtype=int)

    lat_d = lat[idx]
    lon_d = lon[idx]
    alt_d = alt[idx]
    t_d = tt[idx]

    # LLA -> ENU
    # NOTE:
    #   수평 경로가 길게 펴진 가상 CSV(예: straight_xy)에서는
    #   WGS84 접평면 ENU의 up 성분이 지구 곡률 때문에 크게 음수로 내려갈 수 있다.
    #   시뮬레이터의 고도 추종은 "시작점 대비 상대 압력고도" 해석이 더 자연스러우므로,
    #   waypoint z는 geodetic up 대신 alt-alt0를 사용한다.
    x_enu, y_enu, _ = lla_series_to_enu(lat_d, lon_d, alt_d)
    h_rel = alt_d - float(alt_d[0])
    wps = np.stack([x_enu, y_enu, h_rel], axis=1)

    return wps, t_d


def build_oat_input(
    flight: Dict[str, np.ndarray],
    t_target: np.ndarray,
    cfg: SimConfig,
    ) -> np.ndarray:
    
    """
    외기온도 입력 Tamb(t)을 만든다.
    - cfg.USE_REAL_OAT_FROM_CSV=True면 로그 OAT를 재사용
    - 아니면 DEFAULT_OAT_C로 고정

    처리:
      - NaN/0/비정상 범위(-40~60C) 제거
      - 선형 보간으로 채움
      - t_target 시간축으로 resample
    """
    t_target = np.asarray(t_target, dtype=float)

    if not cfg.USE_REAL_OAT_FROM_CSV:
        return np.full_like(t_target, float(cfg.DEFAULT_OAT_C), dtype=float)

    oat_raw = np.asarray(flight.get("OAT", np.array([])), dtype=float)
    t_raw = np.asarray(flight.get("t", np.array([])), dtype=float)

    if len(oat_raw) < 2 or len(t_raw) < 2:
        return np.full_like(t_target, float(cfg.DEFAULT_OAT_C), dtype=float)

    oat = oat_raw.copy()
    bad = (~np.isfinite(oat)) | (oat == 0) | (oat < -40) | (oat > 60)

    if np.all(bad):
        return np.full_like(t_target, float(cfg.DEFAULT_OAT_C), dtype=float)

    oat[bad] = np.nan
    oat = pd.Series(oat).interpolate(limit_direction="both").to_numpy(dtype=float)

    # time 0-start
    tt = (t_raw - float(t_raw[0])).astype(float)

    # 중복 time 처리 (같은 tt가 여러 번 나오면 평균)
    df = pd.DataFrame({"t": tt, "oat": oat}).groupby("t", as_index=False).mean()
    tt_u = df["t"].to_numpy(dtype=float)
    oat_u = df["oat"].to_numpy(dtype=float)

    # t_target로 resample
    return np.interp(t_target, tt_u, oat_u)


def interp_log_to_sim(t_log: np.ndarray, y_log: np.ndarray, t_sim: np.ndarray) -> np.ndarray:
    """
    로그(y_log)를 시뮬 시간축(t_sim)으로 보간.
    (plotting/비교용)
    """
    t_log = np.asarray(t_log, dtype=float)
    y_log = np.asarray(y_log, dtype=float)
    t_sim = np.asarray(t_sim, dtype=float)

    good = np.isfinite(t_log) & np.isfinite(y_log)
    if np.sum(good) < 2:
        return np.full_like(t_sim, np.nan, dtype=float)

    tt = t_log[good]
    yy = y_log[good]

    order = np.argsort(tt)
    tt = tt[order]
    yy = yy[order]

    df = pd.DataFrame({"t": tt, "y": yy}).groupby("t", as_index=False).mean()
    tt_u = df["t"].to_numpy(dtype=float)
    yy_u = df["y"].to_numpy(dtype=float)

    return np.interp(t_sim, tt_u, yy_u)
