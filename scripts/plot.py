# plot.py
from __future__ import annotations
from typing import Dict
import numpy as np
import matplotlib.pyplot as plt

from simulator.config import SimConfig
from simulator.core.io_flight import interp_log_to_sim


# ============================================================
# Metric functions
# ============================================================
def _finite_pair(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    m = np.isfinite(a) & np.isfinite(b)
    return a[m], b[m]


def _hausdorff_1d(a, b):

    if len(a) == 0 or len(b) == 0:
        return np.nan

    a = np.sort(a)
    b = np.sort(b)

    def directed(x, y):

        idx = np.searchsorted(y, x)

        left = np.clip(idx - 1, 0, len(y) - 1)
        right = np.clip(idx, 0, len(y) - 1)

        d_left = np.abs(x - y[left])
        d_right = np.abs(x - y[right])

        return np.max(np.minimum(d_left, d_right))

    return max(directed(a, b), directed(b, a))


def compute_metrics(sim, log):

    sim, log = _finite_pair(sim, log)

    if len(sim) < 2:
        return {"rmse": np.nan, "hausdorff": np.nan}

    err = sim - log

    rmse = np.sqrt(np.mean(err**2))
    hd = _hausdorff_1d(sim, log)

    return {"rmse": rmse, "hausdorff": hd}


def _metric_box(ax, m):

    txt = f"RMSE = {m['rmse']:.3g}\nHausdorff = {m['hausdorff']:.3g}"

    ax.text(
        0.99,
        0.02,
        txt,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
        bbox=dict(boxstyle="round", alpha=0.2),
    )


# ============================================================
# Ground Track
# ============================================================
def plot_ground_track(wps: np.ndarray, out: Dict[str, np.ndarray], title: str = "Ground track"):

    plt.figure(figsize=(6, 6))

    plt.plot(
        wps[:, 0],
        wps[:, 1],
        "-",
        lw=1.2,
        label="Waypoints (ENU)",
        alpha=0.5,
        color="black",
    )

    x = np.asarray(out["x"], dtype=float)
    y = np.asarray(out["y"], dtype=float)

    # (디버깅용-삭제절대금지) phase별 색상 구분해서 시뮬 궤적 표시
    # phase_at_sim = out.get("phase_at_sim")
    # if phase_at_sim is None:
    #     plt.plot(x, y, ":", lw=1.5, label="Simulation")
    # else:
    #     phase_arr = np.char.lower(np.asarray(phase_at_sim, dtype=str))
    #     colors = {
    #         "ground_roll": "tab:green",
    #         "climb": "tab:orange",
    #         "cruise": "tab:blue",
    #         "descent": "tab:red",
    #     }
    #     plotted_labels = set()
    #     for i in range(len(x) - 1):
    #         ph = str(phase_arr[i])
    #         color = colors.get(ph, "k")
    #         label = None
    #         if ph not in plotted_labels:
    #             label = f"Simulation - {ph}"
    #             plotted_labels.add(ph)
    #         plt.plot(x[i:i+2], y[i:i+2], ":", lw=1.2, color=color, label=label)

    # 단일 색상으로 전체 시뮬레이션 궤적을 그림
    plt.plot(x, y, "--", lw=1.2, label="Simulation")

    plt.axis("equal")
    plt.grid(True, alpha=0.25)

    plt.xlabel("x East (m)")
    plt.ylabel("y North (m)")

    plt.title(title)
    plt.legend()

    plt.tight_layout()
    plt.show()


# ============================================================
# Altitude
# ============================================================
def plot_altitude(out: Dict[str, np.ndarray],
                  flight: Dict[str, np.ndarray],
                  cfg: SimConfig,
                  title: str = "Altitude (m)"):

    t_sim = out["t"]
    t_log = flight["t"] - float(flight["t"][0])

    alt_log_on_sim = interp_log_to_sim(t_log, flight["alt"], t_sim)

    m = compute_metrics(out["alt_abs"], alt_log_on_sim)

    plt.figure(figsize=(11, 4))

    plt.plot(t_sim / 60.0, out["alt_abs"], lw=1.2, label="Alt_abs (sim)")
    plt.plot(t_sim / 60.0, alt_log_on_sim, lw=1.2, alpha=0.8, label="PRESSURE_ALT (log)")

    plt.grid(True, alpha=0.25)

    plt.xlabel("time (min)")
    plt.ylabel("Altitude (m)")

    plt.title(title)
    plt.legend()

    _metric_box(plt.gca(), m)

    plt.tight_layout()
    plt.show()


# ============================================================
# Speed
# ============================================================
def plot_speed(out: Dict[str, np.ndarray],
               flight: Dict[str, np.ndarray],
               cfg: SimConfig,
               title: str = "Airspeed"):

    t_sim = out["t"]
    t_log = flight["t"] - float(flight["t"][0])

    IAS_log_on_sim = interp_log_to_sim(t_log, flight["IAS"], t_sim)

    v_sim_kt = out["V"] * cfg.MS2KT

    m = compute_metrics(v_sim_kt, IAS_log_on_sim)

    fig, ax1 = plt.subplots(1, 1, figsize=(11, 4), sharex=True)

    fig.suptitle(title)

    ax1.plot(t_sim / 60.0, v_sim_kt, lw=1.2, label="V_sim (kt)")
    ax1.plot(t_sim / 60.0, IAS_log_on_sim, lw=1.2, alpha=0.8, label="IAS_log (kt)")
    ax1.axhline(cfg.V_REF_KT, lw=1.0, alpha=0.6, label="V_ref (kt)")

    ax1.set_xlabel("Time (min)")
    ax1.set_ylabel("Speed (kt)")

    ax1.grid(True, alpha=0.25)
    ax1.legend(loc="best")
    _metric_box(ax1, m)

    plt.tight_layout()
    plt.show()


# ============================================================
# Power
# ============================================================
def plot_power_signals(out: Dict[str, np.ndarray],
                       flight: Dict[str, np.ndarray],
                       cfg: SimConfig,
                       title: str = "Power signals"):

    t_sim = out["t"]
    t_log = flight["t"] - float(flight["t"][0])

    P_meas_W_on_sim = interp_log_to_sim(t_log, flight["P_meas_W"], t_sim)

    m = compute_metrics(out["P_elec"]/1000.0, P_meas_W_on_sim/1000.0)

    fig, ax1 = plt.subplots(1, 1, figsize=(11, 4), sharex=True)

    fig.suptitle(title)

    ax1.plot(t_sim / 60.0, out["P_cmd"] / 1000.0, lw=1.2, label="P_cmd (kW)")
    ax1.plot(t_sim / 60.0, out["P_prop"] / 1000.0, lw=1.2, label="P_prop (kW)")
    ax1.plot(t_sim / 60.0, out["P_elec"] / 1000.0, lw=1.2, label="P_elec_delivered (kW)")
    ax1.plot(t_sim / 60.0, P_meas_W_on_sim / 1000.0, lw=1.2, alpha=0.8, label="motor power (log) (kW)")

    ax1.set_ylabel("Power (kW)")

    ax1.grid(True, alpha=0.25)
    ax1.legend(loc="best")

    _metric_box(ax1, m)

    plt.tight_layout()
    plt.show()


# ============================================================
# RPM
# ============================================================
def plot_rpm(out: Dict[str, np.ndarray],
             flight: Dict[str, np.ndarray],
             cfg: SimConfig,
             title: str = "RPM"):

    t_sim = out["t"]
    t_log = flight["t"] - float(flight["t"][0])

    RPM_log_on_sim = interp_log_to_sim(t_log, flight["RPM_log"], t_sim)

    m = compute_metrics(out["rpm"], RPM_log_on_sim)

    fig, ax1 = plt.subplots(1, 1, figsize=(11, 4), sharex=True)

    fig.suptitle(title)

    ax1.plot(t_sim / 60.0, out["rpm"], lw=1.2, label="RPM (sim)")
    ax1.plot(t_sim / 60.0, RPM_log_on_sim, lw=1.2, alpha=0.8, label="motor rpm (log)")

    ax1.axhline(cfg.RPM_CONT, lw=1.0, alpha=0.6, label="RPM_CONT")
    ax1.axhline(cfg.RPM_SAFE, lw=1.0, alpha=0.6, label="RPM_SAFE")

    ax1.set_ylabel("RPM")

    ax1.grid(True, alpha=0.25)
    ax1.legend(loc="best")

    _metric_box(ax1, m)

    plt.tight_layout()
    plt.show()


# ============================================================
# Thrust
# ============================================================
def plot_thrust(out: Dict[str, np.ndarray],
                flight: Dict[str, np.ndarray],
                title: str = "Thrust"):

    t_sim = out["t"]
    fig, ax1 = plt.subplots(1, 1, figsize=(11, 4), sharex=True)

    fig.suptitle(title)

    ax1.plot(t_sim / 60.0, out["thrust"], lw=1.2, label="Thrust (sim)")

    ax1.set_ylabel("Thrust (N)")

    ax1.grid(True, alpha=0.25)
    ax1.legend(loc="best")

    plt.tight_layout()
    plt.show()


# ============================================================
# Battery
# ============================================================
def plot_battery(out: Dict[str, np.ndarray],
                 flight: Dict[str, np.ndarray],
                 t_ref: np.ndarray,
                 OAT_ref: np.ndarray,
                 cfg: SimConfig,
                 title: str = "Battery simulation"):

    t_sim = out["t"]
    t_log = flight["t"] - float(flight["t"][0])

    bat_soc_on_sim = interp_log_to_sim(t_log, flight["bat_soc_pct"], t_sim)
    bat_v_on_sim = interp_log_to_sim(t_log, flight["bat_v"], t_sim)
    bat_i_on_sim = interp_log_to_sim(t_log, flight["bat_i"], t_sim)
    bat_t_on_sim = interp_log_to_sim(t_log, flight["bat_t"], t_sim)

    OAT_C = np.interp(t_sim, t_ref, OAT_ref)

    m_v = compute_metrics(out["Vdc"], bat_v_on_sim)
    m_soc = compute_metrics(out["SOC"] * 100.0, bat_soc_on_sim)
    m_i = compute_metrics(out["I_batt"], bat_i_on_sim)
    m_t = compute_metrics(out["Temp"], bat_t_on_sim)

    # ============================================================
    # Figure 1: Altitude + Voltage + SOC
    # ============================================================
    fig1, axes1 = plt.subplots(
        2, 1, figsize=(13, 6.5), sharex=True,
        gridspec_kw={"height_ratios": [1, 1]}
    )
    fig1.suptitle(f"{title} (Voltage / SOC)")

    axes1[0].plot(t_sim / 60.0, out["Vdc"], lw=1.6, label="Voltage (sim)")
    axes1[0].plot(t_sim / 60.0, bat_v_on_sim, lw=1.2, alpha=0.8, label="Voltage (log)")
    axes1[0].set_ylabel("Voltage (V)")
    axes1[0].grid(True, alpha=0.25)
    axes1[0].legend(loc="best")
    _metric_box(axes1[0], m_v)

    axes1[1].plot(t_sim / 60.0, out["SOC"] * 100.0, lw=1.6, label="SOC (sim)")
    axes1[1].plot(t_sim / 60.0, bat_soc_on_sim, lw=1.2, alpha=0.8, label="SOC (log)")
    axes1[1].set_ylabel("SOC (%)")
    axes1[1].grid(True, alpha=0.25)
    axes1[1].legend(loc="best")
    _metric_box(axes1[1], m_soc)
    axes1[1].set_xlabel("Time (min)")

    plt.tight_layout()
    plt.show()

    # ============================================================
    # Figure 2: Altitude + Current + Temp
    # ============================================================
    fig2, axes2 = plt.subplots(
        2, 1, figsize=(13, 6.5), sharex=True,
        gridspec_kw={"height_ratios": [1, 1]}
    )
    fig2.suptitle(f"{title} (Current / Temp)")

    axes2[0].plot(t_sim / 60.0, out["I_batt"], lw=1.6, label="I_batt (sim)")
    axes2[0].plot(t_sim / 60.0, bat_i_on_sim, lw=1.2, alpha=0.8, label="I_batt (log)")
    axes2[0].set_ylabel("Current (A)")
    axes2[0].grid(True, alpha=0.25)
    axes2[0].legend(loc="best")
    _metric_box(axes2[0], m_i)

    axes2[1].plot(t_sim / 60.0, out["Temp"], lw=1.6, label="Temp (sim)")
    axes2[1].plot(t_sim / 60.0, bat_t_on_sim, lw=1.2, alpha=0.8, label="Temp (log)")
    axes2[1].plot(t_sim / 60.0, OAT_C, lw=1.0, alpha=0.6, label="OAT (input)")
    axes2[1].set_ylabel("Temp (°C)")
    axes2[1].grid(True, alpha=0.25)
    axes2[1].legend(loc="best")
    _metric_box(axes2[1], m_t)
    axes2[1].set_xlabel("Time (min)")

    plt.tight_layout()
    plt.show()


# ============================================================
# Plot all
# ============================================================
def plot_all(wps: np.ndarray,
             out: Dict[str, np.ndarray],
             flight: Dict[str, np.ndarray],
             t_ref: np.ndarray,
             OAT_ref: np.ndarray,
             cfg: SimConfig):

    plot_ground_track(wps, out)
    plot_altitude(out, flight, cfg)
    plot_speed(out, flight, cfg)
    plot_power_signals(out, flight, cfg)
    plot_rpm(out, flight, cfg)
    plot_thrust(out, flight)
    plot_battery(out, flight, t_ref, OAT_ref, cfg)
