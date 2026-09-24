# Electric Aircraft Flight & Battery Simulator

A Python-based simulator for predicting electric-aircraft flight and battery states from a mission profile.

The simulator converts mission-profile data into waypoints, follows them through guidance and control logic, propagates aircraft states using 3-DOF flight dynamics, and integrates propulsion and battery models to estimate both aircraft and battery states throughout the mission.


## Key Highlights

- Integrated flight dynamics, guidance/control, propulsion, and battery-state prediction in a single time-stepped simulation.
- Integrated motor, propeller, and battery surrogate models developed by other research team members into the flight-simulation workflow.
- Extended the original batch-oriented research simulator with an incremental `FlightSimulator.step()` interface and structured telemetry output.
- Added regression tests that compare incremental execution against the original batch-simulation workflow.


## Research Validation Snapshot

Research validation using private real-flight logs produced the following battery-state prediction errors:

| Variable | RMSE |
| --- | ---: |
| Battery Voltage | 3.89 V |
| State of Charge (SOC) | 1.8 percentage points |
| Battery Temperature | 0.44 °C |

These results were obtained during the undergraduate research project using real-flight datasets that are not included in this public repository. The public demo and automated tests use synthetic flight data instead.


## Project Background & My Role

This project originated from my undergraduate research at the Air Transportation System Design Laboratory (ATSDL), Sejong University.

The research goal was to build an integrated simulation framework that could reproduce an electric-aircraft mission and predict how both aircraft motion and battery states evolve throughout the flight.

I designed and implemented the core flight-simulation workflow. My work included:

- reading mission-profile data and converting it into a sequence of waypoints
- using waypoints to generate heading and altitude guidance targets
- computing aircraft states using 3-DOF point-mass flight dynamics
- implementing the time-stepped simulation loop that coordinates waypoint tracking, control, and state propagation
- integrating motor, propeller, and battery surrogate models developed by other research team members
- extending the flight-state simulation so that battery states could be predicted throughout the mission

The motor, propeller, and battery surrogate models themselves were developed by other members of the research team. My role was to integrate these subsystem models into the flight simulator and coordinate their interaction within the overall simulation loop.

After the research project, I continued developing the simulator as a software-engineering exercise by adding an incremental execution interface, structured telemetry, synthetic public demo data, and regression tests.


## Research Implementation vs. Current Repository

The current repository is not an exact snapshot of the original research codebase.

The core simulation architecture—including mission-profile processing, waypoint generation, guidance and control, 3-DOF flight dynamics, and the integration of propulsion and battery models—originates from my undergraduate research implementation.

The primary post-research additions in the current repository are:

| Research Implementation | Post-Research Addition |
| --- | --- |
| Batch-oriented simulation workflow | Incremental `FlightSimulator.step()` interface for step-by-step execution and telemetry generation |
| Research-oriented execution and validation workflow | Regression tests for validating simulator behavior across execution paths |


## Simulation Workflow

### Input

The simulator uses mission and flight data to define information such as:

- mission trajectory
- waypoints
- altitude profile
- flight phases
- environmental conditions
- initial aircraft state
- initial battery state

### Simulation

At each simulation step, the system coordinates:

1. Waypoint guidance
2. Flight control
3. Power-command generation
4. Battery and propulsion-system calculation
5. 3-DOF aircraft-state propagation
6. Telemetry generation

### Output

The simulator produces time histories of states including:

- position
- altitude
- airspeed
- heading
- flight-path angle
- battery state of charge (SOC)
- battery voltage
- battery current
- battery temperature
- propeller RPM
- thrust
- flight phase


## System Architecture

```text
Mission Profile / Flight Data
            │
            ▼
     Waypoint Generation
            │
            ▼
         Guidance
            │
            ▼
          Control
            │
            ▼
       Power Command
            │
            ▼
   ┌─────────────────────┐
   │   Powertrain Model  │
   │                     │
   │   Battery*          │
   │   Motor / Inverter* │
   │   Propeller*        │
   │   RPM Solver        │
   └──────────┬──────────┘
              │
            Thrust
              │
              ▼
       3-DOF Flight
         Dynamics
              │
              ▼
        Aircraft State

Battery State ─────────────┐
Aircraft State ────────────┤
                           ▼
                    Telemetry Frame
                           │
                           ▼
                    Next Time Step
```

