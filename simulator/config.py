"""Simulation configuration and model parameters.

Set ``SAVE_SIM_RESULT_CSV`` to True and configure
``SIM_RESULT_CSV_PATH`` to save simulation results to CSV.
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class SimConfig:
    # ============================================================
    # File paths
    # ============================================================
    # Flight-log CSV path
    FLIGHT_CSV_PATH: str = "./data/input/flight_logs/flight_log.csv"
    # Propeller surrogate model path
    PROP_NPZ_PATH: str = "./data/input/prop_surrogate_cp_eta_simready.npz"
    SAVE_SIM_RESULT_CSV: bool = True  # Whether to save simulation results to CSV
    # Simulation-result CSV path
    SIM_RESULT_CSV_PATH: str = "./data/output/simulation_results/simulation_result.csv"

    # ============================================================
    # Simulation time settings
    # ============================================================
    DT_SIM: float = 1.0  # Integration timestep [s]
    DOWNSAMPLE_SEC: float = 1.0  # Flight-log-to-waypoint downsampling interval [s]
    V0: float = 1.0  # Initial airspeed [m/s]
    TMAX_SCALE: float = 1.0  # Simulation-duration scale relative to final waypoint time
    # Enable speed correction based on 2D path-progress error
    PATH_PROGRESS_SPEED_RECOVERY_ENABLE: bool = True
    # Path-progress error [m] to target-speed correction [m/s]
    PATH_PROGRESS_SPEED_RECOVERY_GAIN: float = 0.01
    # Maximum speed correction relative to the base target [kt]
    PATH_PROGRESS_SPEED_RECOVERY_MAX_DELTA_KT: float = 3.0

    # ============================================================
    # Guidance debug logging
    # ============================================================
    # Start logging after this fraction of total simulation time
    WP_DIST_LOG_T_START_FRAC: float = 0.0
    # Stop logging after this fraction of total simulation time
    WP_DIST_LOG_T_END_FRAC: float = 1.0

    # ============================================================
    # Aerodynamics (simple drag polar)
    # ============================================================
    CD0: float = 0.025  # Parasite drag coefficient
    K: float = 0.035  # Induced drag factor
    CL_MIN: float = -0.2  # Minimum lift coefficient
    CL_MAX: float = 1.6  # Maximum lift coefficient near the stall limit
    FLIGHT_DRAG_SCALE_APPROACH: float = 1.0  # Aerodynamic drag scale during approach
    FLIGHT_DRAG_SCALE_FINAL: float = 1.0  # Aerodynamic drag scale during final approach

    # ============================================================
    # Aircraft
    # ============================================================
    MASS_KG: float = 510.0  # Aircraft mass [kg] (HANDBOOK: 510 kg)
    S_WING: float = 9.51  # Wing area [m^2] (HANDBOOK: 9.51 m^2)

    # ============================================================
    # Speed limits
    # ============================================================
    V_MIN_MS: float = 0.0  # Minimum airspeed limit [m/s]
    V_MAX_KT: float = 108.0  # Maximum airspeed limit [kt] (HANDBOOK: V_NE = 108 kt)

    # ============================================================
    # Propulsion limits
    # ============================================================
    RPM_SAFE: float = 2500.0  # Maximum RPM limit (HANDBOOK: Max RPM = 2500)
    # Continuous RPM reference (HANDBOOK: Max continuous RPM = 2300);
    # used for plotting, not enforced as a control limit
    RPM_CONT: float = 2300.0
    # Minimum RPM used by the solver; derived empirically from data
    RPM_SOLVE_MIN: float = 300.0
    P_MCP_W: float = 49.2e3  # Maximum continuous power [W] (HANDBOOK: MCP = 49.2 kW)
    # Maximum takeoff power [W] (HANDBOOK: MTOP = 57.6 kW, 90 s limit)
    P_MTOP_W: float = 57.6e3
    # Maximum cumulative MTOP duration [s] (HANDBOOK: 90 s)
    MTOP_MAX_DURATION_S: float = 90.0
    # Phases in which MTOP may be permitted
    MTOP_ALLOWED_PHASES: Tuple[str, ...] = ("ground_roll", "initial_climb")

    # ============================================================
    # Default speed and power-control settings
    # ============================================================
    V_REF_KT: float = 70.0  # Default target airspeed [kt]
    P_BASE_W: float = 35.0e3  # Common baseline power command [W]
    P_MIN_W: float = 1.0e3  # Common minimum power command [W]
    KP_P: float = 4000.0  # Airspeed-error-to-power gain; simulator tuning value
    TAU_P: float = 2.0  # Power-command low-pass-filter time constant [s]

    # ============================================================
    # Phase-specific speed and power-control settings
    # ============================================================

    # Ground roll before climb
    # Target airspeed (HANDBOOK: 50 KIAS)
    PHASE_GROUND_BEFORE_CLIMB_VREF_KT: float = 50.0
    # Baseline power; simulator tuning value
    PHASE_GROUND_BEFORE_CLIMB_P_BASE_W: float = 50.0e3
    # Airspeed-error-to-power gain; simulator tuning value
    PHASE_GROUND_BEFORE_CLIMB_KP_P: float = 4000.0
    # Ground-friction coefficient; simulator tuning value
    GROUND_ROLL_BEFORE_CLIMB_MU_GROUND: float = 0.5
    # Ground-roll aerodynamic drag coefficient; simulator tuning value
    GROUND_ROLL_BEFORE_CLIMB_CD_GROUND: float = 0.1

    # Initial climb (below approximately 300 ft)
    PHASE_INITIAL_CLIMB_VREF_KT: float = 60.0  # Target airspeed (HANDBOOK: 57-60 KIAS)
    PHASE_INITIAL_CLIMB_P_BASE_W: float = 50.0e3  # Baseline power (HANDBOOK: 50 kW)
    # Airspeed-error-to-power gain; simulator tuning value
    PHASE_INITIAL_CLIMB_KP_P: float = 4000.0

    # Climb (above approximately 300 ft)
    PHASE_CLIMB_VREF_KT: float = 75.0  # Target airspeed (HANDBOOK: 75 KIAS)
    PHASE_CLIMB_P_BASE_W: float = 49.2e3  # Baseline power (HANDBOOK: MCP = 49.2 kW)
    # Airspeed-error-to-power gain; simulator tuning value
    PHASE_CLIMB_KP_P: float = 4000.0

    # Cruise
    PHASE_CRUISE_VREF_KT: float = 85.0  # Target airspeed [kt]; simulator tuning value
    PHASE_CRUISE_P_BASE_W: float = 20.0e3  # Baseline power (HANDBOOK: 20-36 kW)
    # Airspeed-error-to-power gain; simulator tuning value
    PHASE_CRUISE_KP_P: float = 4000.0

    # Approach
    PHASE_APPROACH_VREF_KT: float = 65.0  # Target airspeed (HANDBOOK: 65 KIAS)
    PHASE_APPROACH_P_BASE_W: float = 0.0e3  # Baseline power (HANDBOOK: cut off)
    # Airspeed-error-to-power gain; simulator tuning value
    PHASE_APPROACH_KP_P: float = 4000.0

    # Final approach
    PHASE_FINAL_VREF_KT: float = 60.0  # Target airspeed (HANDBOOK: 60 KIAS)
    PHASE_FINAL_P_BASE_W: float = 0.0e3  # Baseline power (HANDBOOK: cut off)
    # Airspeed-error-to-power gain; simulator tuning value
    PHASE_FINAL_KP_P: float = 4000.0

    # Ground roll after descent: braking with minimum thrust and increased friction
    PHASE_GROUND_AFTER_DESCENT_VREF_KT: float = 0.0  # Target airspeed
    # Baseline power (HANDBOOK: taxi-level power)
    PHASE_GROUND_AFTER_DESCENT_P_BASE_W: float = 1.0e3
    # Airspeed-error-to-power gain; simulator tuning value
    PHASE_GROUND_AFTER_DESCENT_KP_P: float = 4000.0
    # Ground-friction coefficient; simulator tuning value
    GROUND_ROLL_AFTER_DESCENT_MU_GROUND: float = 0.5
    # Ground-roll aerodynamic drag coefficient; simulator tuning value
    GROUND_ROLL_AFTER_DESCENT_CD_GROUND: float = 0.1

    # Derived phase-classification thresholds
    # Initial-climb altitude-gain threshold
    # (HANDBOOK: safe altitude approximately 300 ft)
    INITIAL_CLIMB_MAX_ALT_GAIN_M: float = 91.0
    # Approach-to-final transition speed (HANDBOOK: 60 KIAS)
    APPROACH_TO_FINAL_V_KT: float = 60.0

    # ============================================================
    # Heading control
    # ============================================================
    MU_MAX_DEG: float = 45.0  # Maximum bank-angle limit [deg]
    TAU_HEADING: float = 1.0  # First-order heading-response time constant [s]

    # ============================================================
    # Altitude / gamma control
    # ============================================================
    GAMMA_KP: float = 0.002  # Altitude-error-to-flight-path-angle proportional gain
    GAMMA_MAX_DEG: float = 7.5  # Maximum climb/descent flight-path angle [deg]
    TAU_GAMMA: float = 1.0  # Flight-path-angle tracking time constant [s]

    # ============================================================
    # Battery model parameters
    # ============================================================
    PARAMS: Dict[str, float] = field(
        default_factory=lambda: {
            "V_nom": 345.6,
            "Q_total_Ah": 58.5636,

            # Electrical baseline
            "R_ohm": 0.100,
            "R1": 0.0175,
            "tau1": 20.0,

            # Thermal baseline
            "R_eff": 0.096,
            "A": 5.447850e-06,
            "B": 1.021907e-03,
            "Bias_T": 1.0442,

            # Cold-temperature correction
            "T_ref": 25.0,
            "cold_trigger_temp": 5.0,
            "cold_full_span": 10.0,

            "kR_ohm_cold": 0.055,
            "kR1_cold": 0.025,
            "kR_eff_cold": 0.060,

            "cool_scale_cold": 0.40,
            "alpha_sink_cold": 0.30,
        }
    )

    # Motor + inverter efficiency (HANDBOOK: Efficiency = 0.89)
    EFF_MOTOR_INV: float = 0.89

    # ============================================================
    # Ambient conditions
    # ============================================================
    USE_REAL_OAT_FROM_CSV: bool = True  # Whether to use OAT from the flight log
    DEFAULT_OAT_C: float = 15.0  # Default outside-air temperature [°C]

    # ============================================================
    # Battery initial conditions
    # ============================================================
    INIT_SOC: float = 0.97  # Initial state of charge
    INIT_TEMP_C: float = 25.0  # Initial battery temperature [°C]

    # ============================================================
    # Propulsion stabilization
    # ============================================================
    # Minimum airspeed used in thrust calculations to avoid division by zero
    V_MIN_FOR_THRUST: float = 8.0
    ETA_CLIP: Tuple[float, float] = (0.05, 0.90)  # Propeller-efficiency clipping range
    # Constant efficiency fallback when surrogate data are unavailable
    ETA_FALLBACK_CONST: float = 0.60

    # ============================================================
    # Derived values
    # ============================================================
    KT2MS: float = 1.0 / 1.943844  # Knots -> m/s
    MS2KT: float = 1.943844  # m/s -> knots

    def __post_init__(self):
        self.V_REF_MS = self.V_REF_KT * self.KT2MS  # Default target airspeed [m/s]
        self.V_MAX_MS = self.V_MAX_KT * self.KT2MS  # Maximum airspeed [m/s]
        self.P_MAX_W = self.P_MCP_W  # Default maximum power limit [W]
