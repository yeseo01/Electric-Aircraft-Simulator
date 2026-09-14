"""Atmospheric pressure and air-density utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

import numpy as np


NumberOrArray = Union[float, int, np.ndarray]


@dataclass(frozen=True)
class ISAParams:
    """Parameters for the ISA troposphere approximation up to 11 km."""

    g0: float = 9.80665  # Gravitational acceleration [m/s^2]
    R_air: float = 287.05287  # Specific gas constant for air [J/(kg*K)]
    p0_std: float = 101325.0  # Standard sea-level pressure [Pa]
    T0_std: float = 288.15  # Standard sea-level temperature [K]
    L: float = 0.0065  # Tropospheric temperature lapse rate [K/m]


def isa_pressure_from_alt(
    h_m: NumberOrArray,
    isa: ISAParams = ISAParams(),
) -> NumberOrArray:
    """Compute static pressure from altitude using an ISA approximation.

    Altitude is clipped to the tropospheric range [0, 11000] m.

    Args:
        h_m: Altitude [m], provided as a scalar or NumPy array.
        isa: ISA parameter set.

    Returns:
        Static pressure [Pa], preserving scalar or array form.
    """
    h = np.clip(
        np.asarray(h_m, dtype=float),
        0.0,
        11000.0,
    )

    expo = isa.g0 / (isa.R_air * isa.L)
    p = isa.p0_std * (
        1.0 - isa.L * h / isa.T0_std
    ) ** expo

    return float(p) if np.ndim(p) == 0 else p


def compute_rho(
    alt_m: NumberOrArray,
    oat_c: NumberOrArray,
    isa: ISAParams = ISAParams(),
    T_clip_K: tuple[float, float] = (200.0, 330.0),
) -> NumberOrArray:
    """Compute air density from altitude and outside-air temperature.

    Static pressure is obtained from the ISA troposphere approximation,
    while temperature is taken from OAT and clipped to ``T_clip_K``.

    The density relation is:

        rho = p / (R_air * T)

    NumPy broadcasting applies when ``alt_m`` or ``oat_c`` are arrays.

    Args:
        alt_m: Absolute altitude [m].
        oat_c: Outside-air temperature [°C].
        isa: ISA parameter set.
        T_clip_K: Minimum and maximum temperature used in density
            calculations [K].

    Returns:
        Air density [kg/m^3], preserving scalar or array form.
    """
    p = isa_pressure_from_alt(
        alt_m,
        isa=isa,
    )

    T = np.asarray(oat_c, dtype=float) + 273.15
    T = np.clip(
        T,
        T_clip_K[0],
        T_clip_K[1],
    )

    rho = np.asarray(p, dtype=float) / (
        isa.R_air * T
    )

    return float(rho) if np.ndim(rho) == 0 else rho
