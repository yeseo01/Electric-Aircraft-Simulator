from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import SimConfig
from .core.atmosphere import compute_rho
from .core.control import PowerController, control_gamma_cmd, control_mu
from .core.guidance import guidance_waypoints
from .core.io_flight import build_oat_input, load_flight_csv, make_waypoints_from_csv
from .core.sim_loop import build_xy_progress_table, project_xy_progress, rk4_step
from .core.utils import clamp, wrap_to_pi
from .powertrain.prop import PropellerModel
from .powertrain.system import Powertrain, PowertrainState
from .schemas import FlightScenario, ParamsPM, State, TelemetryFrame


@dataclass
class FlightSimulator:
    """
    Product-facing incremental simulator API.

    `step()` now executes one physics/control/powertrain update and immediately
    returns a TelemetryFrame. The older batch `simulate_flight()` function remains
    available for comparisons and plotting workflows.
    """
    cfg: SimConfig
    scenario: FlightScenario
    verbose: bool = False

    def __post_init__(self) -> None:
        if self.scenario.flight_csv_path:
            self.cfg.FLIGHT_CSV_PATH = self.scenario.flight_csv_path
        self.reset()

    @classmethod
    def from_config(
        cls,
        cfg: SimConfig | None = None,
        scenario: FlightScenario | None = None,
        verbose: bool = False,
    ) -> "FlightSimulator":
        return cls(
            cfg=cfg if cfg is not None else SimConfig(),
            scenario=scenario if scenario is not None else FlightScenario(),
            verbose=verbose,
        )

    def reset(self) -> None:
        cfg = self.cfg
        self.flight = load_flight_csv(cfg.FLIGHT_CSV_PATH)
        self.wps, self.t_wps = make_waypoints_from_csv(
            self.flight["t"],
            self.flight["lat"],
            self.flight["lon"],
            self.flight["alt"],
            downsample_sec=float(cfg.DOWNSAMPLE_SEC),
        )
        self.t_max = float(cfg.TMAX_SCALE) * float(self.t_wps[-1])
        self.t_ref = np.arange(0.0, self.t_max + cfg.DT_SIM, cfg.DT_SIM, dtype=float)
        self.oat_ref = build_oat_input(self.flight, self.t_ref, cfg)
        self.alt0_abs_m = float(self.flight["alt"][0])

        self.params = ParamsPM(
            g=9.80665,
            rho=1.225,
            m=float(cfg.MASS_KG),
            S=float(cfg.S_WING),
            dt=float(cfg.DT_SIM),
        )
        self.power_ctrl = PowerController(cfg)
        prop = PropellerModel.load_surrogate(
            npz_path=cfg.PROP_NPZ_PATH,
            eta_clip=cfg.ETA_CLIP,
            eta_fallback=cfg.ETA_FALLBACK_CONST,
            P_cap_W=cfg.P_MTOP_W,
            V_min_for_thrust=cfg.V_MIN_FOR_THRUST,
        )
        self.powertrain = Powertrain(cfg=cfg, rho_func=self._rho_func, prop=prop)

        beta0 = 0.0
        if self.wps.shape[0] >= 2:
            k_dir = min(self.wps.shape[0] - 1, 1)
            dx = float(self.wps[k_dir, 0] - self.wps[0, 0])
            dy = float(self.wps[k_dir, 1] - self.wps[0, 1])
            beta0 = float(np.arctan2(dy, dx))

        self.state = State(
            x=float(self.wps[0, 0]),
            y=float(self.wps[0, 1]),
            h=float(self.wps[0, 2]),
            V=float(cfg.V0),
            beta=beta0,
            gamma=0.0,
        )
        self.powertrain_state = PowertrainState(
            soc=float(cfg.INIT_SOC),
            temp_c=float(cfg.INIT_TEMP_C),
            vp_v=0.0,
        )

        self.t = 1.0
        self.wp_idx = 1 if self.wps.shape[0] >= 2 else 0
        self.s_wps_xy = build_xy_progress_table(self.wps)

        self.seen_descent = False
        self.phase_prev = ""
        self.climb_start_h = float(self.state.h)
        self.mtop_used_s = 0.0

        self.t_log_arr = self.flight["t"] - float(self.flight["t"][0])
        self.ias_log_arr = np.asarray(self.flight["IAS"], dtype=float)
        self.use_real_ias = (
            len(self.t_log_arr) == len(self.ias_log_arr)
            and len(self.t_log_arr) >= 2
        )
        self.phase_arr = None
        if "phase" in self.flight and len(self.flight["phase"]) == len(self.t_log_arr):
            self.phase_arr = np.asarray(self.flight["phase"])

        self._finished = self.t >= self.t_max

    @property
    def finished(self) -> bool:
        return self._finished

    def step(self) -> TelemetryFrame | None:
        if self._finished:
            return None

        frame = self._step_once()
        if self.wp_idx >= self.wps.shape[0] - 1:
            self._finished = True
        if self.powertrain_state.soc <= 0.001:
            self._finished = True
        if self.t >= self.t_max:
            self._finished = True
        return frame

    def run_all(self) -> list[TelemetryFrame]:
        frames: list[TelemetryFrame] = []
        while True:
            frame = self.step()
            if frame is None:
                break
            frames.append(frame)
        return frames

    def _rho_func(self, t_now: float, alt_abs_m: float) -> float:
        oat = float(np.interp(float(t_now), self.t_ref, self.oat_ref))
        return float(compute_rho(float(alt_abs_m), oat))

    def _step_once(self) -> TelemetryFrame:
        cfg = self.cfg
        params = self.params
        state = self.state
        t = float(self.t)
        dt = float(cfg.DT_SIM)

        alt_abs = float(self.alt0_abs_m + state.h)
        tamb = float(np.interp(t, self.t_ref, self.oat_ref))
        params.rho = float(self.powertrain.rho_func(t, alt_abs))

        g_out = guidance_waypoints(state, self.wps, self.wp_idx, cfg, t, self.t_wps)
        self.wp_idx = int(g_out.wp_idx)
        if self.verbose:
            self._print_guidance_debug(t, g_out)

        mu = control_mu(state, g_out.beta_d, params, cfg)
        gamma_cmd = control_gamma_cmd(state, g_out.h_d, cfg)
        (
            v_ref_ms_phase,
            kp_phase,
            p_base_phase,
            is_ground,
            is_landing_roll,
            flight_drag_scale,
            phase_now,
            control_phase,
        ) = self._phase_control_inputs(t)

        if (
            bool(getattr(cfg, "PATH_PROGRESS_SPEED_RECOVERY_ENABLE", True))
            and (not is_ground)
            and v_ref_ms_phase is not None
            and len(self.s_wps_xy) == len(self.t_wps)
            and len(self.s_wps_xy) >= 2
        ):
            s_ref = float(np.interp(t, np.asarray(self.t_wps, dtype=float), self.s_wps_xy))
            s_now = float(project_xy_progress(state.x, state.y, self.wps, self.s_wps_xy))
            s_err = s_ref - s_now
            gain = float(getattr(cfg, "PATH_PROGRESS_SPEED_RECOVERY_GAIN", 0.02))
            max_delta_ms = float(getattr(cfg, "PATH_PROGRESS_SPEED_RECOVERY_MAX_DELTA_KT", 15.0)) * float(cfg.KT2MS)
            v_ref_corr = float(v_ref_ms_phase) + gain * s_err
            v_ref_ms_phase = float(np.clip(v_ref_corr, float(v_ref_ms_phase) - max_delta_ms, float(v_ref_ms_phase) + max_delta_ms))

        p_cmd_raw = float(
            self.power_ctrl(
                t_now=t,
                V_ms=state.V,
                alt_abs_m=alt_abs,
                V_ref_ms=v_ref_ms_phase,
                KP_P_override=kp_phase,
                P_base_W_override=p_base_phase,
            )
        )

        phase_for_cap = control_phase
        mtop_allowed_phases = {str(p).lower().strip() for p in cfg.MTOP_ALLOWED_PHASES}
        mtop_phase_allowed = phase_for_cap in mtop_allowed_phases
        mtop_time_left_s = max(0.0, float(cfg.MTOP_MAX_DURATION_S) - float(self.mtop_used_s))
        allow_mtop_now = mtop_phase_allowed and (mtop_time_left_s > 0.0)
        p_cap_now = float(cfg.P_MTOP_W if allow_mtop_now else cfg.P_MCP_W)

        p_cmd_raw = float(np.clip(p_cmd_raw, float(cfg.P_MIN_W), p_cap_now))
        if allow_mtop_now and p_cmd_raw > float(cfg.P_MCP_W):
            self.mtop_used_s += min(float(cfg.DT_SIM), mtop_time_left_s)

        pt_out = self.powertrain.step(
            t_now=t,
            V_ms=float(state.V),
            alt_abs_m=alt_abs,
            Tamb_C=tamb,
            P_shaft_cmd_W=p_cmd_raw,
            st=self.powertrain_state,
            P_max_W=p_cap_now,
        )
        thrust_now = float(pt_out.thrust_N)

        next_state = State.from_vec(
            rk4_step(t, state.vec(), mu, gamma_cmd, dt, params, thrust_now, cfg, is_ground, flight_drag_scale, is_landing_roll)
        )
        next_state.beta = wrap_to_pi(next_state.beta)
        next_state.V = float(clamp(next_state.V, float(cfg.V_MIN_MS), float(cfg.V_MAX_MS)))

        self.powertrain_state = PowertrainState(
            soc=float(pt_out.soc_next),
            temp_c=float(pt_out.temp_next_c),
            vp_v=float(pt_out.vp_next_v),
        )
        self.state = next_state
        self.t = t + dt

        phase = control_phase if control_phase else phase_now
        return TelemetryFrame(
            timestamp=float(self.t),
            x_m=float(next_state.x),
            y_m=float(next_state.y),
            altitude_m=float(self.alt0_abs_m + next_state.h),
            airspeed_mps=float(next_state.V),
            heading_rad=float(next_state.beta),
            flight_path_angle_rad=float(next_state.gamma),
            soc=float(self.powertrain_state.soc),
            voltage_v=float(pt_out.Vdc_V),
            current_a=float(pt_out.I_batt_A),
            battery_temperature_c=float(self.powertrain_state.temp_c),
            rpm=float(pt_out.rpm),
            thrust_n=thrust_now,
            phase=str(phase),
        )

    def _phase_control_inputs(
        self,
        t: float,
    ) -> tuple[float | None, float | None, float | None, bool, bool, float, str, str]:
        cfg = self.cfg
        v_ref_ms_phase = None
        kp_phase = None
        p_base_phase = None
        is_ground = False
        is_landing_roll = False
        flight_drag_scale = 1.0
        phase_now = ""
        control_phase = ""

        if self.phase_arr is None:
            return (
                v_ref_ms_phase,
                kp_phase,
                p_base_phase,
                is_ground,
                is_landing_roll,
                flight_drag_scale,
                phase_now,
                control_phase,
            )

        idx_phase = int(np.searchsorted(self.t_log_arr, float(t), side="right") - 1)
        idx_phase = int(clamp(idx_phase, 0, len(self.phase_arr) - 1))
        phase_now = (str(self.phase_arr[idx_phase]) or "").lower().strip()

        if phase_now == "descent":
            self.seen_descent = True

        if phase_now != self.phase_prev:
            if phase_now == "climb":
                self.climb_start_h = float(self.state.h)
            self.phase_prev = phase_now

        if phase_now == "ground_roll":
            is_ground = True
            if self.seen_descent:
                is_landing_roll = True
                control_phase = "landing_roll"
                v_ref_ms_phase = float(cfg.PHASE_GROUND_AFTER_DESCENT_VREF_KT * cfg.KT2MS)
                kp_phase = float(cfg.PHASE_GROUND_AFTER_DESCENT_KP_P)
                p_base_phase = float(cfg.PHASE_GROUND_AFTER_DESCENT_P_BASE_W)
            else:
                control_phase = "ground_roll"
                v_ref_ms_phase = float(cfg.PHASE_GROUND_BEFORE_CLIMB_VREF_KT * cfg.KT2MS)
                kp_phase = float(cfg.PHASE_GROUND_BEFORE_CLIMB_KP_P)
                p_base_phase = float(cfg.PHASE_GROUND_BEFORE_CLIMB_P_BASE_W)

        elif phase_now == "climb":
            v_now_kt = float(self.state.V * cfg.MS2KT)
            climb_gain_m = float(self.state.h - self.climb_start_h)
            is_initial_climb = (
                climb_gain_m <= float(cfg.INITIAL_CLIMB_MAX_ALT_GAIN_M)
                and v_now_kt <= float(cfg.PHASE_CLIMB_VREF_KT)
            )
            if is_initial_climb:
                control_phase = "initial_climb"
                v_ref_ms_phase = float(cfg.PHASE_INITIAL_CLIMB_VREF_KT * cfg.KT2MS)
                kp_phase = float(cfg.PHASE_INITIAL_CLIMB_KP_P)
                p_base_phase = float(cfg.PHASE_INITIAL_CLIMB_P_BASE_W)
            else:
                control_phase = "climb"
                v_ref_ms_phase = float(cfg.PHASE_CLIMB_VREF_KT * cfg.KT2MS)
                kp_phase = float(cfg.PHASE_CLIMB_KP_P)
                p_base_phase = float(cfg.PHASE_CLIMB_P_BASE_W)

        elif phase_now == "cruise":
            control_phase = "cruise"
            v_ref_ms_phase = float(cfg.PHASE_CRUISE_VREF_KT * cfg.KT2MS)
            kp_phase = float(cfg.PHASE_CRUISE_KP_P)
            p_base_phase = float(cfg.PHASE_CRUISE_P_BASE_W)

        elif phase_now == "descent":
            v_now_kt = float(self.state.V * cfg.MS2KT)
            if v_now_kt <= float(cfg.APPROACH_TO_FINAL_V_KT):
                control_phase = "final"
                v_ref_ms_phase = float(cfg.PHASE_FINAL_VREF_KT * cfg.KT2MS)
                kp_phase = float(cfg.PHASE_FINAL_KP_P)
                p_base_phase = float(cfg.PHASE_FINAL_P_BASE_W)
                flight_drag_scale = float(cfg.FLIGHT_DRAG_SCALE_FINAL)
            else:
                control_phase = "approach"
                v_ref_ms_phase = float(cfg.PHASE_APPROACH_VREF_KT * cfg.KT2MS)
                kp_phase = float(cfg.PHASE_APPROACH_KP_P)
                p_base_phase = float(cfg.PHASE_APPROACH_P_BASE_W)
                flight_drag_scale = float(cfg.FLIGHT_DRAG_SCALE_APPROACH)
        else:
            control_phase = phase_now

        return (
            v_ref_ms_phase,
            kp_phase,
            p_base_phase,
            is_ground,
            is_landing_roll,
            flight_drag_scale,
            phase_now,
            control_phase,
        )

    def _print_guidance_debug(self, t: float, g_out) -> None:
        cfg = self.cfg
        t_norm = float(t) / float(self.t_max) if self.t_max > 0.0 else 0.0
        if not (
            t_norm >= float(cfg.WP_DIST_LOG_T_START_FRAC)
            and t_norm <= float(cfg.WP_DIST_LOG_T_END_FRAC)
        ):
            return

        phase_for_log = ""
        if self.phase_arr is not None:
            idx_phase_log = int(np.searchsorted(self.t_log_arr, float(t), side="right") - 1)
            idx_phase_log = int(clamp(idx_phase_log, 0, len(self.phase_arr) - 1))
            phase_for_log = (str(self.phase_arr[idx_phase_log]) or "").lower().strip()

        t_wp_cur = float(self.t_wps[self.wp_idx])
        t_wp_next = float(self.t_wps[self.wp_idx + 1]) if self.wp_idx < self.wps.shape[0] - 1 else float("nan")
        v_now_kt = float(self.state.V * cfg.MS2KT)
        v_real_kt = float(np.interp(t, self.t_log_arr, self.ias_log_arr)) if self.use_real_ias else float("nan")
        beta_now_deg = float(np.degrees(self.state.beta))
        beta_cmd_deg = float(np.degrees(g_out.beta_d))
        beta_err_deg = float(np.degrees(wrap_to_pi(g_out.beta_d - self.state.beta)))

        print(
            f"[guidance] t={t:7.2f}s "
            f"| t_wp_cur={t_wp_cur:7.2f}s | t_wp_next={t_wp_next:7.2f}s "
            f"| wp_idx={self.wp_idx:4d}/{self.wps.shape[0]-1:4d}"
            f"| V_sim={v_now_kt:6.2f}kt "
            f"| V_real={v_real_kt:6.2f}kt "
            f"| beta={beta_now_deg:7.2f}deg | beta_d={beta_cmd_deg:7.2f}deg "
            f"| e_beta={beta_err_deg:7.2f}deg "
            f"| phase={phase_for_log}"
        )
