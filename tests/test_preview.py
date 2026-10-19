"""Preview contracts tested with generated, fully artificial CSV content."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from simulator.demo_data import create_synthetic_flight_csv
from simulator.preview import (
    MAX_UPLOAD_BYTES,
    PreviewValidationError,
    build_flight_preview,
)


HEADER = ["time(ms)", "LAT", "LNG", "PRESSURE_ALT"]
ROWS = [
    [1000, 0, 0, 100],
    [1500, 0, 0.0001, 110],
    [2600, 0, 0.0002, 120],
    [3100, 0, 0.0003, 130],
]


def _csv_bytes(rows=None, header=None) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(HEADER if header is None else header)
    writer.writerows(ROWS if rows is None else rows)
    return stream.getvalue().encode("utf-8")


def test_minimal_csv_returns_normalized_time_and_local_coordinates():
    preview = build_flight_preview(_csv_bytes())

    assert preview.sample_count == 4
    assert preview.waypoint_count == 3
    assert preview.duration_s == pytest.approx(2.1)
    assert preview.downsample_sec == 1.0
    assert preview.coordinate_system == "local_enu"
    assert preview.altitude_reference == "first_pressure_altitude"
    assert preview.origin.latitude_deg == 0
    assert preview.origin.longitude_deg == 0
    assert preview.origin.pressure_altitude_m == 100
    assert [wp.time_s for wp in preview.waypoints] == pytest.approx([0, 1.6, 2.1])
    assert [wp.relative_altitude_m for wp in preview.waypoints] == [0, 20, 30]
    assert preview.waypoints[0].east_m == 0
    assert preview.waypoints[0].north_m == 0
    # At the equator, a 0.0003-degree eastward displacement is about 33.4 m.
    assert preview.waypoints[-1].east_m == pytest.approx(33.4, abs=0.01)
    assert preview.waypoints[-1].north_m == pytest.approx(0, abs=1e-9)
    json.dumps(preview.to_dict(), allow_nan=False)


def test_first_and_final_samples_survive_large_downsampling_interval():
    preview = build_flight_preview(_csv_bytes(), downsample_sec=100)

    assert preview.waypoint_count == 2
    assert [wp.time_s for wp in preview.waypoints] == pytest.approx([0, 2.1])
    assert preview.waypoints[-1].relative_altitude_m == 30


def test_subsecond_interval_can_preserve_all_samples():
    preview = build_flight_preview(_csv_bytes(), downsample_sec=0.5)

    assert preview.waypoint_count == 4
    assert [wp.time_s for wp in preview.waypoints] == pytest.approx([0, 0.5, 1.6, 2.1])


def test_existing_synthetic_simulator_csv_also_supports_preview(tmp_path):
    path = Path(create_synthetic_flight_csv(tmp_path / "synthetic.csv"))
    preview = build_flight_preview(path.read_bytes())

    assert preview.sample_count == 121
    assert preview.waypoint_count == 121
    assert preview.duration_s == 120


def test_bom_header_whitespace_and_extra_channels_are_supported():
    header = [f" {name} " for name in HEADER] + ["optional channel"]
    content = b"\xef\xbb\xbf" + _csv_bytes(
        rows=[row + ["not needed for preview"] for row in ROWS], header=header
    )

    assert build_flight_preview(content).sample_count == 4


def test_reordered_columns_are_mapped_by_name():
    preview = build_flight_preview(
        _csv_bytes(
            header=list(reversed(HEADER)),
            rows=[list(reversed(row)) for row in ROWS],
        )
    )

    assert preview.origin.pressure_altitude_m == 100
    assert preview.duration_s == pytest.approx(2.1)


@pytest.mark.parametrize("content", [b"", b" \n\t", b"\xef\xbb\xbf"])
def test_empty_content_is_rejected(content):
    with pytest.raises(PreviewValidationError) as exc:
        build_flight_preview(content)

    assert exc.value.issue.code == "empty_file"


@pytest.mark.parametrize("rows", [[], [ROWS[0]]])
def test_at_least_two_samples_are_required(rows):
    with pytest.raises(PreviewValidationError) as exc:
        build_flight_preview(_csv_bytes(rows=rows))

    assert exc.value.issue.code == "insufficient_samples"


def test_missing_required_column_identifies_header_field():
    with pytest.raises(PreviewValidationError) as exc:
        build_flight_preview(
            _csv_bytes(header=HEADER[:-1], rows=[r[:-1] for r in ROWS])
        )

    assert exc.value.issue.code == "missing_column"
    assert exc.value.issue.column == "PRESSURE_ALT"
    assert exc.value.issue.row == 1


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"\xff\xfe", "invalid_encoding"),
        (b",LAT,LNG,PRESSURE_ALT\n", "invalid_header"),
        (_csv_bytes(header=HEADER + [" LAT "]), "duplicate_column"),
        (b'time(ms),LAT,LNG,PRESSURE_ALT\n"unterminated', "invalid_csv"),
        (_csv_bytes(rows=[ROWS[0][:-1]]), "invalid_row"),
        (_csv_bytes(rows=[ROWS[0] + ["extra"]]), "invalid_row"),
    ],
)
def test_invalid_csv_structure_has_an_actionable_code(content, code):
    with pytest.raises(PreviewValidationError) as exc:
        build_flight_preview(content)

    assert exc.value.issue.code == code


@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("", "invalid_number"),
        ("private-value", "invalid_number"),
        ("NaN", "non_finite_value"),
        ("inf", "non_finite_value"),
    ],
)
def test_required_values_must_be_present_numeric_and_finite(index, value, code):
    rows = [list(row) for row in ROWS]
    rows[1][index] = value
    with pytest.raises(PreviewValidationError) as exc:
        build_flight_preview(_csv_bytes(rows=rows))

    assert exc.value.issue.code == code
    assert exc.value.issue.column == HEADER[index]
    assert exc.value.issue.row == 3
    assert "private-value" not in json.dumps(exc.value.to_dict())


@pytest.mark.parametrize(
    ("index", "value"), [(1, -91), (1, 91), (2, -181), (2, 181)]
)
def test_invalid_latitude_and_longitude_are_rejected(index, value):
    rows = [list(row) for row in ROWS]
    rows[1][index] = value
    with pytest.raises(PreviewValidationError) as exc:
        build_flight_preview(_csv_bytes(rows=rows))

    assert exc.value.issue.code == "out_of_range"
    assert exc.value.issue.column == HEADER[index]
    assert exc.value.issue.row == 3


@pytest.mark.parametrize(
    ("time_ms", "code"),
    [
        (-1, "negative_time"),
        (1000, "non_increasing_time"),
        (500, "non_increasing_time"),
    ],
)
def test_invalid_time_is_reported_without_sorting_the_flight(time_ms, code):
    rows = [list(row) for row in ROWS]
    rows[1][0] = time_ms
    with pytest.raises(PreviewValidationError) as exc:
        build_flight_preview(_csv_bytes(rows=rows))

    assert exc.value.issue.code == code
    assert exc.value.issue.column == "time(ms)"
    assert exc.value.issue.row == 3


@pytest.mark.parametrize(
    "interval", [0, -1, float("nan"), float("inf"), True, "1", 10**400]
)
def test_invalid_downsampling_interval_is_rejected(interval):
    with pytest.raises(PreviewValidationError) as exc:
        build_flight_preview(_csv_bytes(), downsample_sec=interval)

    assert exc.value.issue.code == "invalid_downsample_sec"


def test_upload_size_is_bounded():
    with pytest.raises(PreviewValidationError) as exc:
        build_flight_preview(b"x" * (MAX_UPLOAD_BYTES + 1))

    assert exc.value.issue.code == "file_too_large"


def test_blank_lines_do_not_shift_error_line_numbers():
    content = b"time(ms),LAT,LNG,PRESSURE_ALT\n\n1000,0,0,100\n1500,invalid,0,110\n"
    with pytest.raises(PreviewValidationError) as exc:
        build_flight_preview(content)

    assert exc.value.issue.row == 4


def test_multiline_syntax_error_reports_the_start_of_the_record():
    content = b'time(ms),LAT,LNG,PRESSURE_ALT\n1000,0,0,"unclosed\nfield'
    with pytest.raises(PreviewValidationError) as exc:
        build_flight_preview(content)

    assert exc.value.issue.code == "invalid_csv"
    assert exc.value.issue.row == 2


def test_time_that_collapses_during_unit_conversion_is_rejected():
    with pytest.raises(PreviewValidationError) as exc:
        build_flight_preview(_csv_bytes(rows=[[0, 0, 0, 100], [5e-324, 0, 0, 100]]))

    assert exc.value.issue.code == "invalid_time_resolution"


def test_finite_inputs_that_overflow_coordinate_conversion_are_rejected():
    with pytest.raises(PreviewValidationError) as exc:
        build_flight_preview(
            _csv_bytes(rows=[[0, 0, 0, -1e308], [1000, 0, 0, 1e308]])
        )

    assert exc.value.issue.code == "invalid_coordinates"


def test_error_response_contract_does_not_echo_uploaded_values():
    content = _csv_bytes(rows=[[1000, 0, 0, "private-flight-value"]])
    with pytest.raises(PreviewValidationError) as exc:
        build_flight_preview(content)

    assert exc.value.to_dict() == {
        "error": {
            "code": "invalid_preview_input",
            "message": "The flight preview input is invalid.",
            "issues": [
                {
                    "code": "invalid_number",
                    "message": "A required value must be numeric and present.",
                    "column": "PRESSURE_ALT",
                    "row": 2,
                }
            ],
        }
    }
