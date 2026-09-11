# Electric Aircraft Flight & Battery Simulator

A Python-based simulator for predicting electric-aircraft flight and battery states from a mission profile.

The simulator converts mission-profile data into waypoints, follows them through guidance and control logic, propagates aircraft states using 3-DOF flight dynamics, and integrates propulsion and battery models to estimate both aircraft and battery states throughout the mission.

---

## Project Background

This project originated from my undergraduate research at the Air Transportation System Design Laboratory (ATSDL), Sejong University.

The research goal was to build an integrated simulation framework that could reproduce an electric-aircraft mission and predict how both aircraft motion and battery states evolve throughout the flight.

During the research project, I designed and implemented the core flight-simulation workflow. After the research period, I continued developing the project as a personal software-engineering exercise, exploring how the simulation core could be reorganized and extended toward a web-based telemetry and monitoring system.

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

The core simulation logic originates from my undergraduate research implementation, while additional software structure was introduced afterward as part of my software-development study.

| Research Implementation | Current Repository |
| --- | --- |
| Mission-profile input | Structured input and configuration modules |
| Waypoint generation | Modular flight-data and waypoint handling |
| Guidance and control | Separated guidance and control modules |
| 3-DOF flight dynamics | Modular flight-dynamics simulation core |
| Integrated propulsion and battery simulation | Explicit powertrain modules and interfaces |
| Batch-oriented simulation workflow | Incremental `FlightSimulator.step()` API |
| Research-oriented scripts | Reusable package structure and tests |

The web-oriented structure, API-related code, backend/frontend scaffolding, and monitoring-system extensions were added after the research project and were not part of the original research implementation.

These post-research extensions were developed with the assistance of AI coding tools as part of my effort to study software architecture and application development.

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
3. Propulsion-system calculation
4. Battery-state update
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
   ┌───────────────────┐
   │  Powertrain Model │
   │                   │
   │  Motor*           │
   │    ↓              │
   │  Propeller*       │
   │    ↓              │
   │  Battery*         │
   └───────────────────┘
        │         │
      Thrust   Battery State
        │         │
        ▼         │
  3-DOF Flight    │
    Dynamics      │
        │         │
        ▼         │
  Aircraft State │
        │         │
        └────┬────┘
             ▼
      Telemetry Frame
             │
             ▼
       Next Time Step
```

\* Motor, propeller, and battery surrogate models were developed by other research team members and integrated into the simulator by me.

The `FlightSimulator` class acts as the orchestration layer that coordinates guidance, control, flight dynamics, propulsion, and battery-state updates.

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
├── scripts/                   # Demo and utility scripts
├── data/                      # Simulation input/output data
├── docs/                      # Architecture and development notes
├── apps/                      # Post-research web-oriented extensions
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

The current repository provides an incremental simulation interface:

```python
from simulator import FlightSimulator

simulator = FlightSimulator.from_config()

while not simulator.finished:
    frame = simulator.step()
```

Each call to `step()` advances the simulator by one simulation step and returns a telemetry frame containing the current aircraft and battery states.

### Modular Subsystems

Guidance, control, flight dynamics, atmosphere, propulsion, and battery-related logic are separated into modules to make the simulation structure easier to inspect, test, and extend.

### Regression Testing

The repository includes tests that compare the incremental simulator against the existing batch-simulation workflow to verify consistency between the two execution paths.

---

## Validation

The integrated simulator was validated against real-flight logs.

Battery-state prediction performance included:

| Variable | RMSE |
| --- | ---: |
| Battery Voltage | 3.89 V |
| State of Charge (SOC) | 1.8 percentage points |
| Battery Temperature | 0.44 °C |

These results were used to evaluate how closely the integrated simulation reproduced battery behavior observed during real flights.

---

## Quick Start

### 1. Create a virtual environment

```bash
python -m venv .venv
```

### 2. Activate the environment

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the demo

```bash
python -m scripts.run_demo
```

---

## Testing

Run the test suite with:

```bash
python -m pytest
```

The current tests verify:

- consistency between the incremental `FlightSimulator` interface and the existing batch simulation
- correct simulator execution and termination behavior

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

## Post-Research Software Extension

After the undergraduate research project, I explored how the simulation core could be extended toward a software system supporting live telemetry and monitoring.

This work includes software structure related to:

- incremental simulation interfaces
- API-oriented integration
- backend architecture
- telemetry delivery
- web-based monitoring
- future visualization tools

These components were developed after the research project with the assistance of AI coding tools and should be considered separate from the original research implementation.

---

## Future Work

Possible extensions include:

- FastAPI-based simulation APIs
- WebSocket-based telemetry streaming
- live flight and battery-state visualization
- scenario comparison tools
- route and energy trade-off analysis
- additional validation using independent flight datasets

---

## Related Research

This simulator was developed as a follow-up research effort to earlier work on electric-aircraft operational and battery-performance analysis.

**Cho, Y., Lee, J., Kim, Y., Jung, C., Kang, S., & Kim, J.**  
*Understanding the Impact of Operational Variables on Electric Aircraft Battery Performance via Real-Flight Data Analysis.*  
Accepted for presentation at ICAS 2026.
