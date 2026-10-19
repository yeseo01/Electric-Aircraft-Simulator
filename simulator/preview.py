"""Validate uploaded CSV bytes and build a framework-independent flight preview."""

from __future__ import annotations

import csv
import io
import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .core.io_flight import make_waypoints_from_csv


REQUIRED_COLUMNS = ("time(ms)", "LAT", "LNG", "PRESSURE_ALT")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    column: str | None = None
    row: int | None = None


class PreviewValidationError(ValueError):
    """An actionable error that does not echo uploaded values or file paths."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        column: str | None = None,
        row: int | None = None,
    ) -> None:
        super().__init__(message)
        self.issue = ValidationIssue(code, message, column, row)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": "invalid_preview_input",
                "message": "The flight preview input is invalid.",
                "issues": [asdict(self.issue)],
            }
        }


@dataclass(frozen=True)
class PreviewOrigin:
    latitude_deg: float
    longitude_deg: float
    pressure_altitude_m: float


@dataclass(frozen=True)
class PreviewWaypoint:
    time_s: float
    east_m: float
    north_m: float
    relative_altitude_m: float


@dataclass(frozen=True)
class FlightPreview:
    sample_count: int
    waypoint_count: int
    duration_s: float
    downsample_sec: float
    coordinate_system: str
    altitude_reference: str
    origin: PreviewOrigin
    waypoints: list[PreviewWaypoint]

    def to_dict(self) -> dict[str, Any]:
        """Return built-in types suitable for a JSON response."""
        return asdict(self)


def build_flight_preview(
    csv_content: bytes,
    *,
    downsample_sec: float = 1.0,
) -> FlightPreview:
    """Validate one flight log and preview its waypoints without storing it.

    Required units: time in milliseconds, latitude/longitude in degrees,
    and pressure altitude in meters. Returned time starts at zero.
    Errors identify physical CSV line numbers, with the header at line 1.
    See ``docs/flight-preview-contract.md`` for the complete contract.
    """
    try:
        valid_interval = (
            not isinstance(downsample_sec, bool)
            and isinstance(downsample_sec, (int, float))
            and math.isfinite(downsample_sec)
            and downsample_sec > 0
        )
    except OverflowError:
        valid_interval = False
    if not valid_interval:
        raise PreviewValidationError(
            "invalid_downsample_sec", "downsample_sec must be finite and positive."
        )
    if len(csv_content) > MAX_UPLOAD_BYTES:
        raise PreviewValidationError(
            "file_too_large", "CSV must be at most 10 MiB."
        )
    try:
        text = csv_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise PreviewValidationError(
            "invalid_encoding", "CSV must use UTF-8 encoding (BOM is supported)."
        ) from None
    if not text.strip():
        raise PreviewValidationError("empty_file", "CSV is empty.")

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    samples: list[list[float]] = []
    row_number = 1
    try:
        header = [name.strip() for name in next(reader)]
        if not header or any(not name for name in header):
            raise PreviewValidationError(
                "invalid_header", "Every CSV column must have a name.", row=1
            )
        if len(set(header)) != len(header):
            raise PreviewValidationError(
                "duplicate_column", "CSV column names must be unique.", row=1
            )
        for name in REQUIRED_COLUMNS:
            if name not in header:
                raise PreviewValidationError(
                    "missing_column",
                    "A required column is missing.",
                    column=name,
                    row=1,
                )
        indices = [header.index(name) for name in REQUIRED_COLUMNS]

        while True:
            row_number = reader.line_num + 1
            values = next(reader, None)
            if values is None:
                break
            if not values:
                continue
            if len(values) != len(header):
                raise PreviewValidationError(
                    "invalid_row",
                    "Row must have the same number of fields as the header.",
                    row=row_number,
                )
            sample = []
            for name, index in zip(REQUIRED_COLUMNS, indices):
                try:
                    value = float(values[index])
                except ValueError:
                    raise PreviewValidationError(
                        "invalid_number",
                        "A required value must be numeric and present.",
                        column=name,
                        row=row_number,
                    ) from None
                if not math.isfinite(value):
                    raise PreviewValidationError(
                        "non_finite_value",
                        "A required value must be finite.",
                        column=name,
                        row=row_number,
                    )
                sample.append(value)
            time_ms, lat, lon, _ = sample
            for name, value, lower, upper in (
                ("LAT", lat, -90.0, 90.0),
                ("LNG", lon, -180.0, 180.0),
            ):
                if not lower <= value <= upper:
                    raise PreviewValidationError(
                        "out_of_range",
                        f"Value must be between {lower:g} and {upper:g} degrees.",
                        column=name,
                        row=row_number,
                    )
            if time_ms < 0:
                raise PreviewValidationError(
                    "negative_time",
                    "Time must be non-negative.",
                    column="time(ms)",
                    row=row_number,
                )
            if samples and time_ms <= samples[-1][0]:
                raise PreviewValidationError(
                    "non_increasing_time",
                    "Time must strictly increase; "
                    "duplicate or reversed times are invalid.",
                    column="time(ms)",
                    row=row_number,
                )
            samples.append(sample)
    except csv.Error:
        raise PreviewValidationError(
            "invalid_csv", "CSV syntax could not be read.", row=row_number
        ) from None

    if len(samples) < 2:
        raise PreviewValidationError(
            "insufficient_samples", "CSV must contain at least two data rows."
        )

    data = np.asarray(samples, dtype=float)
    time_s = (data[:, 0] - data[0, 0]) * 1e-3
    if not np.all(np.diff(time_s) > 0):
        raise PreviewValidationError(
            "invalid_time_resolution",
            "Times must remain distinct after conversion to elapsed seconds.",
            column="time(ms)",
        )
    with np.errstate(over="ignore", invalid="ignore"):
        wps, times = make_waypoints_from_csv(
            time_s, data[:, 1], data[:, 2], data[:, 3], float(downsample_sec)
        )
    if not np.all(np.isfinite(wps)):
        raise PreviewValidationError(
            "invalid_coordinates",
            "Input values cannot produce finite waypoint coordinates.",
        )
    return FlightPreview(
        sample_count=len(samples),
        waypoint_count=len(wps),
        duration_s=float(time_s[-1]),
        downsample_sec=float(downsample_sec),
        coordinate_system="local_enu",
        altitude_reference="first_pressure_altitude",
        origin=PreviewOrigin(float(data[0, 1]), float(data[0, 2]), float(data[0, 3])),
        waypoints=[
            PreviewWaypoint(float(t), float(wp[0]), float(wp[1]), float(wp[2]))
            for wp, t in zip(wps, times)
        ],
    )
