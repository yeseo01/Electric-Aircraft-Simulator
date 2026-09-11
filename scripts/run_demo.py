# run_demo.py
r'''
실행방법:
    로컬환경에서 sim폴더로 이동후 아래 명령어를 터미널에 순서대로 입력하기
    1) python -m venv .venv
    2) .venv\Scripts\activate (** mac 환경이면 -> source .venv/bin/activate)
    3) pip install -r requirements.txt
    4) python -m scripts.run_demo
'''

from __future__ import annotations
import csv
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from simulator.config import SimConfig
from simulator.schemas import ParamsPM
from simulator.core.atmosphere import compute_rho
from simulator.core.io_flight import load_flight_csv, make_waypoints_from_csv, build_oat_input
from simulator.core.control import PowerController
from simulator.powertrain.prop import PropellerModel
from simulator.powertrain.system import Powertrain
from simulator.core.sim_loop import simulate_flight
from scripts.plot import plot_all


def save_sim_result_csv(path: str, out: dict[str, np.ndarray]) -> None:
    """
    시뮬레이션 결과 dict를 CSV로 저장한다.
    - 1차원 ndarray만 저장 대상에 포함한다.
    - 길이가 다른 항목은 제외하여 CSV 컬럼 길이를 일치시킨다.
    """
    one_dim = {
        key: np.asarray(val)
        for key, val in out.items()
        if isinstance(val, np.ndarray) and np.asarray(val).ndim == 1
    }
    if not one_dim:
        return

    n_rows = min(len(arr) for arr in one_dim.values())
    cols = [key for key, arr in one_dim.items() if len(arr) == n_rows]

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        for i in range(n_rows):
            writer.writerow([one_dim[col][i] for col in cols])


def main():
    # ============================================================
    # (1) 설정 로드
    # ============================================================
    cfg = SimConfig()

    # ============================================================
    # (2) 비행 로그 로드 + 웨이포인트 생성
    # ============================================================
    flight = load_flight_csv(cfg.FLIGHT_CSV_PATH)

    # 로그를 시간 기준으로 다운샘플링하여 ENU 웨이포인트 생성
    wps, twp = make_waypoints_from_csv(
        flight["t"],
        flight["lat"],
        flight["lon"],
        flight["alt"],
        downsample_sec=float(cfg.DOWNSAMPLE_SEC),
        phase=flight.get("phase"),
        )

    # 시뮬레이션 종료 시간 설정
    t_max = float(cfg.TMAX_SCALE) * float(twp[-1])

    # ============================================================
    # (3) 외기 온도 입력 생성 (OAT)
    # ============================================================
    # 시뮬레이션 시간 축 생성
    t_ref = np.arange(0.0, t_max + cfg.DT_SIM, cfg.DT_SIM, dtype=float)

    # 로그 기반 OAT(t) 생성
    OAT_ref = build_oat_input(flight, t_ref, cfg)

    # 로그 첫 고도를 절대 고도 기준점으로 설정
    alt0_abs_m = float(flight["alt"][0])

    # rho 계산 함수 정의 (시간 + 절대고도 기반)
    def rho_func(t_now: float, alt_abs_m: float) -> float:
        oat = float(np.interp(float(t_now), t_ref, OAT_ref))
        return float(compute_rho(float(alt_abs_m), oat))

    # ============================================================
    # (4) Point-mass 파라미터 초기화
    # ============================================================
    p = ParamsPM(
        g=9.80665,
        rho=1.225,                 # 초기 밀도 (루프에서 업데이트됨)
        m=float(cfg.MASS_KG),
        S=float(cfg.S_WING),
        dt=float(cfg.DT_SIM),
        )

    # ============================================================
    # (5) 속도 기반 파워 컨트롤러 생성
    # ============================================================
    power_ctrl = PowerController(cfg)

    # ============================================================
    # (6) 프로펠러 surrogate 로드 + 파워트레인 생성
    # ============================================================
    prop = PropellerModel.load_surrogate(
        npz_path=cfg.PROP_NPZ_PATH,
        eta_clip=cfg.ETA_CLIP,
        eta_fallback=cfg.ETA_FALLBACK_CONST,
        P_cap_W=cfg.P_MTOP_W,
        V_min_for_thrust=cfg.V_MIN_FOR_THRUST,
        )

    powertrain = Powertrain(
        cfg=cfg,
        rho_func=rho_func,
        prop=prop,
        )

    # ============================================================
    # (7) 비행 시뮬레이션 실행
    # ============================================================
    t_log_0 = flight["t"] - float(flight["t"][0])
    phase_log = flight.get("phase")

    out = simulate_flight(
        wps=wps,
        t_wps=twp,
        t_max=t_max,
        p=p,
        cfg=cfg,
        power_ctrl=power_ctrl,
        powertrain=powertrain,
        t_ref=t_ref,
        OAT_ref=OAT_ref,
        alt0_abs_m=alt0_abs_m,
        t_log=t_log_0,
        IAS_log=flight["IAS"],
        phase_log=phase_log,
        )

    # ============================================================
    # (8) 결과 플롯
    # ============================================================
    plot_all(
        wps=wps,
        out=out,
        flight=flight,
        t_ref=t_ref,
        OAT_ref=OAT_ref,
        cfg=cfg,
        )

    # ============================================================
    # (9) 간단 요약 출력
    # ============================================================
    print("\n=== 시뮬레이션 요약 ===")
    print(f"CSV 파일          : {cfg.FLIGHT_CSV_PATH}")
    print(f"프로펠러 NPZ 파일 : {cfg.PROP_NPZ_PATH}")
    print(f"적분 시간 간격    : {cfg.DT_SIM:.3f} s")
    print(f"시뮬 종료 시간    : {out['t'][-1]/60.0:.2f} min  | step 수={len(out['t'])}")
    print(f"속도 kt (최소/중간/최대): "
          f"{np.nanmin(out['V']*cfg.MS2KT):.2f} / "
          f"{np.nanmedian(out['V']*cfg.MS2KT):.2f} / "
          f"{np.nanmax(out['V']*cfg.MS2KT):.2f}")
    print(f"명령 파워 kW (최소/중간/최대): "
          f"{np.nanmin(out['P_cmd'])/1000.0:.2f} / "
          f"{np.nanmedian(out['P_cmd'])/1000.0:.2f} / "
          f"{np.nanmax(out['P_cmd'])/1000.0:.2f}")
    print(f"최종 SOC (%)      : {out['SOC'][-1]*100.0:.2f}")
    print(f"최종 배터리 전압 : {out['Vdc'][-1]:.2f} V")
    print(f"최종 배터리 온도 : {out['Temp'][-1]:.2f} °C")
    print(f"현재(마지막 step) 위치-웨이포인트 거리 : {out['wp_dist'][-1]:.2f} m")
    print(f"웨이포인트 거리 m (최소/중간/최대): "
          f"{np.nanmin(out['wp_dist']):.2f} / "
          f"{np.nanmedian(out['wp_dist']):.2f} / "
          f"{np.nanmax(out['wp_dist']):.2f}")

    if cfg.SAVE_SIM_RESULT_CSV:
        save_sim_result_csv(cfg.SIM_RESULT_CSV_PATH, out)
        print(f"시뮬 결과 CSV 저장 : {cfg.SIM_RESULT_CSV_PATH}")


if __name__ == "__main__":
    main()
