from __future__ import annotations

import contextlib
import io

import numpy as np

from simulator import FlightSimulator
from simulator.config import SimConfig
from simulator.core.atmosphere import compute_rho
from simulator.core.control import PowerController
from simulator.core.io_flight import build_oat_input, load_flight_csv, make_waypoints_from_csv
from simulator.core.sim_loop import simulate_flight
from simulator.powertrain.prop import PropellerModel
from simulator.powertrain.system import Powertrain
from simulator.schemas import ParamsPM
from simulator.demo_data import create_synthetic_flight_csv

def _make_test_config(tmp_path) -> SimConfig:
    cfg = SimConfig()
    cfg.FLIGHT_CSV_PATH = create_synthetic_flight_csv(
        tmp_path / "synthetic_flight.csv"
    )
    return cfg

def _run_batch_simulation(
    cfg: SimConfig,
    include_ias: bool = True,
) -> dict[str, np.ndarray]:
    flight = load_flight_csv(cfg.FLIGHT_CSV_PATH)

    wps, t_wps = make_waypoints_from_csv(
        flight["t"],
        flight["lat"],
        flight["lon"],
        flight["alt"],
        downsample_sec=float(cfg.DOWNSAMPLE_SEC),
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
            IAS_log=flight["IAS"] if include_ias else None,
            phase_log=flight.get("phase"),
        )


def test_incremental_run_matches_batch_simulation(tmp_path) -> None:
    cfg = _make_test_config(tmp_path)

    batch = _run_batch_simulation(cfg)
    sim = FlightSimulator.from_config(cfg=cfg)

    with contextlib.redirect_stdout(io.StringIO()):
        frames = sim.run_all()

    assert len(frames) == len(batch["t"])

    assert np.allclose(
        [frame.timestamp for frame in frames],
        batch["t"],
    )
    assert np.allclose(
        [frame.x_m for frame in frames],
        batch["x"],
    )
    assert np.allclose(
        [frame.y_m for frame in frames],
        batch["y"],
    )

    alt0_abs_m = float(load_flight_csv(cfg.FLIGHT_CSV_PATH)["alt"][0])

    assert np.allclose(
        batch["alt_abs"],
        alt0_abs_m + batch["h"],
    )
    assert np.allclose(
        [frame.altitude_m for frame in frames],
        batch["alt_abs"],
    )
    assert np.allclose(
        [frame.airspeed_mps for frame in frames],
        batch["V"],
    )
    assert np.allclose(
        [frame.soc for frame in frames],
        batch["SOC"],
    )
    assert np.allclose(
        [frame.voltage_v for frame in frames],
        batch["Vdc"],
    )

    assert [frame.phase for frame in frames] == [
        str(phase) for phase in batch["phase_at_sim"]
    ]


def test_run_all_reaches_finished_state(tmp_path) -> None:
    cfg = _make_test_config(tmp_path)
    sim = FlightSimulator.from_config(cfg=cfg)

    frames = sim.run_all()

    assert len(frames) > 0
    assert sim.finished
    assert sim.step() is None
    assert frames[-1].timestamp >= frames[0].timestamp


def test_batch_phase_control_does_not_require_ias_log(tmp_path) -> None:
    cfg = _make_test_config(tmp_path)

    batch_with_ias = _run_batch_simulation(cfg, include_ias=True)
    batch_without_ias = _run_batch_simulation(cfg, include_ias=False)

    assert np.array_equal(
        batch_without_ias["phase_at_sim"],
        batch_with_ias["phase_at_sim"],
    )
