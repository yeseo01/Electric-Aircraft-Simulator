"""Electric aircraft simulation core package."""

from .config import SimConfig
from .flight_simulator import FlightSimulator
from .schemas import FlightScenario, GuidanceOut, ParamsPM, State, TelemetryFrame
from .core.sim_loop import simulate_flight

__all__ = [
    "FlightScenario",
    "FlightSimulator",
    "GuidanceOut",
    "ParamsPM",
    "SimConfig",
    "State",
    "TelemetryFrame",
    "simulate_flight",
]
