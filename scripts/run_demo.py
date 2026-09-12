"""Run the public synthetic end-to-end simulator demo."""

from __future__ import annotations

import contextlib
import csv
import io
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from simulator.config import SimConfig
from simulator.demo_data import create_demo_flight_csv
from simulator.schemas import ParamsPM
from simulator.core.atmosphere import compute_rho
from simulator.core.io_flight import (
    load_flight_csv,
    make_waypoints_from_csv,
    build_oat_input,
)
from simulator.core.control import PowerController
from simulator.powertrain.prop import PropellerModel
from simulator.powertrain.system import Powertrain
from simulator.core.sim_loop import simulate_flight
from scripts.plot_demo import plot_demo


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

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(cols)

        for i in range(n_rows):
            writer.writerow([one_dim[col][i] for col in cols])


def main() -> None:
    # ============================================================
    # (1) 설정 로드
    # ============================================================
    cfg = SimConfig()

    # ============================================================
    # (2) Public demo input 생성 + 비행 로그 로드
    # ============================================================
    demo_flight_path = (
        PROJECT_ROOT
        / "data"
        / "input"
        / "demo"
        / "synthetic_flight.csv"
    )

    cfg.FLIGHT_CSV_PATH = create_demo_flight_csv(demo_flight_path)

    print(f"Created synthetic demo mission: {cfg.FLIGHT_CSV_PATH}")

    flight = load_flight_csv(cfg.FLIGHT_CSV_PATH)

    # 로그를 시간 기준으로 다운샘플링하여 ENU 웨이포인트 생성
    wps, twp = make_waypoints_from_csv(
        flight["t"],
        flight["lat"],
        flight["lon"],
        flight["alt"],
        downsample_sec=float(cfg.DOWNSAMPLE_SEC),
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

    print("Running synthetic demo simulation...")

    with contextlib.redirect_stdout(io.StringIO()):
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

    print("Simulation completed.")

    # ============================================================
    # (8) 결과 플롯
    # ============================================================
    plot_demo(
        wps=wps,
        out=out,
        cfg=cfg,
    )

    # ============================================================
    # (9) 간단 요약 출력
    # ============================================================
    print("\n=== Simulation Summary ===")
    print(f"Duration                  : {out['t'][-1] / 60.0:.2f} min")
    print(f"Simulation steps          : {len(out['t'])}")
    print(
        f"Airspeed range            : "
        f"{np.nanmin(out['V'] * cfg.MS2KT):.2f} - "
        f"{np.nanmax(out['V'] * cfg.MS2KT):.2f} kt"
    )
    print(f"Final SOC                 : {out['SOC'][-1] * 100.0:.2f} %")
    print(f"Final battery voltage     : {out['Vdc'][-1]:.2f} V")
    print(f"Final battery temperature : {out['Temp'][-1]:.2f} °C")

    if cfg.SAVE_SIM_RESULT_CSV:
        save_sim_result_csv(cfg.SIM_RESULT_CSV_PATH, out)
        print(f"Results saved to           : {cfg.SIM_RESULT_CSV_PATH}")


if __name__ == "__main__":
    main()
