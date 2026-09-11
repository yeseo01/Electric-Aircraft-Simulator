# Electric Aircraft Simulation Control System

전기비행기의 비행, 에너지, 환경 상태를 시뮬레이션하고 이후 실시간 관제 화면과 추천 경로 시스템으로 확장하기 위한 프로젝트입니다.

## Structure

```text
simulator/      Python simulation core
data/input/     Flight logs and model input files
data/output/    Generated simulation results and plots
scripts/        Demo, plotting, and data generation scripts
apps/backend/   Future FastAPI and WebSocket gateway
apps/frontend/  Future React/Cesium/ECharts UI
docs/           Architecture and product notes
```

## Run

```bash
source .venv/bin/activate
python -m scripts.run_demo
```

## Step API

```python
from simulator import FlightSimulator

simulator = FlightSimulator.from_config()
frame = simulator.step()
```

## Test

```bash
source .venv/bin/activate
python -m pytest
```
