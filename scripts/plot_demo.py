from __future__ import annotations

from typing import Dict

import matplotlib.pyplot as plt
import numpy as np

from simulator.config import SimConfig


def plot_demo(
    wps: np.ndarray,
    out: Dict[str, np.ndarray],
    flight: Dict[str, np.ndarray],
    cfg: SimConfig,
) -> None:
    """Plot an overview of the public synthetic demo.

    The synthetic mission demonstrates end-to-end simulator execution.
    It is not used as a model-validation dataset.
    """
    t_sim = np.asarray(out["t"], dtype=float)
    t_min = t_sim / 60.0

    x = np.asarray(out["x"], dtype=float)
    y = np.asarray(out["y"], dtype=float)
    altitude = np.asarray(out["alt_abs"], dtype=float)
    airspeed_kt = np.asarray(out["V"], dtype=float) * float(cfg.MS2KT)

    soc_pct = np.asarray(out["SOC"], dtype=float) * 100.0
    voltage_v = np.asarray(out["Vdc"], dtype=float)
    temperature_c = np.asarray(out["Temp"], dtype=float)

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))

    fig.suptitle(
        "Synthetic Demo — Electric Aircraft Flight & Battery Simulation",
        fontsize=14,
    )

    # ------------------------------------------------------------
    # Ground track
    # ------------------------------------------------------------
    ax = axes[0, 0]

    ax.plot(
        wps[:, 0],
        wps[:, 1],
        "-",
        linewidth=1.2,
        alpha=0.6,
        label="Mission waypoints",
    )

    ax.plot(
        x,
        y,
        "--",
        linewidth=1.4,
        label="Simulation",
    )

    ax.set_title("Ground Track")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.axis("equal")
    ax.grid(True, alpha=0.25)
    ax.legend()

    # ------------------------------------------------------------
    # Altitude
    # ------------------------------------------------------------
    ax = axes[0, 1]

    ax.plot(
        t_min,
        altitude,
        linewidth=1.4,
    )

    ax.set_title("Simulated Altitude")
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Altitude (m)")
    ax.grid(True, alpha=0.25)

    # ------------------------------------------------------------
    # Airspeed
    # ------------------------------------------------------------
    ax = axes[0, 2]

    ax.plot(
        t_min,
        airspeed_kt,
        linewidth=1.4,
    )

    ax.set_title("Simulated Airspeed")
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Airspeed (kt)")
    ax.grid(True, alpha=0.25)

    # ------------------------------------------------------------
    # SOC
    # ------------------------------------------------------------
    ax = axes[1, 0]

    ax.plot(
        t_min,
        soc_pct,
        linewidth=1.4,
    )

    ax.set_title("Battery State of Charge")
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("SOC (%)")
    ax.grid(True, alpha=0.25)

    # ------------------------------------------------------------
    # Battery voltage
    # ------------------------------------------------------------
    ax = axes[1, 1]

    ax.plot(
        t_min,
        voltage_v,
        linewidth=1.4,
    )

    ax.set_title("Battery Voltage")
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Voltage (V)")
    ax.grid(True, alpha=0.25)

    # ------------------------------------------------------------
    # Battery temperature
    # ------------------------------------------------------------
    ax = axes[1, 2]

    ax.plot(
        t_min,
        temperature_c,
        linewidth=1.4,
    )

    ax.set_title("Battery Temperature")
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Temperature (°C)")
    ax.grid(True, alpha=0.25)

    fig.tight_layout()
    plt.show()