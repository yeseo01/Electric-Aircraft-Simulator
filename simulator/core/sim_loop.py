from __future__ import annotations
from typing import Dict, List
from math import sin, cos, sqrt
import numpy as np

from ..config import SimConfig
from ..schemas import State, ParamsPM
from .utils import wrap_to_pi, clamp
from .guidance import guidance_waypoints
from .control import control_mu, control_gamma_cmd, PowerController
from .aero import schedule_CL_for_gamma, aero_from_CL
from ..powertrain.system import Powertrain, PowertrainState


# ============================================================
# Dynamics (EOM) + Integrator
# ============================================================

def build_xy_progress_table(wps: np.ndarray) -> np.ndarray:
    """Return cumulative horizontal distance along a 2D waypoint polyline [m]."""
    if len(wps) == 0:
        return np.zeros(0, dtype=float)
    if len(wps) == 1:
        return np.zeros(1, dtype=float)
    seg = np.diff(wps[:, :2], axis=0)
    seg_len = np.linalg.norm(seg, axis=1)
    return np.concatenate(([0.0], np.cumsum(seg_len)))


def project_xy_progress(x: float, y: float, wps: np.ndarray, s_wps: np.ndarray) -> float:
    """Project a 2D position onto the waypoint polyline and return cumulative path progress [m]."""
    n = int(wps.shape[0])
    if n <= 1:
        return 0.0

    px = float(x)
    py = float(y)
    best_dist2 = float("inf")
    best_s = 0.0

    for i in range(n - 1):
        ax = float(wps[i, 0])
        ay = float(wps[i, 1])
        bx = float(wps[i + 1, 0])
        by = float(wps[i + 1, 1])
        abx = bx - ax
        aby = by - ay
        ab2 = abx * abx + aby * aby

        if ab2 <= 1e-12:
            tau = 0.0
            qx = ax
            qy = ay
        else:
            tau = ((px - ax) * abx + (py - ay) * aby) / ab2
            tau = float(clamp(tau, 0.0, 1.0))
            qx = ax + tau * abx
            qy = ay + tau * aby

        dx = px - qx
        dy = py - qy
        dist2 = dx * dx + dy * dy
        if dist2 < best_dist2:
            best_dist2 = dist2
            seg_len = sqrt(ab2)
            best_s = float(s_wps[i] + tau * seg_len)

    return best_s

