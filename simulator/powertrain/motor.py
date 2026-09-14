"""Constant-efficiency motor and inverter power-conversion utilities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MotorModel:
    """Constant-efficiency model for the motor and inverter.

    ``eta`` represents the electrical-to-shaft conversion efficiency and
    must lie in the interval ``(0, 1]``.
    """

    eta: float = 0.92

    def __post_init__(self) -> None:
        if not (0.0 < float(self.eta) <= 1.0):
            raise ValueError(
                f"MotorModel.eta must be in (0, 1]. got {self.eta}"
            )


def elec_to_shaft_power(
    P_elec_W: float,
    eta: float,
    clamp_nonneg: bool = True,
) -> float:
    """Convert electrical input power to delivered shaft power.

    The conversion follows:

        P_shaft = eta * P_elec

    Args:
        P_elec_W: Electrical power supplied to the motor [W].
        eta: Motor/inverter efficiency.
        clamp_nonneg: Clamp negative output power to zero when enabled.

    Returns:
        Mechanical shaft power [W].
    """
    eta = float(eta)
    if eta <= 0.0:
        return 0.0

    P_shaft = eta * float(P_elec_W)
    return max(0.0, P_shaft) if clamp_nonneg else P_shaft


def shaft_to_elec_power(
    P_shaft_W: float,
    eta: float,
    clamp_nonneg: bool = True,
    eps: float = 1e-6,
) -> float:
    """Convert requested shaft power to electrical-power demand.

    The conversion follows:

        P_elec = P_shaft / eta

    Args:
        P_shaft_W: Requested mechanical shaft power [W].
        eta: Motor/inverter efficiency.
        clamp_nonneg: Clamp negative electrical demand to zero when enabled.
        eps: Lower bound used to protect against division by zero.

    Returns:
        Required electrical input power [W].
    """
    eta = float(eta)
    if eta <= 0.0:
        return 0.0

    P_elec = float(P_shaft_W) / max(eps, eta)
    return max(0.0, P_elec) if clamp_nonneg else P_elec
