"""Waypoint-guidance utilities."""

from __future__ import annotations

from math import atan2, sqrt

import numpy as np

from ..config import SimConfig
from ..schemas import GuidanceOut, State
from .utils import clamp


def compute_bearing_beta(
    x: float,
    y: float,
    x_wp: float,
    y_wp: float,
) -> float:
    """Compute the heading angle from the current position to a waypoint."""
    return atan2(y_wp - y, x_wp - x)


def guidance_waypoints(
    st: State,
    wps: np.ndarray,
    wp_idx: int,
    cfg: SimConfig,
    t: float,
    t_wps: np.ndarray,
) -> GuidanceOut:
    """Compute waypoint-based horizontal and vertical guidance targets.

    The active waypoint index advances according to waypoint timestamps.
    Horizontal guidance points directly toward the active waypoint, while
    the altitude target is interpolated continuously from the waypoint
    altitude profile.

    Args:
        st: Current aircraft state.
        wps: Waypoint array with shape ``(M, 3)`` containing
            ``[east, north, relative_altitude]``.
        wp_idx: Current waypoint index.
        cfg: Simulation configuration retained as part of the guidance
            interface.
        t: Current simulation time [s].
        t_wps: Waypoint timestamps relative to the start of the mission [s].

    Returns:
        Guidance output containing altitude and heading targets, the active
        waypoint index, and the 3D distance to the current guidance target.
    """
    M = int(wps.shape[0])
    wp_idx = int(clamp(wp_idx, 0, M - 1))

    # Advance the waypoint index when the next waypoint time is reached.
    if wp_idx < M - 1 and float(t) >= float(t_wps[wp_idx + 1]):
        wp_idx += 1

    # Current horizontal waypoint target.
    x_wp = float(wps[wp_idx, 0])
    y_wp = float(wps[wp_idx, 1])

    beta_d = compute_bearing_beta(
        st.x,
        st.y,
        x_wp,
        y_wp,
    )

    # Generate the altitude target independently from horizontal guidance.
    h_d = float(
        np.interp(
            float(t),
            np.asarray(t_wps, dtype=float),
            np.asarray(wps[:, 2], dtype=float),
        )
    )

    # 3D distance used for diagnostics and termination logic.
    dx = x_wp - st.x
    dy = y_wp - st.y
    dz = h_d - st.h
    dist_to_wp = sqrt(
        dx * dx
        + dy * dy
        + dz * dz
    )

    return GuidanceOut(
        h_d=h_d,
        beta_d=beta_d,
        wp_idx=wp_idx,
        dist_to_wp=float(dist_to_wp),
    )
