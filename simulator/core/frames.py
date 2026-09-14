"""Coordinate-frame conversions for WGS84 LLA, ECEF, and local ENU."""

from __future__ import annotations

from math import cos, radians, sin, sqrt
from typing import Tuple

import numpy as np


# WGS84 ellipsoid constants
WGS84_A = 6378137.0  # Equatorial radius [m]
WGS84_F = 1.0 / 298.257223563  # Flattening
WGS84_E2 = WGS84_F * (2 - WGS84_F)  # First eccentricity squared


def lla_to_ecef(
    lat_rad: float,
    lon_rad: float,
    alt_m: float,
) -> Tuple[float, float, float]:
    """Convert geodetic latitude, longitude, and altitude to ECEF.

    Args:
        lat_rad: Geodetic latitude [rad].
        lon_rad: Longitude [rad].
        alt_m: Altitude above the WGS84 ellipsoid [m].

    Returns:
        ECEF coordinates ``(x, y, z)`` in meters.
    """
    sin_lat = sin(lat_rad)
    cos_lat = cos(lat_rad)
    sin_lon = sin(lon_rad)
    cos_lon = cos(lon_rad)

    N = WGS84_A / sqrt(
        1.0 - WGS84_E2 * sin_lat * sin_lat
    )

    x = (N + alt_m) * cos_lat * cos_lon
    y = (N + alt_m) * cos_lat * sin_lon
    z = (
        N * (1.0 - WGS84_E2) + alt_m
    ) * sin_lat

    return x, y, z


def ecef_to_enu(
    x: float,
    y: float,
    z: float,
    x0: float,
    y0: float,
    z0: float,
    lat0_rad: float,
    lon0_rad: float,
) -> Tuple[float, float, float]:
    """Convert ECEF coordinates to local East-North-Up coordinates.

    The local ENU frame is defined relative to the reference ECEF
    position ``(x0, y0, z0)`` and geodetic latitude/longitude
    ``(lat0_rad, lon0_rad)``.
    """
    dx = x - x0
    dy = y - y0
    dz = z - z0

    sin_lat0 = sin(lat0_rad)
    cos_lat0 = cos(lat0_rad)
    sin_lon0 = sin(lon0_rad)
    cos_lon0 = cos(lon0_rad)

    e = (
        -sin_lon0 * dx
        + cos_lon0 * dy
    )

    n = (
        -sin_lat0 * cos_lon0 * dx
        - sin_lat0 * sin_lon0 * dy
        + cos_lat0 * dz
    )

    u = (
        cos_lat0 * cos_lon0 * dx
        + cos_lat0 * sin_lon0 * dy
        + sin_lat0 * dz
    )

    return e, n, u


def lla_series_to_enu(
    lat_deg: np.ndarray,
    lon_deg: np.ndarray,
    alt_m: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert an LLA time series to a local ENU time series.

    The first sample defines the local-frame origin. Altitude values are
    treated as absolute altitudes before being converted to relative
    ENU up coordinates.

    Returns:
        Arrays of east, north, and up coordinates in meters.
    """
    lat_deg = np.asarray(lat_deg, dtype=float)
    lon_deg = np.asarray(lon_deg, dtype=float)
    alt_m = np.asarray(alt_m, dtype=float)

    lat0_rad = radians(float(lat_deg[0]))
    lon0_rad = radians(float(lon_deg[0]))

    x0, y0, z0 = lla_to_ecef(
        lat0_rad,
        lon0_rad,
        float(alt_m[0]),
    )

    xs = np.empty_like(lat_deg)
    ys = np.empty_like(lat_deg)
    hs = np.empty_like(lat_deg)

    for i in range(len(lat_deg)):
        lat_rad = radians(float(lat_deg[i]))
        lon_rad = radians(float(lon_deg[i]))
        alt = float(alt_m[i])

        x, y, z = lla_to_ecef(
            lat_rad,
            lon_rad,
            alt,
        )
        e, n, u = ecef_to_enu(
            x,
            y,
            z,
            x0,
            y0,
            z0,
            lat0_rad,
            lon0_rad,
        )

        xs[i] = e
        ys[i] = n
        hs[i] = u

    return xs, ys, hs