def rhs(
    t: float,
    x: np.ndarray,
    mu: float,
    gamma_cmd: float,
    p: ParamsPM,
    thrust_N: float,
    cfg: SimConfig,
    is_ground: bool,
    flight_drag_scale: float = 1.0,
    is_landing_roll: bool = False,
    ) -> np.ndarray:

    """Evaluate the point-mass equations of motion.

    The state derivatives are:

        x_dot = V cos(gamma) cos(beta)
        y_dot = V cos(gamma) sin(beta)
        h_dot = V sin(gamma)

        V_dot     = (T - D) / m - g sin(gamma)
        gamma_dot = (L cos(mu)) / (m V) - (g / V) cos(gamma)
        beta_dot  = (L sin(mu)) / (m V cos(gamma))

    Lift coefficient is scheduled to track ``gamma_cmd``, and the
    resulting lift and drag forces are applied to the equations of motion.
    """
    st = State.from_vec(x)

    # Use separate dynamics for ground and flight phases.
    if is_ground:
        # Use a simplified ground-dynamics model.
        V = max(1e-3, float(st.V))
        beta = float(st.beta)

        m = float(p.m)
        g = float(p.g)
        if is_landing_roll:
            # Landing roll: apply braking friction and increased aerodynamic drag.
            mu_ground = float(cfg.GROUND_ROLL_AFTER_DESCENT_MU_GROUND)
            Cd_ground = float(cfg.GROUND_ROLL_AFTER_DESCENT_CD_GROUND)
        else:
            # Takeoff roll: use the configured ground-friction and drag parameters.
            mu_ground = float(cfg.GROUND_ROLL_BEFORE_CLIMB_MU_GROUND)
            Cd_ground = float(cfg.GROUND_ROLL_BEFORE_CLIMB_CD_GROUND)

        CL_ground, _ = schedule_CL_for_gamma(st, mu, gamma_cmd, p, cfg)
        q_ground = 0.5 * float(p.rho) * V * V
        L_est = q_ground * p.S * float(CL_ground)
        N_ground = max(0.0, m * g - L_est)
        F_ground = mu_ground * N_ground
        F_drag = q_ground * p.S * Cd_ground

        x_dot = V * cos(beta)
        y_dot = V * sin(beta)
        h_dot = 0.0

        T = float(thrust_N)
        V_dot = (T - F_ground - F_drag) / m
        # Apply a yaw-rate approximation so bank command affects ground heading.
        beta_dot = (p.g / V) * np.tan(mu)
        gamma_dot = 0.0
    else:
        # Flight phase: point-mass equations of motion.
        # Schedule CL to track the flight-path-angle command.
        CL_req, _ = schedule_CL_for_gamma(st, mu, gamma_cmd, p, cfg)

        # Compute aerodynamic forces and apply thrust.
        L, D, T, _ = aero_from_CL(st.V, p.rho, p, CL_req, thrust_N, cfg)
        D *= float(max(0.1, flight_drag_scale))

        V = max(1e-3, float(st.V))
        beta = float(st.beta)
        gamma = float(st.gamma)

        x_dot = V * cos(gamma) * cos(beta)
        y_dot = V * cos(gamma) * sin(beta)
        h_dot = V * sin(gamma)

        V_dot = (T - D) / p.m - p.g * sin(gamma)

        cos_gamma = max(1e-3, cos(gamma))
        gamma_dot = (L * cos(mu)) / (p.m * V) - (p.g / V) * cos(gamma)
        beta_dot  = (L * sin(mu)) / (p.m * V * cos_gamma)

    return np.array([x_dot, y_dot, h_dot, V_dot, beta_dot, gamma_dot], dtype=float)


def rk4_step(
    t: float,
    x: np.ndarray,
    mu: float,
    gamma_cmd: float,
    dt: float,
    p: ParamsPM,
    thrust_N: float,
    cfg: SimConfig,
    is_ground: bool,
    flight_drag_scale: float = 1.0,
    is_landing_roll: bool = False,
    ) -> np.ndarray:

    """Advance the state by one RK4 integration step."""
    k1 = rhs(t, x, mu, gamma_cmd, p, thrust_N, cfg, is_ground, flight_drag_scale, is_landing_roll)
    k2 = rhs(t + 0.5 * dt, x + 0.5 * dt * k1, mu, gamma_cmd, p, thrust_N, cfg, is_ground, flight_drag_scale, is_landing_roll)
    k3 = rhs(t + 0.5 * dt, x + 0.5 * dt * k2, mu, gamma_cmd, p, thrust_N, cfg, is_ground, flight_drag_scale, is_landing_roll)
    k4 = rhs(t + dt, x + dt * k3, mu, gamma_cmd, p, thrust_N, cfg, is_ground, flight_drag_scale, is_landing_roll)
    return x + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


# ============================================================
# Main simulation loop
# ============================================================

