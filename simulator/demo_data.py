from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def create_synthetic_flight_csv(path: str | Path) -> str:
    """Create synthetic flight data for the public demo and tests.

    The generated data are fully artificial and are not derived from
    real-flight research datasets.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    n = 121
    t_sec = np.arange(n, dtype=float)

    # Artificial route.
    lat0 = 37.0
    lon0 = 127.0

    lat = lat0 + np.linspace(0.0, 0.01, n)
    lon = lon0 + np.linspace(0.0, 0.005, n)

    # Artificial climb -> cruise -> descent profile.
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

    df.to_csv(path, index=False)

    return str(path)

def create_demo_flight_csv(path: str | Path) -> str:
    """Create a synthetic mission for the public simulator demo.

    The generated data are fully artificial and are not derived from
    real-flight research datasets.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 200-second synthetic mission.
    t_sec = np.arange(0.0, 201.0, 1.0)
    n = len(t_sec)

    # ------------------------------------------------------------
    # Flight phases
    # ------------------------------------------------------------
    phase = np.empty(n, dtype=object)

    phase[t_sec < 20.0] = "ground_roll"
    phase[(t_sec >= 20.0) & (t_sec < 80.0)] = "climb"
    phase[(t_sec >= 80.0) & (t_sec < 130.0)] = "cruise"
    phase[(t_sec >= 130.0) & (t_sec < 180.0)] = "descent"
    phase[t_sec >= 180.0] = "ground_roll"

    # ------------------------------------------------------------
    # Synthetic airspeed profile [kt]
    #
    # 0-20 s:   ground acceleration
    # 20-80 s:  climb
    # 80-130 s: cruise
    # 130-180 s: descent / approach
    # 180-200 s: landing roll
    # ------------------------------------------------------------
    ias_kt = np.interp(
        t_sec,
        [0.0, 20.0, 80.0, 130.0, 180.0, 200.0],
        [0.0, 50.0, 75.0, 85.0, 60.0, 0.0],
    )

    kt_to_ms = 1.0 / 1.943844
    speed_mps = ias_kt * kt_to_ms

    # Integrate the synthetic speed profile to obtain a route whose
    # length is consistent with the mission duration and airspeed.
    x_m = np.zeros(n, dtype=float)
    x_m[1:] = np.cumsum(
        0.5 * (speed_mps[:-1] + speed_mps[1:])
    )

    # Straight eastbound route.
    lat0 = 37.0
    lon0 = 127.0

    meters_per_degree_lon = 111_320.0 * np.cos(np.deg2rad(lat0))

    lat = np.full(n, lat0, dtype=float)
    lon = lon0 + x_m / meters_per_degree_lon

    # ------------------------------------------------------------
    # Altitude profile [m]
    # ------------------------------------------------------------
    altitude = np.interp(
        t_sec,
        [0.0, 20.0, 80.0, 130.0, 180.0, 200.0],
        [100.0, 100.0, 350.0, 350.0, 100.0, 100.0],
    )

    # ------------------------------------------------------------
    # Artificial log channels required by load_flight_csv()
    #
    # These values exist only to provide a complete public demo input.
    # They are not research-validation measurements.
    # ------------------------------------------------------------
    motor_power_kw = np.select(
        [
            t_sec < 20.0,
            (t_sec >= 20.0) & (t_sec < 80.0),
            (t_sec >= 80.0) & (t_sec < 130.0),
            (t_sec >= 130.0) & (t_sec < 180.0),
            t_sec >= 180.0,
        ],
        [45.0, 49.2, 25.0, 5.0, 2.0],
    )

    motor_rpm = np.select(
        [
            t_sec < 20.0,
            (t_sec >= 20.0) & (t_sec < 80.0),
            (t_sec >= 80.0) & (t_sec < 130.0),
            (t_sec >= 130.0) & (t_sec < 180.0),
            t_sec >= 180.0,
        ],
        [2200.0, 2300.0, 2100.0, 1400.0, 500.0],
    )

    battery_voltage = np.linspace(400.0, 385.0, n)

    total_current = (
        motor_power_kw * 1000.0 / battery_voltage
    )

    df = pd.DataFrame(
        {
            "time(ms)": t_sec * 1000.0,
            "LAT": lat,
            "LNG": lon,
            "PRESSURE_ALT": altitude,
            "OAT": np.full(n, 20.0),
            "motor power": motor_power_kw,
            "motor rpm": motor_rpm,
            "IAS": ias_kt,
            "bat 1 soc": np.linspace(97.0, 94.5, n),
            "bat 1 voltage": battery_voltage,
            "bat 1 current": total_current / 2.0,
            "bat 2 current": total_current / 2.0,
            "bat 1 avg cell temp": np.linspace(25.0, 27.0, n),
            "phase": phase,
        }
    )

    df.to_csv(path, index=False)

    return str(path)