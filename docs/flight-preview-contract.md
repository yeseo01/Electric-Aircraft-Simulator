# Flight preview contract

Related issue: [#1 — CSV upload and waypoint preview](https://github.com/yeseo01/Electric-Aircraft-Simulator/issues/1).

Status: the CSV validation and preview service are implemented in
`simulator.preview`. The HTTP endpoint and React screen described below are
the next implementation steps; this document defines their shared contract.

## User flow

Select or drop a CSV → validate → preview the route and altitude profile.
The preview does not execute the flight simulator. The same existing waypoint
and coordinate conversion functions are used by the simulation engine.

## CSV input

Accept comma-delimited UTF-8, optionally with a UTF-8 BOM. The first line is
the header. Header names are case-sensitive; surrounding whitespace is removed.
Duplicate or unnamed columns are rejected. Reordered columns and extra named
columns are supported. Blank physical lines after the header are skipped.

| Required column | Unit | Validation |
| --- | --- | --- |
| `time(ms)` | milliseconds | Finite, non-negative, strictly increasing |
| `LAT` | degrees | Finite, from -90 to 90 inclusive |
| `LNG` | degrees | Finite, from -180 to 180 inclusive |
| `PRESSURE_ALT` | meters | Finite; negative values are supported |

Require at least two valid data rows. Every nonblank record must have the same
number of fields as the header. Required cells must contain finite numbers.
Missing cells, nonnumeric values, NaN, infinity, duplicate times, and reversed
times produce errors. Do not silently sort, drop, or interpolate invalid rows.
Report the first validation error, including its column and physical line number
where available. The header is line 1; for a multiline CSV record, use the line
where that record starts.

The preview only requires these four channels. Battery, RPM, power, IAS, OAT,
and phase columns can be present and are ignored at this stage. A successful
preview does not imply that the file contains all inputs needed for simulation
or real-flight comparison. Existing `load_flight_csv()` behavior is unchanged.

The maximum file size is 10 MiB (10,485,760 bytes). Process uploaded content
in memory. Do not retain uploaded files, echo cell values in errors, or log the
CSV body or coordinate response. Public examples and tests use synthetic data.

## Preview semantics

- `downsample_sec` is a finite positive number, default `1.0` seconds.
- Convert time to elapsed seconds from the first sample.
- Keep the first sample, select each subsequent sample at least
  `downsample_sec` after the previous selected sample, and always keep the last.
  This selects existing samples; it does not generate a uniform interpolated grid.
- The first sample is the local coordinate origin. East and north are meters
  returned by the existing LLA → ECEF → ENU conversion.
- `relative_altitude_m` is `PRESSURE_ALT - first PRESSURE_ALT`, in meters;
  it is not the ENU Up coordinate or height above terrain.
- Preserve the first pressure altitude separately in `origin`. Absolute logged
  pressure altitude can be reconstructed as origin plus relative altitude.
- `duration_s` describes the entire uploaded flight, regardless of downsampling.

The current engine passes pressure altitude to its geodetic conversion.
This preview preserves that approximation. Pressure altitude is not WGS84
ellipsoidal altitude, GPS altitude, or terrain elevation; the response must not
label it as one of those quantities. The altitude graph should be labeled
"Relative pressure altitude (m)".

## Planned HTTP endpoint

`POST /api/flight-previews`, request body `multipart/form-data`:

| Field | Type | Requirement |
| --- | --- | --- |
| `file` | uploaded CSV | Required, at most 10 MiB |
| `downsample_sec` | number | Optional, finite and positive, default 1.0 |

Client filename and MIME type are not evidence that content is valid CSV. The
server validates the contents. Do not use a client filename as a storage path.
The HTTP layer must enforce the size limit while reading the upload, then invoke
the service. It maps validation errors to the envelope below, including request
parsing errors, rather than returning framework-dependent error shapes.

Development request, once the endpoint is implemented:

```bash
curl -X POST http://127.0.0.1:8000/api/flight-previews \
  -F 'file=@data/input/demo/synthetic_flight.csv' \
  -F 'downsample_sec=1.0'
```

### Success: HTTP 200

This response is an artificial, stationary two-sample example.

```json
{
  "sample_count": 2,
  "waypoint_count": 2,
  "duration_s": 1.0,
  "downsample_sec": 1.0,
  "coordinate_system": "local_enu",
  "altitude_reference": "first_pressure_altitude",
  "origin": {
    "latitude_deg": 0.0,
    "longitude_deg": 0.0,
    "pressure_altitude_m": 100.0
  },
  "waypoints": [
    {"time_s": 0.0, "east_m": 0.0, "north_m": 0.0, "relative_altitude_m": 0.0},
    {"time_s": 1.0, "east_m": 0.0, "north_m": 0.0, "relative_altitude_m": 0.0}
  ]
}
```

Only JSON-compatible finite numbers are returned; no NaN/Infinity values.
The first and final times are zero and `duration_s`. The number of entries in
`waypoints` equals `waypoint_count`.

### Validation error: HTTP 422 (size limit: HTTP 413)

```json
{
  "error": {
    "code": "invalid_preview_input",
    "message": "The flight preview input is invalid.",
    "issues": [
      {
        "code": "invalid_number",
        "message": "A required value must be numeric and present.",
        "column": "PRESSURE_ALT",
        "row": 2
      }
    ]
  }
}
```

`column` and `row` are nullable. Error codes are stable values; the React screen
should use them to choose messages instead of matching the English text.

| Issue code | Meaning |
| --- | --- |
| `empty_file` | Empty or whitespace-only file |
| `invalid_encoding` | Not UTF-8 |
| `file_too_large` | File exceeds 10 MiB |
| `invalid_header` | Missing/empty column name |
| `duplicate_column` | Column names repeat after trimming |
| `missing_column` | Required column is absent |
| `invalid_csv` | CSV syntax cannot be parsed |
| `invalid_row` | Record field count differs from header |
| `invalid_number` | Required cell is empty or nonnumeric |
| `non_finite_value` | Required cell contains NaN or infinity |
| `out_of_range` | Latitude or longitude outside valid bounds |
| `negative_time` | Time is negative |
| `non_increasing_time` | Duplicate or reversed time |
| `invalid_time_resolution` | Time values collapse after conversion to elapsed seconds |
| `insufficient_samples` | Fewer than two data rows |
| `invalid_downsample_sec` | Invalid downsampling interval |
| `invalid_coordinates` | Coordinate conversion produces non-finite output |

The HTTP implementation will also add request-level codes for missing fields
or invalid multipart bodies using this envelope. Internal errors should receive
a generic response without exposing input data or local filesystem paths.

## Python service available now

```python
from pathlib import Path
from simulator.preview import build_flight_preview, PreviewValidationError

try:
    preview = build_flight_preview(
        Path("data/input/demo/synthetic_flight.csv").read_bytes(),
        downsample_sec=1.0,
    )
    response = preview.to_dict()
except PreviewValidationError as error:
    response = error.to_dict()
```

Run `python -m scripts.run_demo` to generate that synthetic input first.
For future uploads, pass the file bytes to the same service.

## Implementation sequence

1. CSV/preview contract and service with synthetic unit tests (this change).
2. FastAPI multipart endpoint and API tests for success, validation, and limits.
3. React drag/drop, file selection, ECharts route/altitude, and error/retry states.
4. Browser flow checks and run instructions; review against issue #1.

These steps make up issue #1 together. It stays open until the complete browser
flow works. Subsequent issues can add simulation execution and live comparison.
