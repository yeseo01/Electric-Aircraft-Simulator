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
    """2D waypoint polyline의 누적 수평거리 [m]."""
    if len(wps) == 0:
        return np.zeros(0, dtype=float)
    if len(wps) == 1:
        return np.zeros(1, dtype=float)
    seg = np.diff(wps[:, :2], axis=0)
    seg_len = np.linalg.norm(seg, axis=1)
    return np.concatenate(([0.0], np.cumsum(seg_len)))


def project_xy_progress(x: float, y: float, wps: np.ndarray, s_wps: np.ndarray) -> float:
    """
    현재 2D 위치를 waypoint polyline에 사영해 누적 진행거리 s_now [m]를 반환.
    """
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

    """
    point-mass ODE (3-DOF navigation + point-mass):

      x_dot = V cos(gamma) cos(beta)
      y_dot = V cos(gamma) sin(beta)
      h_dot = V sin(gamma)

      V_dot     = (T - D)/m - g sin(gamma)
      gamma_dot = (L cos(mu))/(mV) - (g/V) cos(gamma)
      beta_dot  = (L sin(mu))/(mV cos(gamma))

    - 여기서는 gamma_cmd를 따라가게 만들기 위해 CL을 스케줄링하고,
      그 CL로 L,D를 계산해서 EOM에 넣는다.
    """
    st = State.from_vec(x)

    # 지상/비행 모드에 따라 다른 동역학 사용
    if is_ground:
        # 현재는 간단한 지상 모델만 사용
        V = max(1e-3, float(st.V))
        beta = float(st.beta)

        m = float(p.m)
        g = float(p.g)
        if is_landing_roll:
            # 하강 후 지상: 브레이크 마찰, 공기저항 강화
            mu_ground = float(cfg.GROUND_ROLL_AFTER_DESCENT_MU_GROUND)
            Cd_ground = float(cfg.GROUND_ROLL_AFTER_DESCENT_CD_GROUND)
        else:
            # 상승 전 지상 구간(이륙 롤): config에서 설정한 기본 마찰/공기저항 사용
            mu_ground = float(cfg.GROUND_ROLL_BEFORE_CLIMB_MU_GROUND)
            Cd_ground = float(cfg.GROUND_ROLL_BEFORE_CLIMB_CD_GROUND)
        # 수정전: F_ground = mu_ground * m * g
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
        # 지상활주에서도 heading 제어 입력(mu)이 반영되도록 yaw-rate 모델 적용
        beta_dot = (p.g / V) * np.tan(mu)
        gamma_dot = 0.0
    else:
        # 비행 구간: 기존 point-mass EOM
        # (1) gamma_cmd 추종용 CL 스케줄링
        CL_req, _ = schedule_CL_for_gamma(st, mu, gamma_cmd, p, cfg)

        # (2) 공력 및 thrust 반영
        L, D, T, _ = aero_from_CL(st.V, p.rho, p, CL_req, thrust_N, cfg, gamma=st.gamma)
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

    """RK4 1-step 적분"""
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

    """
    폐루프 시뮬레이션 루프

    각 스텝:
      1) rho 업데이트 (alt_abs, OAT 기반)
      2) guidance -> (beta_d, h_d)
      3) control -> (mu, gamma_cmd)
      4) power controller -> P_shaft_cmd
      5) powertrain.step -> thrust + battery update
      6) RK4 적분
      7) 로그 저장
    """
    # 초기 상태 (첫 waypoint에서 시작)
    beta0 = 0.0
    gamma0 = 0.0
    if wps.shape[0] >= 2:
        k_dir = min(wps.shape[0] - 1, 1)  # ground_roll이 어느 정도 진행된 지점 사용
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

    # powertrain state
    pt_state = PowertrainState(
        soc=float(cfg.INIT_SOC),
        temp_c=float(cfg.INIT_TEMP_C),
        vp_v=0.0,
    )

    t = 1.0
    wp_idx = 1 if wps.shape[0] >= 2 else 0
    s_wps_xy = build_xy_progress_table(wps)


    # logs
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

    # battery/power logs
    SOC_hist: List[float] = []
    Temp_hist: List[float] = []
    Vp_hist: List[float] = []
    Vdc_hist: List[float] = []
    I_hist: List[float] = []

    P_cmd_hist: List[float] = []
    P_elec_hist: List[float] = []
    P_shaft_hist: List[float] = []
    P_prop_hist: List[float] = []

    # phase at sim time
    phase_hist: List[str] = []

    # 하강 후 지상(랜딩 롤) 구간 판별용
    seen_descent = False
    phase_prev = ""
    climb_start_h = float(st.h)
    # MTOP(최대 이륙 출력) 누적 사용 시간 [s]
    mtop_used_s = 0.0

    # 로그 기반 실제 IAS를 시뮬 시간축에 보간하기 위한 준비
    use_real_ias = (
        t_log is not None
        and IAS_log is not None
        and len(t_log) == len(IAS_log)
        and len(t_log) >= 2
    )
    t_log_arr = None
    IAS_log_arr = None
    if use_real_ias:
        t_log_arr = np.asarray(t_log, dtype=float)
        IAS_log_arr = np.asarray(IAS_log, dtype=float)

    # phase(time) → 속도제어 파라미터용 phase 문자열
    phase_arr = None
    if phase_log is not None and t_log is not None and len(phase_log) == len(t_log):
        phase_arr = np.asarray(phase_log)

    while t < float(t_max):
        dt = float(cfg.DT_SIM)

        # (1) abs altitude & rho update (for aero scheduling)
        alt_abs = float(alt0_abs_m + st.h)
        Tamb = float(np.interp(t, t_ref, OAT_ref))
        p.rho = float(powertrain.rho_func(t, alt_abs))

        # (2) guidance
        g_out = guidance_waypoints(st, wps, wp_idx, cfg, t, t_wps)
        wp_idx = int(g_out.wp_idx)

        # (디버깅용-삭제절대금지)
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

        # (3) control
        mu = control_mu(st, g_out.beta_d, p, cfg)
        gamma_cmd = control_gamma_cmd(st, g_out.h_d, cfg)

        # (4) 현재 CL/CD
        CL_now, CD_now = schedule_CL_for_gamma(st, mu, gamma_cmd, p, cfg)

        # (5) power controller
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

        # phase/time 기반 power cap
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

        # (6) powertrain step
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

        # (7) integrate
        st = State.from_vec(
            rk4_step(t, st.vec(), mu, gamma_cmd, dt, p, T_now, cfg, is_ground, flight_drag_scale, is_landing_roll)
        )
        st.beta = wrap_to_pi(st.beta)

        # clamp V for stability
        st.V = float(clamp(st.V, float(cfg.V_MIN_MS), float(cfg.V_MAX_MS)))

        # update powertrain internal state
        pt_state = PowertrainState(
            soc=float(pt_out.soc_next),
            temp_c=float(pt_out.temp_next_c),
            vp_v=float(pt_out.vp_next_v),
        )

        # advance time
        t += dt

        # (8) logs
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

        # 종료 조건
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

        # battery/power logs
        "SOC": np.asarray(SOC_hist, dtype=float),
        "Temp": np.asarray(Temp_hist, dtype=float),
        "Vp": np.asarray(Vp_hist, dtype=float),
        "Vdc": np.asarray(Vdc_hist, dtype=float),
        "I_batt": np.asarray(I_hist, dtype=float),

        "P_cmd": np.asarray(P_cmd_hist, dtype=float),
        "P_elec": np.asarray(P_elec_hist, dtype=float),
        "P_shaft": np.asarray(P_shaft_hist, dtype=float),
        "P_prop": np.asarray(P_prop_hist, dtype=float),

        # phase at simulation times
        "phase_at_sim": np.asarray(phase_hist, dtype=str),
    }