def simulate_flight(
    wps: np.ndarray,
    t_wps: np.ndarray,
    t_max: float,
    p: ParamsPM,
    cfg: SimConfig,
    power_ctrl: PowerController,
    powertrain: Powertrain,
    t_ref: np.ndarray,
    OAT_ref: np.ndarray,
    alt0_abs_m: float,
    t_log: np.ndarray | None = None,
    IAS_log: np.ndarray | None = None,
    phase_log: np.ndarray | None = None,
    ) -> Dict[str, np.ndarray]:

    """Run the closed-loop flight and powertrain simulation.

    At each simulation step:
        1. Update absolute altitude and air density.
        2. Compute waypoint-guidance targets.
        3. Compute flight-control commands.
        4. Compute the shaft-power command.
        5. Advance the powertrain and battery models.
        6. Integrate the aircraft state with RK4.
        7. Record simulation outputs.
    """
    # Initialize the aircraft state at the first waypoint.
    beta0 = 0.0
    gamma0 = 0.0
    if wps.shape[0] >= 2:
        k_dir = min(wps.shape[0] - 1, 1)  # Use the next waypoint to initialize ground-roll heading.
        dx = float(wps[k_dir, 0] - wps[0, 0])
        dy = float(wps[k_dir, 1] - wps[0, 1])
        beta0 = float(np.arctan2(dy, dx))

    st = State(
        x=float(wps[0, 0]),
        y=float(wps[0, 1]),
        h=float(wps[0, 2]),
        V=float(cfg.V0),
        beta=beta0,
        gamma=gamma0,
        )

    # Initialize powertrain state.
    pt_state = PowertrainState(
        soc=float(cfg.INIT_SOC),
        temp_c=float(cfg.INIT_TEMP_C),
        vp_v=0.0,
    )

    t = 1.0
    wp_idx = 1 if wps.shape[0] >= 2 else 0
    s_wps_xy = build_xy_progress_table(wps)


    # Simulation histories.
    times: List[float] = []
    states: List[np.ndarray] = []

    mu_hist: List[float] = []
    gamma_cmd_hist: List[float] = []
    wp_idxs: List[int] = []
    wp_dists: List[float] = []

    thrust_hist: List[float] = []
    rpm_hist: List[float] = []
    ok_hist: List[bool] = []

    CL_hist: List[float] = []
    CD_hist: List[float] = []

    rho_hist: List[float] = []
    alt_abs_hist: List[float] = []

    # Battery and power histories.
    SOC_hist: List[float] = []
    Temp_hist: List[float] = []
    Vp_hist: List[float] = []
    Vdc_hist: List[float] = []
    I_hist: List[float] = []

    P_cmd_hist: List[float] = []
    P_elec_hist: List[float] = []
    P_shaft_hist: List[float] = []
    P_prop_hist: List[float] = []

    # Phase history at simulation times.
    phase_hist: List[str] = []

    # Track whether a subsequent ground-roll phase is a landing roll.
    seen_descent = False
    phase_prev = ""
    climb_start_h = float(st.h)
    # Cumulative maximum-takeoff-power usage [s].
    mtop_used_s = 0.0

    # Shared log time axis used by phase control and optional IAS diagnostics.
    t_log_arr = None
    if t_log is not None and len(t_log) >= 1:
        t_log_arr = np.asarray(t_log, dtype=float)

    # IAS is optional and is used only for diagnostic comparison.
    use_real_ias = (
        t_log_arr is not None
        and IAS_log is not None
        and len(t_log_arr) == len(IAS_log)
        and len(t_log_arr) >= 2
    )
    IAS_log_arr = None
    if use_real_ias:
        IAS_log_arr = np.asarray(IAS_log, dtype=float)

    # Optional phase labels used by phase-dependent control.
    phase_arr = None
    if (
        phase_log is not None
        and t_log_arr is not None
        and len(phase_log) == len(t_log_arr)
    ):
        phase_arr = np.asarray(phase_log)

    while t < float(t_max):
        dt = float(cfg.DT_SIM)

        # Update absolute altitude and air density.
        alt_abs = float(alt0_abs_m + st.h)
        Tamb = float(np.interp(t, t_ref, OAT_ref))
        p.rho = float(powertrain.rho_func(t, alt_abs))

        # Compute guidance targets.
        g_out = guidance_waypoints(st, wps, wp_idx, cfg, t, t_wps)
        wp_idx = int(g_out.wp_idx)

        # Optional guidance diagnostics within the configured logging window.
        t_norm = float(t) / float(t_max) if t_max > 0.0 else 0.0
        if (
            t_norm >= float(cfg.WP_DIST_LOG_T_START_FRAC)
            and t_norm <= float(cfg.WP_DIST_LOG_T_END_FRAC)
        ):
            phase_for_log = ""
            if phase_arr is not None and t_log_arr is not None:
                idx_phase_log = int(np.searchsorted(t_log_arr, float(t), side="right") - 1)
                idx_phase_log = int(clamp(idx_phase_log, 0, len(phase_arr) - 1))
                phase_for_log = (str(phase_arr[idx_phase_log]) or "").lower().strip()

            t_wp_cur = float(t_wps[wp_idx])
            t_wp_next = float(t_wps[wp_idx + 1]) if wp_idx < wps.shape[0] - 1 else float("nan")
            V_now_kt = float(st.V * cfg.MS2KT)
            V_real_kt = float(np.interp(t, t_log_arr, IAS_log_arr)) if use_real_ias else float("nan")
            beta_now_deg = float(np.degrees(st.beta))
            beta_cmd_deg = float(np.degrees(g_out.beta_d))
            beta_err_deg = float(np.degrees(wrap_to_pi(g_out.beta_d - st.beta)))

            print(
                f"[guidance] t={t:7.2f}s "
                f"| t_wp_cur={t_wp_cur:7.2f}s | t_wp_next={t_wp_next:7.2f}s "
                f"| wp_idx={wp_idx:4d}/{wps.shape[0]-1:4d}"
                f"| V_sim={V_now_kt:6.2f}kt "
                f"| V_real={V_real_kt:6.2f}kt "
                f"| beta={beta_now_deg:7.2f}deg | beta_d={beta_cmd_deg:7.2f}deg "
                f"| e_beta={beta_err_deg:7.2f}deg "
                f"| phase={phase_for_log}"
            )

        # Compute flight-control commands.
        mu = control_mu(st, g_out.beta_d, p, cfg)
        gamma_cmd = control_gamma_cmd(st, g_out.h_d, cfg)

        # Compute the current lift and drag coefficients.
        CL_now, CD_now = schedule_CL_for_gamma(st, mu, gamma_cmd, p, cfg)

        # Apply phase-dependent power control.
        V_ref_ms_phase = None
        KP_phase = None
        P_base_phase = None
        is_ground = False
        is_landing_roll = False
        flight_drag_scale = 1.0
        phase_now = ""
        control_phase = ""
        if phase_arr is not None and t_log_arr is not None:
            idx_phase = int(np.searchsorted(t_log_arr, float(t), side="right") - 1)
            idx_phase = int(clamp(idx_phase, 0, len(phase_arr) - 1))
            phase_now = (str(phase_arr[idx_phase]) or "").lower().strip()

            if phase_now == "descent":
                seen_descent = True

            if phase_now != phase_prev:
                if phase_now == "climb":
                    climb_start_h = float(st.h)
                phase_prev = phase_now

            if phase_now == "ground_roll":
                is_ground = True
                if seen_descent:
                    is_landing_roll = True
                    control_phase = "landing_roll"
                    V_ref_ms_phase = float(cfg.PHASE_GROUND_AFTER_DESCENT_VREF_KT * cfg.KT2MS)
                    KP_phase = float(cfg.PHASE_GROUND_AFTER_DESCENT_KP_P)
                    P_base_phase = float(cfg.PHASE_GROUND_AFTER_DESCENT_P_BASE_W)
                else:
                    control_phase = "ground_roll"
                    V_ref_ms_phase = float(cfg.PHASE_GROUND_BEFORE_CLIMB_VREF_KT * cfg.KT2MS)
                    KP_phase = float(cfg.PHASE_GROUND_BEFORE_CLIMB_KP_P)
                    P_base_phase = float(cfg.PHASE_GROUND_BEFORE_CLIMB_P_BASE_W)

            elif phase_now == "climb":
                v_now_kt = float(st.V * cfg.MS2KT)
                climb_gain_m = float(st.h - climb_start_h)
                is_initial_climb = (
                    climb_gain_m <= float(cfg.INITIAL_CLIMB_MAX_ALT_GAIN_M)
                    and v_now_kt <= float(cfg.PHASE_CLIMB_VREF_KT)
                )
                if is_initial_climb:
                    control_phase = "initial_climb"
                    V_ref_ms_phase = float(cfg.PHASE_INITIAL_CLIMB_VREF_KT * cfg.KT2MS)
                    KP_phase = float(cfg.PHASE_INITIAL_CLIMB_KP_P)
                    P_base_phase = float(cfg.PHASE_INITIAL_CLIMB_P_BASE_W)
                else:
                    control_phase = "climb"
                    V_ref_ms_phase = float(cfg.PHASE_CLIMB_VREF_KT * cfg.KT2MS)
                    KP_phase = float(cfg.PHASE_CLIMB_KP_P)
                    P_base_phase = float(cfg.PHASE_CLIMB_P_BASE_W)

            elif phase_now == "cruise":
                control_phase = "cruise"
                V_ref_ms_phase = float(cfg.PHASE_CRUISE_VREF_KT * cfg.KT2MS)
                KP_phase = float(cfg.PHASE_CRUISE_KP_P)
                P_base_phase = float(cfg.PHASE_CRUISE_P_BASE_W)

            elif phase_now == "descent":
                v_now_kt = float(st.V * cfg.MS2KT)
                if v_now_kt <= float(cfg.APPROACH_TO_FINAL_V_KT):
                    control_phase = "final"
                    V_ref_ms_phase = float(cfg.PHASE_FINAL_VREF_KT * cfg.KT2MS)
                    KP_phase = float(cfg.PHASE_FINAL_KP_P)
                    P_base_phase = float(cfg.PHASE_FINAL_P_BASE_W)
                    flight_drag_scale = float(cfg.FLIGHT_DRAG_SCALE_FINAL)
                else:
                    control_phase = "approach"
                    V_ref_ms_phase = float(cfg.PHASE_APPROACH_VREF_KT * cfg.KT2MS)
                    KP_phase = float(cfg.PHASE_APPROACH_KP_P)
                    P_base_phase = float(cfg.PHASE_APPROACH_P_BASE_W)
                    flight_drag_scale = float(cfg.FLIGHT_DRAG_SCALE_APPROACH)

            else:
                control_phase = phase_now

        if (
            bool(getattr(cfg, "PATH_PROGRESS_SPEED_RECOVERY_ENABLE", True))
            and (not is_ground)
            and V_ref_ms_phase is not None
            and len(s_wps_xy) == len(t_wps)
            and len(s_wps_xy) >= 2
        ):
            s_ref = float(np.interp(float(t), np.asarray(t_wps, dtype=float), s_wps_xy))
            s_now = float(project_xy_progress(st.x, st.y, wps, s_wps_xy))
            s_err = s_ref - s_now
            gain = float(getattr(cfg, "PATH_PROGRESS_SPEED_RECOVERY_GAIN", 0.02))
            max_delta_ms = float(getattr(cfg, "PATH_PROGRESS_SPEED_RECOVERY_MAX_DELTA_KT", 15.0)) * float(cfg.KT2MS)
            v_ref_corr = float(V_ref_ms_phase) + gain * s_err
            V_ref_ms_phase = float(np.clip(v_ref_corr, float(V_ref_ms_phase) - max_delta_ms, float(V_ref_ms_phase) + max_delta_ms))

        P_cmd_raw = float(
            power_ctrl(
                t_now=t,
                V_ms=st.V,
                alt_abs_m=alt_abs,
                V_ref_ms=V_ref_ms_phase,
                KP_P_override=KP_phase,
                P_base_W_override=P_base_phase,
            )
        )

        # Apply phase- and duration-dependent power limits.
        phase_for_cap = control_phase
        mtop_allowed_phases = {str(p).lower().strip() for p in cfg.MTOP_ALLOWED_PHASES}
        mtop_phase_allowed = phase_for_cap in mtop_allowed_phases
        mtop_time_left_s = max(0.0, float(cfg.MTOP_MAX_DURATION_S) - float(mtop_used_s))
        allow_mtop_now = mtop_phase_allowed and (mtop_time_left_s > 0.0)
        p_cap_now = float(cfg.P_MTOP_W if allow_mtop_now else cfg.P_MCP_W)

        P_min_use = float(cfg.P_MIN_W)
        P_cmd_raw = float(np.clip(P_cmd_raw, P_min_use, p_cap_now))

        if allow_mtop_now and P_cmd_raw > float(cfg.P_MCP_W):
            mtop_used_s += min(float(cfg.DT_SIM), mtop_time_left_s)

        # Advance the powertrain model.
        pt_out = powertrain.step(
            t_now=t,
            V_ms=float(st.V),
            alt_abs_m=alt_abs,
            Tamb_C=Tamb,
            P_shaft_cmd_W=P_cmd_raw,
            st=pt_state,
            P_max_W=p_cap_now,
        )

        T_now = float(pt_out.thrust_N)

        # Integrate the aircraft state.
        st = State.from_vec(
            rk4_step(t, st.vec(), mu, gamma_cmd, dt, p, T_now, cfg, is_ground, flight_drag_scale, is_landing_roll)
        )
        st.beta = wrap_to_pi(st.beta)

        # Clamp airspeed for numerical stability.
        st.V = float(clamp(st.V, float(cfg.V_MIN_MS), float(cfg.V_MAX_MS)))

        # Update the powertrain state.
        pt_state = PowertrainState(
            soc=float(pt_out.soc_next),
            temp_c=float(pt_out.temp_next_c),
            vp_v=float(pt_out.vp_next_v),
        )

        # Advance simulation time.
        t += dt

        # Record simulation outputs.
        times.append(t)
        states.append(st.vec())

        mu_hist.append(mu)
        gamma_cmd_hist.append(gamma_cmd)
        wp_idxs.append(wp_idx)

        dx = float(wps[wp_idx, 0] - st.x)
        dy = float(wps[wp_idx, 1] - st.y)
        dz = float(wps[wp_idx, 2] - st.h)
        wp_dists.append(float(sqrt(dx * dx + dy * dy + dz * dz)))

        thrust_hist.append(T_now)
        rpm_hist.append(float(pt_out.rpm))
        ok_hist.append(bool(pt_out.bracket_ok))

        CL_hist.append(float(CL_now))
        CD_hist.append(float(CD_now))

        rho_hist.append(float(p.rho))
        alt_abs_hist.append(float(alt0_abs_m + st.h))

        SOC_hist.append(float(pt_state.soc))
        Temp_hist.append(float(pt_state.temp_c))
        Vp_hist.append(float(pt_state.vp_v))
        Vdc_hist.append(float(pt_out.Vdc_V))
        I_hist.append(float(pt_out.I_batt_A))

        P_cmd_hist.append(float(pt_out.P_shaft_cmd_W))
        P_elec_hist.append(float(pt_out.P_elec_deliv_W))
        P_shaft_hist.append(float(pt_out.P_shaft_deliv_W))
        P_prop_hist.append(float(pt_out.P_prop_W))

        phase_hist.append(control_phase if control_phase else phase_now)

        # Termination conditions.
        if wp_idx >= wps.shape[0] - 1:
            break

        if pt_state.soc <= 0.001:
            break

    S = np.vstack(states) if len(states) > 0 else np.zeros((0, 6), dtype=float)
    T_arr = np.asarray(times, dtype=float)

    return {
        "t": T_arr,
        "x": S[:, 0], "y": S[:, 1], "h": S[:, 2],
        "V": S[:, 3], "beta": S[:, 4], "gamma": S[:, 5],

        "mu": np.asarray(mu_hist, dtype=float),
        "gamma_cmd": np.asarray(gamma_cmd_hist, dtype=float),
        "wp_idx": np.asarray(wp_idxs, dtype=int),
        "wp_dist": np.asarray(wp_dists, dtype=float),

        "thrust": np.asarray(thrust_hist, dtype=float),
        "rpm": np.asarray(rpm_hist, dtype=float),
        "bracket_ok": np.asarray(ok_hist, dtype=bool),

        "CL": np.asarray(CL_hist, dtype=float),
        "CD": np.asarray(CD_hist, dtype=float),
        "rho": np.asarray(rho_hist, dtype=float),
        "alt_abs": np.asarray(alt_abs_hist, dtype=float),

        # Battery and power histories.
        "SOC": np.asarray(SOC_hist, dtype=float),
        "Temp": np.asarray(Temp_hist, dtype=float),
        "Vp": np.asarray(Vp_hist, dtype=float),
        "Vdc": np.asarray(Vdc_hist, dtype=float),
        "I_batt": np.asarray(I_hist, dtype=float),

        "P_cmd": np.asarray(P_cmd_hist, dtype=float),
        "P_elec": np.asarray(P_elec_hist, dtype=float),
        "P_shaft": np.asarray(P_shaft_hist, dtype=float),
        "P_prop": np.asarray(P_prop_hist, dtype=float),

        # Phase at each simulation timestamp.
        "phase_at_sim": np.asarray(phase_hist, dtype=str),
    }
