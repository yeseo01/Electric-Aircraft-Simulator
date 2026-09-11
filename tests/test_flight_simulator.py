from __future__ import annotations

import contextlib
import io

import numpy as np
import pandas as pd

from simulator import FlightSimulator
from simulator.config import SimConfig
from simulator.core.atmosphere import compute_rho
from simulator.core.control import PowerController
from simulator.core.io_flight import build_oat_input, load_flight_csv, make_waypoints_from_csv
from simulator.core.sim_loop import simulate_flight
from simulator.powertrain.prop import PropellerModel
from simulator.powertrain.system import Powertrain
from simulator.schemas import ParamsPM


def _create_synthetic_flight_csv(tmp_path) -> str:
    """Create a small synthetic flight log for tests.

    The data are artificial and do not originate from real flight logs.
    """
    n = 121
    t_sec = np.arange(n, dtype=float)

    # Simple artificial route.
    lat0 = 37.0
    lon0 = 127.0

    lat = lat0 + np.linspace(0.0, 0.01, n)
    lon = lon0 + np.linspace(0.0, 0.005, n)

    # Simple climb / cruise / descent profile.
    altitude = np.concatenate(
        [
            np.linspace(100.0, 300.0, 41),
            np.full(40, 300.0),
            np.linspace(300.0, 120.0, 40),
        ]
    )

    phase = np.array(
        ["climb"] * 41
        + ["cruise"] * 40
        + ["descent"] * 40
    )

    df = pd.DataFrame(
        {
            "time(ms)": t_sec * 1000.0,
            "LAT": lat,
            "LNG": lon,
            "PRESSURE_ALT": altitude,
            "OAT": np.full(n, 20.0),
            "motor power": np.full(n, 40.0),
            "motor rpm": np.full(n, 2200.0),
            "IAS": np.full(n, 30.0),
            "bat 1 soc": np.linspace(95.0, 90.0, n),
            "bat 1 voltage": np.full(n, 400.0),
            "bat 1 current": np.full(n, 50.0),
            "bat 2 current": np.full(n, 50.0),
            "bat 1 avg cell temp": np.full(n, 25.0),
            "phase": phase,
        }
    )

    path = tmp_path / "synthetic_flight.csv"
    df.to_csv(path, index=False)

    return str(path)


def _make_test_config(tmp_path) -> SimConfig:
    cfg = SimConfig()
    cfg.FLIGHT_CSV_PATH = _create_synthetic_flight_csv(tmp_path)
    return cfg


def _run_batch_simulation(cfg: SimConfig) -> dict[str, np.ndarray]:
    flight = load_flight_csv(cfg.FLIGHT_CSV_PATH)

    wps, t_wps = make_waypoints_from_csv(
        flight["t"],
        flight["lat"],
        flight["lon"],
        flight["alt"],
        downsample_sec=float(cfg.DOWNSAMPLE_SEC),
        phase=flight.get("phase"),
    )

    t_max = float(cfg.TMAX_SCALE) * float(t_wps[-1])
    t_ref = np.arange(0.0, t_max + cfg.DT_SIM, cfg.DT_SIM, dtype=float)
    oat_ref = build_oat_input(flight, t_ref, cfg)
    alt0_abs_m = float(flight["alt"][0])

    def rho_func(t_now: float, alt_abs_m: float) -> float:
        oat = float(np.interp(float(t_now), t_ref, oat_ref))
        return float(compute_rho(float(alt_abs_m), oat))

    params = ParamsPM(
        g=9.80665,
        rho=1.225,
        m=float(cfg.MASS_KG),
        S=float(cfg.S_WING),
        dt=float(cfg.DT_SIM),
    )

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

    t_log = flight["t"] - float(flight["t"][0])

    with contextlib.redirect_stdout(io.StringIO()):
        return simulate_flight(
            wps=wps,
            t_wps=t_wps,
            t_max=t_max,
            p=params,
            cfg=cfg,
            power_ctrl=PowerController(cfg),
            powertrain=powertrain,
            t_ref=t_ref,
            OAT_ref=oat_ref,
            alt0_abs_m=alt0_abs_m,
            t_log=t_log,
            IAS_log=flight["IAS"],
            phase_log=flight.get("phase"),
        )


def test_incremental_first_20_frames_match_batch_simulation(tmp_path) -> None:
    cfg = _make_test_config(tmp_path)

    batch = _run_batch_simulation(cfg)
    sim = FlightSimulator.from_config(cfg=cfg)

    frames = [sim.step() for _ in range(20)]

    assert all(frame is not None for frame in frames)
    assert np.allclose([frame.timestamp for frame in frames], batch["t"][:20])
    assert np.allclose([frame.x_m for frame in frames], batch["x"][:20])
    assert np.allclose([frame.y_m for frame in frames], batch["y"][:20])
    assert np.allclose(
        [frame.airspeed_mps for frame in frames],
        batch["V"][:20],
    )
    assert np.allclose([frame.soc for frame in frames], batch["SOC"][:20])
    assert np.allclose(
        [frame.voltage_v for frame in frames],
        batch["Vdc"][:20],
    )
    assert [frame.phase for frame in frames] == [
        str(phase) for phase in batch["phase_at_sim"][:20]
    ]


def test_run_all_reaches_finished_state(tmp_path) -> None:
    cfg = _make_test_config(tmp_path)
    sim = FlightSimulator.from_config(cfg=cfg)

    frames = sim.run_all()

    assert len(frames) > 0
    assert sim.finished
    assert sim.step() is None
    assert frames[-1].timestamp >= frames[0].timestamp