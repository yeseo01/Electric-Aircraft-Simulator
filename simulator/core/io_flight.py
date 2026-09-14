"""Flight-log loading, waypoint generation, and signal interpolation."""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pandas as pd

from ..config import SimConfig
from .frames import lla_series_to_enu


def load_flight_csv(path: str) -> Dict[str, np.ndarray]:
    """Load the required signals from a flight-log CSV file.

    The input CSV is expected to contain all required columns. Missing
    columns raise ``KeyError`` immediately so data-format problems are
    detected before simulation begins.

    Required columns:
        time(ms), LAT, LNG, PRESSURE_ALT,
        OAT, motor power, motor rpm, IAS,
        bat 1 soc, bat 1 voltage, bat 1 current, bat 2 current,
        bat 1 avg cell temp
    """
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()

    required = [
        "time(ms)",
        "LAT",
        "LNG",
        "PRESSURE_ALT",
        "OAT",
        "motor power",
        "motor rpm",
        "IAS",
        "bat 1 soc",
        "bat 1 voltage",
        "bat 1 current",
        "bat 2 current",
        "bat 1 avg cell temp",
    ]

    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required CSV columns: {missing}")

    # Convert milliseconds to seconds.
    t = np.asarray(df["time(ms)"], dtype=float) * 1e-3

    out: Dict[str, np.ndarray] = {
        "t": t,
        "lat": np.asarray(df["LAT"], dtype=float),
        "lon": np.asarray(df["LNG"], dtype=float),
        "alt": np.asarray(df["PRESSURE_ALT"], dtype=float),

        "OAT": np.asarray(df["OAT"], dtype=float),

        # Convert motor power from kW to W.
        "P_meas_W": np.asarray(df["motor power"], dtype=float) * 1000.0,
        "RPM_log": np.asarray(df["motor rpm"], dtype=float),
        "IAS": np.asarray(df["IAS"], dtype=float),

        "bat_soc_pct": np.asarray(df["bat 1 soc"], dtype=float),
        "bat_v": np.asarray(df["bat 1 voltage"], dtype=float),
        "bat_i": np.asarray(
            df["bat 1 current"] + df["bat 2 current"],
            dtype=float,
        ),
        "bat_t": np.asarray(df["bat 1 avg cell temp"], dtype=float),
    }

    # Preserve an optional phase column for phase-specific control logic.
    if "phase" in df.columns:
        out["phase"] = df["phase"].astype(str).to_numpy()

    return out


def make_waypoints_from_csv(
    t: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    alt: np.ndarray,
    downsample_sec: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Generate ENU waypoints by uniformly downsampling a flight log.

    Processing steps:
        1. Shift the input time axis to start at zero.
        2. Select samples separated by at least ``downsample_sec``.
        3. Convert the selected LLA positions to local ENU coordinates.
        4. Build waypoints as ``[east, north, relative_altitude]``.

    Returns:
        ``wps``:
            ENU waypoint array with shape ``(N, 3)`` in meters.
        ``t_d``:
            Downsampled waypoint times in seconds.
    """
    t = np.asarray(t, dtype=float)
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    alt = np.asarray(alt, dtype=float)

    t0 = float(t[0])
    tt = t - t0

    base_dt = float(downsample_sec)

    idx = [0]
    last_t = float(tt[0])

    for i in range(1, len(tt)):
        if float(tt[i]) - last_t >= base_dt:
            idx.append(i)
            last_t = float(tt[i])

    # Always include the final sample.
    if idx[-1] != len(tt) - 1:
        idx.append(len(tt) - 1)

    idx = np.asarray(idx, dtype=int)

    lat_d = lat[idx]
    lon_d = lon[idx]
    alt_d = alt[idx]
    t_d = tt[idx]

    x_enu, y_enu, _ = lla_series_to_enu(
        lat_d,
        lon_d,
        alt_d,
    )
    h_rel = alt_d - float(alt_d[0])

    wps = np.stack(
        [x_enu, y_enu, h_rel],
        axis=1,
    )

    return wps, t_d


def build_oat_input(
    flight: Dict[str, np.ndarray],
    t_target: np.ndarray,
    cfg: SimConfig,
) -> np.ndarray:
    """Build the outside-air-temperature input on a target time axis.

    When ``USE_REAL_OAT_FROM_CSV`` is enabled, the flight-log OAT signal
    is cleaned, interpolated, and resampled. Otherwise,
    ``DEFAULT_OAT_C`` is used.

    Invalid OAT samples are defined as non-finite values, zero, or values
    outside the range [-40, 60] °C.
    """
    t_target = np.asarray(t_target, dtype=float)

    if not cfg.USE_REAL_OAT_FROM_CSV:
        return np.full_like(
            t_target,
            float(cfg.DEFAULT_OAT_C),
            dtype=float,
        )

    oat_raw = np.asarray(
        flight.get("OAT", np.array([])),
        dtype=float,
    )
    t_raw = np.asarray(
        flight.get("t", np.array([])),
        dtype=float,
    )

    if len(oat_raw) < 2 or len(t_raw) < 2:
        return np.full_like(
            t_target,
            float(cfg.DEFAULT_OAT_C),
            dtype=float,
        )

    oat = oat_raw.copy()
    bad = (
        (~np.isfinite(oat))
        | (oat == 0)
        | (oat < -40)
        | (oat > 60)
    )

    if np.all(bad):
        return np.full_like(
            t_target,
            float(cfg.DEFAULT_OAT_C),
            dtype=float,
        )

    oat[bad] = np.nan
    oat = (
        pd.Series(oat)
        .interpolate(limit_direction="both")
        .to_numpy(dtype=float)
    )

    # Shift the source time axis to start at zero.
    tt = (t_raw - float(t_raw[0])).astype(float)

    # Average duplicate timestamps before interpolation.
    df = (
        pd.DataFrame({"t": tt, "oat": oat})
        .groupby("t", as_index=False)
        .mean()
    )
    tt_u = df["t"].to_numpy(dtype=float)
    oat_u = df["oat"].to_numpy(dtype=float)

    return np.interp(t_target, tt_u, oat_u)


def interp_log_to_sim(
    t_log: np.ndarray,
    y_log: np.ndarray,
    t_sim: np.ndarray,
) -> np.ndarray:
    """Interpolate a logged signal onto the simulation time axis."""
    t_log = np.asarray(t_log, dtype=float)
    y_log = np.asarray(y_log, dtype=float)
    t_sim = np.asarray(t_sim, dtype=float)

    good = np.isfinite(t_log) & np.isfinite(y_log)
    if np.sum(good) < 2:
        return np.full_like(
            t_sim,
            np.nan,
            dtype=float,
        )

    tt = t_log[good]
    yy = y_log[good]

    order = np.argsort(tt)
    tt = tt[order]
    yy = yy[order]

    df = (
        pd.DataFrame({"t": tt, "y": yy})
        .groupby("t", as_index=False)
        .mean()
    )
    tt_u = df["t"].to_numpy(dtype=float)
    yy_u = df["y"].to_numpy(dtype=float)

    return np.interp(t_sim, tt_u, yy_u)
