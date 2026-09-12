from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ParamsPM:
    """Parameters required by the point-mass equations of motion.

    ``rho`` may be updated at each simulation step as atmospheric
    conditions change.
    """

    g: float          # Gravitational acceleration [m/s^2]
    rho: float        # Air density [kg/m^3]
    m: float          # Aircraft mass [kg]
    S: float          # Wing area [m^2]
    dt: float         # Integration timestep [s]


@dataclass
class State:
    """Aircraft state used by the point-mass simulation.

    Attributes:
        x: East position in the local ENU frame [m].
        y: North position in the local ENU frame [m].
        h: Relative altitude [m].
        V: Airspeed magnitude [m/s].
        beta: Heading angle [rad].
        gamma: Flight-path angle [rad].
    """

    x: float
    y: float
    h: float
    V: float
    beta: float
    gamma: float

    def vec(self) -> np.ndarray:
        """Return the state as an array for numerical integration."""
        return np.array(
            [self.x, self.y, self.h, self.V, self.beta, self.gamma],
            dtype=float,
        )

    @staticmethod
    def from_vec(v: np.ndarray) -> "State":
        """Construct a state from a numerical state vector."""
        return State(
            x=float(v[0]),
            y=float(v[1]),
            h=float(v[2]),
            V=float(v[3]),
            beta=float(v[4]),
            gamma=float(v[5]),
        )


@dataclass
class GuidanceOut:
    """Output produced by the waypoint-guidance logic.

    Attributes:
        h_d: Target altitude [m].
        beta_d: Target heading [rad].
        wp_idx: Index of the active waypoint.
        dist_to_wp: Horizontal distance to the active waypoint [m].
    """

    h_d: float
    beta_d: float
    wp_idx: int
    dist_to_wp: float


@dataclass
class FlightScenario:
    """Input scenario for a simulator run.

    When provided, ``flight_csv_path`` overrides the default input path
    defined in ``SimConfig``.
    """

    name: str = "default"
    flight_csv_path: str | None = None


@dataclass
class TelemetryFrame:
    """Post-step simulation state exposed as a telemetry frame."""

    timestamp: float
    x_m: float
    y_m: float
    altitude_m: float
    airspeed_mps: float
    heading_rad: float
    flight_path_angle_rad: float
    soc: float
    voltage_v: float
    current_a: float
    battery_temperature_c: float
    rpm: float
    thrust_n: float
    phase: str