\* The motor, propeller, and battery models were developed by other research team members and integrated into the overall simulator by me.

The `FlightSimulator` class acts as the orchestration layer that coordinates guidance, control, flight dynamics, propulsion, battery-state updates, and telemetry generation.


## Incremental Simulation Interface

The original research workflow was batch-oriented. The current repository additionally provides an incremental simulation interface for step-by-step execution:

```python
from simulator import FlightSimulator

simulator = FlightSimulator.from_config()

while not simulator.finished:
    frame = simulator.step()
```

Each call to `step()` advances the simulator by one simulation step and returns structured telemetry containing the current aircraft and battery states.

Regression tests compare incremental execution against the existing batch-simulation workflow to verify consistency between the two execution paths.


## Repository Structure

```text
Electric-Aircraft-Simulator/
│
├── simulator/
│   ├── flight_simulator.py    # Incremental simulation interface
│   ├── demo_data.py           # Synthetic data generation for demo and tests
│   ├── config.py              # Simulation configuration
│   ├── schemas.py             # State and telemetry data structures
│   │
│   ├── core/
│   │   ├── aero.py
│   │   ├── atmosphere.py
│   │   ├── control.py
│   │   ├── frames.py
│   │   ├── guidance.py
│   │   ├── io_flight.py
│   │   ├── sim_loop.py
│   │   └── utils.py
│   │
│   └── powertrain/
│       ├── battery.py
│       ├── motor.py
│       ├── prop.py
│       ├── rpm_solve.py
│       └── system.py
│
├── tests/                     # Simulator regression tests
├── scripts/                   # Demo and simulation utilities
├── data/                      # Simulation inputs and generated outputs
├── requirements.txt
└── README.md
```


## Reproducibility and Data Availability

The battery-state RMSE values summarized above were obtained during the undergraduate research project using private real-flight logs.

Those research datasets are not included in this public repository, so the reported real-flight validation metrics cannot be reproduced directly from the public demo.

The public repository instead provides synthetic flight data for demonstrating the end-to-end simulation workflow and for automated regression testing.


## Quick Start

### Tested Environment

- Python 3.13.3

### 1. Clone the repository

```bash
git clone https://github.com/yeseo01/Electric-Aircraft-Simulator.git
cd Electric-Aircraft-Simulator
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
```

### 3. Activate the environment

macOS / Linux:

```bash
source .venv/bin/activate
```

Windows:

```bash
.venv\Scripts\activate
```

### 4. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 5. Run the demo

```bash
python -m scripts.run_demo
```

The demo automatically generates synthetic flight data and does not require the private research flight logs.


## Testing

Run the test suite with:

```bash
python -m pytest
```

The current tests verify:

- consistency between the incremental `FlightSimulator` interface and the existing batch-simulation workflow
- correct execution, termination, and finished-state behavior
- phase-control consistency when logged IAS data are unavailable
- reproducible simulator state after `reset()`

Synthetic flight data are generated at runtime for testing and are not derived from the private research datasets.


## Limitations

This project is a research and software-development prototype rather than a certified flight-performance or aircraft-control system.

Current limitations include:

- simplified 3-DOF point-mass flight dynamics
- model parameters that depend on available aircraft and flight data
- control logic tuned around the analyzed flight profiles
- surrogate-model accuracy limited by the underlying model data
- no certification or safety validation for operational aircraft use

The simulator is intended for research, analysis, and software-development experimentation only.


## Future Work

Possible extensions include:

- FastAPI-based simulation APIs
- WebSocket-based telemetry streaming
- live flight and battery-state visualization
- scenario comparison tools
- route and energy trade-off analysis
- additional automated tests
- additional validation using independent flight datasets


## Related Research

This simulator was developed as a follow-up research effort to earlier work on electric-aircraft operational and battery-performance analysis.

**Cho, Y., Lee, J., Kim, Y., Jung, C., Kang, S., & Kim, J.**
*Understanding the Impact of Operational Variables on Electric Aircraft Battery Performance via Real-Flight Data Analysis.*
Accepted for presentation at ICAS 2026.
