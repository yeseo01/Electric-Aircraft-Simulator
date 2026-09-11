# config.py
# 시뮬레이션 결과를 저장하려면 SAVE_SIM_RESULT_CSV 값을 True로 변경하고 
# SIM_RESULT_CSV_PATH 값을 원하는 경로, 원하는 파일명을 설정해야함.
from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class SimConfig:
    # ============================================================
    # File paths
    # ============================================================
    FLIGHT_CSV_PATH: str = "./data/input/flight_logs/flight_log.csv"   # 비행 로그 CSV 경로
    PROP_NPZ_PATH: str = "./data/input/prop_surrogate_cp_eta_simready.npz"      # 프로펠러 surrogate 결과 파일 경로
    SAVE_SIM_RESULT_CSV: bool = True                       # 시뮬레이션 결과 CSV 저장 여부
    SIM_RESULT_CSV_PATH: str = "./data/output/simulation_results/simulation_result.csv"     # 시뮬레이션 결과 CSV 저장 경로

    # ============================================================
    # Simulation time settings
    # ============================================================
    DT_SIM: float = 1.0         # 적분 timestep [s]
    DOWNSAMPLE_SEC: float = 1.0  # 로그 → waypoint 다운샘플 간격 [s]
    V0: float = 1.0               # 초기 속도 [m/s]
    TMAX_SCALE: float = 1.0    # 시뮬 종료 시간 배율 (마지막 waypoint 시간 × 배율)
    PATH_PROGRESS_SPEED_RECOVERY_ENABLE: bool = True   # 원본 2D 경로 진행률 기준 속도 보정 사용
    PATH_PROGRESS_SPEED_RECOVERY_GAIN: float = 0.01    # 진행거리 오차[m] → 목표속도 보정[m/s] 게인
    PATH_PROGRESS_SPEED_RECOVERY_MAX_DELTA_KT: float = 3.0  # 기본 속도 대비 최대 보정폭 [kt]

    # ============================================================
    # (디버깅용-삭제절대금지) 로그 출력 시간 범위
    # ============================================================
    WP_DIST_LOG_T_START_FRAC: float = 0.0   # 전체 시뮬 시간(=1)에서 이 비율 이후부터 로그 출력
    WP_DIST_LOG_T_END_FRAC: float = 1.0    # 전체 시뮬 시간(=1)에서 이 비율까지 로그 출력

    # ============================================================
    # Aerodynamics (simple drag polar)
    # ============================================================
    CD0: float = 0.025            # 기생 항력 계수 (parasite drag)
    K: float = 0.035              # 유도 항력 계수 (induced drag factor)
    CL_MIN: float = -0.2          # 최소 양력계수 (하강 한계)
    CL_MAX: float = 1.6           # 최대 양력계수 (실속 근처 한계)
    FLIGHT_DRAG_SCALE_APPROACH: float = 1.0   # 접근 구간 비행 항력 배율 // 1.45(10966), 1.0(10777), 1.0(10578)
    FLIGHT_DRAG_SCALE_FINAL: float = 1.0    # 최종 접근 구간 비행 항력 배율 // 1.45(10966), 1.0(10777), 1.0(10578) 

    # ============================================================
    # Aircraft
    # ============================================================
    MASS_KG: float = 510.0        # 기체 질량 [kg] (HANDBOOK: 510 kg)
    S_WING: float = 9.51          # 날개 면적 [m^2] (HANDBOOK: 9.51 m^2)

    # ============================================================
    # 속도 제한
    # ============================================================
    V_MIN_MS: float = 0.0        # 최소 속도 제한 [m/s]
    V_MAX_KT: float = 108.0       # 최대 속도 제한 [knots] (HANDBOOK: V_NE = 108 knots)

    # ============================================================
    # 프로펠러 제한
    # ============================================================
    RPM_SAFE: float = 2500.0      # 최대 rpm 제한 (HANDBOOK: Max rpm = 2500 rpm)
    RPM_CONT: float = 2300.0      # 연속 운전 rpm 제한 (HANDBOOK: Max continuous rpm = 2300 rpm) // plot.py에서 기준선 표시용, 제어 제한으로는 미사용
    RPM_SOLVE_MIN: float = 300.0  # 최소 rpm // 데이터로 역산한 값
    P_MCP_W: float = 49.2e3       # 최대 연속 출력 [W] (HANDBOOK: MCP = 49.2 kW)
    P_MTOP_W: float = 57.6e3      # 최대 이륙 출력 [W] (HANDBOOK: MTOP = 57.6 kW(90초제한))
    MTOP_MAX_DURATION_S: float = 90.0  # MTOP 허용 누적 시간 [s] (HANDBOOK: 90초)
    MTOP_ALLOWED_PHASES: Tuple[str, ...] = ("ground_roll", "initial_climb")  # MTOP 허용 phase

    # ============================================================
    # 기본값 설정 (목표속도, 게인, 기본 파워)
    # ============================================================
    V_REF_KT: float = 70.0        # 목표 속도 [knots]
    P_BASE_W: float = 35.0e3      # 기준 크루즈 파워 [W], 전체 파워 명령 체인의 공통 기본치 
    P_MIN_W: float = 1.0e3        # 최소 파워 제한 [W], 전체 파워 명령 체인의 공통 최소치
    KP_P: float = 4000.0          # 속도 오차 → 파워 변환 게인 // 시뮬레이터 튜닝값
    TAU_P: float = 2.0            # 파워 명령 LPF 시간상수 [s], 파워 응답 속도 조절용

    # ============================================================
    # 구간별 설정 (목표속도, 게인, 기본 파워)
    # ============================================================
    # 상승 전 지상 구간
    PHASE_GROUND_BEFORE_CLIMB_VREF_KT: float = 50.0      # 목표 속도 (HANDBOOK: 50 KIAS) 
    PHASE_GROUND_BEFORE_CLIMB_P_BASE_W: float = 50.0e3    # 기본 파워 // 시뮬레이터 튜닝값
    PHASE_GROUND_BEFORE_CLIMB_KP_P: float = 4000.0       # 속도 오차 → 파워 변환 게인 // 시뮬레이터 튜닝값 (일단 지금은 기본값과 동일)
    GROUND_ROLL_BEFORE_CLIMB_MU_GROUND: float = 0.5     # 지상 마찰 계수 // 보통 0.6~0.8로 설정 -> 시뮬레이터 튜닝값
    GROUND_ROLL_BEFORE_CLIMB_CD_GROUND: float = 0.1   # 지상 공기저항 계수 // 시뮬레이터 튜닝값

    # 초기 상승 구간 (300ft 이전)
    PHASE_INITIAL_CLIMB_VREF_KT: float = 60.0  # 목표 속도 (HANDBOOK: 초기 상승 57~60 KIAS)
    PHASE_INITIAL_CLIMB_P_BASE_W: float = 50.0e3  # 기본 파워 (HANDBOOK: 50 kW)
    PHASE_INITIAL_CLIMB_KP_P: float = 4000.0    # 속도 오차 → 파워 변환 게인 // 시뮬레이터 튜닝값 (일단 지금은 기본값과 동일)

    # 상승 구간 (300ft 이상)
    PHASE_CLIMB_VREF_KT: float = 75.0       # 목표 속도 (HANDBOOK: 75 KIAS) 
    PHASE_CLIMB_P_BASE_W: float = 49.2e3    # 기본 파워 (HANDBOOK: MCP 49.2 kW) 
    PHASE_CLIMB_KP_P: float = 4000.0        # 속도 오차 → 파워 변환 게인 // 시뮬레이터 튜닝값 (일단 지금은 기본값과 동일)

    # 크루즈 구간
    PHASE_CRUISE_VREF_KT: float = 85.0       # 목표 속도 (HANDBOOK: 없음) // 70(10777), 85(10578), 90(10966)
    PHASE_CRUISE_P_BASE_W: float = 20.0e3    # 기본 파워 (HANDBOOK: 20~36 kW) 
    PHASE_CRUISE_KP_P: float = 4000.0        # 속도 오차 → 파워 변환 게인 // 시뮬레이터 튜닝값

    # 접근 구간
    PHASE_APPROACH_VREF_KT: float = 65.0      # 목표 속도 (HANDBOOK: 65 KIAS)
    PHASE_APPROACH_P_BASE_W: float = 0.0e3    # 기본 파워 (HANDBOOK: cut off) //1.0e3
    PHASE_APPROACH_KP_P: float = 4000.0        # 속도 오차 → 파워 변환 게인 // 시뮬레이터 튜닝값 (일단 지금은 기본값과 동일)

    # 최종 구간
    PHASE_FINAL_VREF_KT: float = 60.0         # 목표 속도 (HANDBOOK: 60 KIAS) 
    PHASE_FINAL_P_BASE_W: float = 0.0e3    # 기본 파워 (HANDBOOK: cut off) //1.0e3
    PHASE_FINAL_KP_P: float = 4000.0        # 속도 오차 → 파워 변환 게인 // 시뮬레이터 튜닝값 (일단 지금은 기본값과 동일)

    # 하강 후 지상 구간: 제동 — 목표속도 0, 추력 최소화, 마찰 강화
    PHASE_GROUND_AFTER_DESCENT_VREF_KT: float = 0.0     # 목표 속도 (HANDBOOK: 없음) 
    PHASE_GROUND_AFTER_DESCENT_P_BASE_W: float = 1.0e3   # 기본 파워 (HANDBOOK: taxi수준) 
    PHASE_GROUND_AFTER_DESCENT_KP_P: float = 4000.0      # 속도 오차 → 파워 변환 게인 // 시뮬레이터 튜닝값(일단 지금은 기본값과 동일)
    GROUND_ROLL_AFTER_DESCENT_MU_GROUND: float = 0.5       # 지상 마찰 계수 // 보통 0.6~0.8로 설정 -> 시뮬레이터 튜닝값
    GROUND_ROLL_AFTER_DESCENT_CD_GROUND: float = 0.1     # 지상 공기저항 계수 // 시뮬레이터 튜닝값

    # 파생 phase 판별 임계값
    INITIAL_CLIMB_MAX_ALT_GAIN_M: float = 91.0      # 초기 이륙구간 구분 임계 고도 (HANDBOOK: safe altitude 약 300 ft)
    APPROACH_TO_FINAL_V_KT: float = 60.0            # 하강 구간 중 final 전환 기준 속도 (HANDBOOK: 60 KIAS)

    # ============================================================
    # Heading control
    # ============================================================
    MU_MAX_DEG: float = 45.0      # 최대 bank angle 제한 [deg]
    TAU_HEADING: float = 1.0      # heading 1차 응답 시간상수 [s]

    # ============================================================
    # Altitude / gamma control
    # ============================================================
    GAMMA_KP: float = 0.002       # 고도 오차 → gamma_cmd 비례 게인 // 0.004
    GAMMA_MAX_DEG: float = 7.5    # 최대 상승/강하 경로각 제한 [deg] // 7.5
    TAU_GAMMA: float = 1.0        # gamma 추종 1차 시간상수 [s] // 1.0

    # ============================================================
    # 베터리 모델 파라미터
    # ============================================================
    PARAMS: Dict[str, float] = field(default_factory=lambda: {
        "V_nom": 345.6,
        "Q_total_Ah": 58.5636,

        # electrical baseline
        "R_ohm": 0.100,
        "R1": 0.0175,
        "tau1": 20.0,

        # thermal baseline
        "R_eff": 0.096,
        "A": 5.447850e-06,
        "B": 1.021907e-03,
        "Bias_T": 1.0442,

        # cold correction
        "T_ref": 25.0,
        "cold_trigger_temp": 5.0,
        "cold_full_span": 10.0,

        "kR_ohm_cold": 0.055,
        "kR1_cold": 0.025,
        "kR_eff_cold": 0.060,

        "cool_scale_cold": 0.40,
        "alpha_sink_cold": 0.30,
    })

    EFF_MOTOR_INV: float = 0.89          # 모터+인버터 효율 (HANDBOOK: Efficiency = 0.89)

    # ============================================================
    # Ambient
    # ============================================================
    USE_REAL_OAT_FROM_CSV: bool = True   # 로그 OAT 사용 여부
    DEFAULT_OAT_C: float = 15.0          # 기본 외기온도 [°C]

    # ============================================================
    # 베터리 초기값
    # ============================================================
    INIT_SOC: float = 0.97    #0.99(10966) / 0.99(10777) / 0.97(10578)      # 초기 SOC
    INIT_TEMP_C: float = 25.0 #29.0(10966) / 30(10777) / 25(10578)     # 초기 배터리 온도 [°C]

    # ============================================================
    # Propulsion stabilization
    # ============================================================
    V_MIN_FOR_THRUST: float = 8.0        # 추력 계산 시 최소 속도 (0 division 방지)
    ETA_CLIP: Tuple[float, float] = (0.05, 0.90)  # 프로펠러 효율 클립 범위
    ETA_FALLBACK_CONST: float = 0.60     # eta 데이터 없을 때 상수 가정값

    # ============================================================
    # Derived values (자동 계산)
    # ============================================================
    KT2MS: float = 1.0 / 1.943844  # knots -> m/s
    MS2KT: float = 1.943844        # m/s -> knots


    def __post_init__(self):
        self.V_REF_MS = self.V_REF_KT * self.KT2MS   # 목표 속도 [m/s]
        self.V_MAX_MS = self.V_MAX_KT * self.KT2MS   # 최대 속도 [m/s]
        self.P_MAX_W = self.P_MCP_W                  # 기본 최대 파워 제한 [W]
