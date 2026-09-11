# Electric Aircraft Flight & Battery Simulator

A Python-based simulator for predicting electric-aircraft flight and battery states from a mission profile.

The simulator converts mission-profile data into waypoints, follows them through guidance and control logic, propagates aircraft states using 3-DOF flight dynamics, and integrates propulsion and battery models to estimate both aircraft and battery states throughout the mission.

---

## Project Background

This project originated from my undergraduate research at the Air Transportation System Design Laboratory (ATSDL), Sejong University.

The research goal was to build an integrated simulation framework that could reproduce an electric-aircraft mission and predict how both aircraft motion and battery states evolve throughout the flight.

During the research project, I designed and implemented the core flight-simulation workflow. After the research period, I continued developing the project as a personal software-engineering exercise, exploring how the existing simulation core could support incremental execution, telemetry, testing, and future application-layer integration.

---

## My Contribution

During the undergraduate research project, I designed and implemented the overall flight-simulation workflow.

My work included:

- Reading mission-profile data and converting it into a sequence of waypoints.
- Using each waypoint as a target for guidance and control.
- Computing the aircraft state at each simulation step using 3-DOF point-mass flight dynamics.
- Implementing the time-stepped simulation loop that coordinates waypoint tracking, control, and state propagation.
- Integrating motor, propeller, and battery surrogate models developed by other research team members into the simulator.
- Extending the original flight-state simulation so that battery states could also be predicted throughout the mission.

The motor, propeller, and battery surrogate models themselves were developed by other members of the research team. My role was to integrate these subsystem models into the flight simulator and coordinate their interaction within the overall simulation loop.

---

## Research Implementation vs. Current Repository

The current repository is not an exact snapshot of the original research codebase.

The core simulation architecture—including mission-profile processing, waypoint generation, guidance and control, 3-DOF flight dynamics, and the integration of propulsion and battery models—originates from my undergraduate research implementation.

The primary post-research additions in the current repository are:

| Research Implementation | Post-Research Addition |
| --- | --- |
| Batch-oriented simulation workflow | Incremental `FlightSimulator.step()` interface for step-by-step execution and telemetry generation |
| Research-oriented execution and validation workflow | Regression tests for validating simulator behavior across execution paths |

The backend/frontend scaffolding and other web-oriented project structure were also added after the research project as part of an exploration of software architecture and application development.

These web-oriented post-research additions were developed with the assistance of AI coding tools. They should be considered separate from the original research implementation.

---

## What the Simulator Does

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

---

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

---

## Repository Structure

```text
Electric-Aircraft-Simulator/
│
├── simulator/
│   ├── flight_simulator.py    # Incremental simulation interface
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
├── docs/                      # Architecture and development notes
├── apps/                      # Placeholder structure for future web extensions
├── requirements.txt
└── README.md
```

---

## Technical Highlights

### Integrated Multidomain Simulation

The simulator couples flight dynamics with propulsion and battery models so that aircraft motion and battery behavior evolve together within the same time-stepped simulation.

### Waypoint-Based Mission Simulation

Mission-profile data are converted into waypoints, which are sequentially used as guidance targets throughout the simulated flight.

### Incremental Simulation API

In addition to the batch-oriented simulation workflow used during the research project, the current repository provides an incremental simulation interface:

```python
from simulator import FlightSimulator

simulator = FlightSimulator.from_config()

while not simulator.finished:
    frame = simulator.step()
```

Each call to `step()` advances the simulator by one simulation step and returns a telemetry frame containing the current aircraft and battery states.

### Modular Simulation Components

The simulator separates guidance, control, flight dynamics, atmosphere, propulsion, and battery-related logic into distinct components with explicit responsibilities within the overall simulation workflow.

### Regression Testing

The repository includes regression tests that compare the incremental simulator against the existing batch-simulation workflow to verify consistency between the two execution paths.

The tests use synthetic flight data generated at runtime and do not require the private real-flight datasets used during the research project.

---

## Validation

During the research project, the integrated simulator was validated against real-flight logs.

Battery-state prediction performance included:

| Variable | RMSE |
| --- | ---: |
| Battery Voltage | 3.89 V |
| State of Charge (SOC) | 1.8 percentage points |
| Battery Temperature | 0.44 °C |

These results were used to evaluate how closely the integrated simulation reproduced battery behavior observed during the analyzed real flights.

The original real-flight datasets used for this validation are not included in this public repository.

---

## Quick Start

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

---

## Testing

Run the test suite with:

```bash
python -m pytest
```

The current tests verify:

- consistency between the incremental `FlightSimulator` interface and the existing batch simulation
- correct simulator execution and termination behavior

Synthetic flight data are generated at runtime for testing and are not derived from the private research datasets.

---

## Limitations

This project is a research and software-development prototype rather than a certified flight-performance or aircraft-control system.

Current limitations include:

- simplified 3-DOF point-mass flight dynamics
- model parameters that depend on available aircraft and flight data
- control logic tuned around the analyzed flight profiles
- surrogate-model accuracy limited by the underlying model data
- no certification or safety validation for operational aircraft use

The simulator is intended for research, analysis, and software-development experimentation only.

---

## Post-Research Software Exploration

After the undergraduate research project, I explored how the existing simulation core could be extended toward a software system supporting incremental execution, telemetry, automated testing, and future web-based monitoring.

The current repository therefore includes post-research software-oriented additions intended to support future work such as:

- API-based simulation control
- telemetry delivery
- backend integration
- web-based monitoring
- interactive visualization

The backend/frontend scaffolding and other web-oriented project structure were added after the research project with the assistance of AI coding tools.

These additions are separate from the original research implementation.

---

## Future Work

Possible extensions include:

- FastAPI-based simulation APIs
- WebSocket-based telemetry streaming
- live flight and battery-state visualization
- scenario comparison tools
- route and energy trade-off analysis
- additional automated tests
- additional validation using independent flight datasets

---

## Related Research

This simulator was developed as a follow-up research effort to earlier work on electric-aircraft operational and battery-performance analysis.

**Cho, Y., Lee, J., Kim, Y., Jung, C., Kang, S., & Kim, J.**  
*Understanding the Impact of Operational Variables on Electric Aircraft Battery Performance via Real-Flight Data Analysis.*  
Accepted for presentation at ICAS 2026.
