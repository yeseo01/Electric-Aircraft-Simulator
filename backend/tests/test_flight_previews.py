"""HTTP behavior tested with synthetic CSV uploads, never research logs."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartParser

from backend.body_limit import MAX_REQUEST_BYTES, PreviewBodyLimitMiddleware
from backend.main import app
from simulator.preview import MAX_UPLOAD_BYTES


CSV = (
    b"time(ms),LAT,LNG,PRESSURE_ALT\n"
    b"1000,0,0,100\n2000,0,0,110\n3000,0,0,120\n"
)
ENDPOINT = "/api/flight-previews"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_upload_returns_preview_json_and_default_interval(client):
    response = client.post(ENDPOINT, files={"file": ("synthetic.csv", CSV, "text/csv")})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert data["sample_count"] == 3
    assert data["waypoint_count"] == 3
    assert data["duration_s"] == 2
    assert data["downsample_sec"] == 1
    assert data["coordinate_system"] == "local_enu"
    assert data["origin"]["pressure_altitude_m"] == 100
    assert [wp["time_s"] for wp in data["waypoints"]] == [0, 1, 2]
    assert [wp["relative_altitude_m"] for wp in data["waypoints"]] == [0, 10, 20]


def test_form_interval_controls_waypoint_selection(client):
    response = client.post(
        ENDPOINT, files={"file": ("synthetic.csv", CSV)}, data={"downsample_sec": "10"}
    )

    assert response.status_code == 200
    assert response.json()["waypoint_count"] == 2
    assert response.json()["downsample_sec"] == 10


def test_missing_file_uses_the_contract_error_envelope(client):
    response = client.post(ENDPOINT, data={"downsample_sec": "1"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_preview_input"
    assert response.json()["error"]["issues"][0]["code"] == "missing_file"
    assert "detail" not in response.json()


def test_text_instead_of_file_is_rejected_without_echoing_input(client):
    response = client.post(ENDPOINT, data={"file": "private-file-content"})

    assert response.status_code == 422
    assert response.json()["error"]["issues"][0]["code"] == "invalid_file"
    assert "private-file-content" not in response.text


@pytest.mark.parametrize("interval", ["0", "-1", "NaN", "inf", "-inf", "private-input"])
def test_invalid_interval_has_a_safe_error_response(client, interval):
    response = client.post(
        ENDPOINT,
        files={"file": ("synthetic.csv", CSV)},
        data={"downsample_sec": interval},
    )

    assert response.status_code == 422
    assert response.json()["error"]["issues"][0]["code"] == "invalid_downsample_sec"
    assert "private-input" not in response.text


@pytest.mark.parametrize(
    ("content", "code", "column", "row"),
    [
        (b"", "empty_file", None, None),
        (b"\xff", "invalid_encoding", None, None),
        (b"time(ms),LAT,LNG\n", "missing_column", "PRESSURE_ALT", 1),
        (
            b"time(ms),LAT,LNG,PRESSURE_ALT\n0,0,0,100\n1000,private,0,100\n",
            "invalid_number",
            "LAT",
            3,
        ),
        (
            b"time(ms),LAT,LNG,PRESSURE_ALT\n0,0,0,100\n0,0,0,100\n",
            "non_increasing_time",
            "time(ms)",
            3,
        ),
    ],
)
def test_csv_validation_errors_preserve_code_and_location(
    client, content, code, column, row
):
    response = client.post(ENDPOINT, files={"file": ("private-name.csv", content)})

    assert response.status_code == 422
    issue = response.json()["error"]["issues"][0]
    assert (issue["code"], issue["column"], issue["row"]) == (code, column, row)
    assert "private" not in response.text


def test_file_one_byte_over_limit_is_413(client):
    response = client.post(
        ENDPOINT, files={"file": ("synthetic.csv", b"x" * (MAX_UPLOAD_BYTES + 1))}
    )

    assert response.status_code == 413
    assert response.json()["error"]["issues"][0]["code"] == "file_too_large"


def test_request_above_multipart_budget_is_413(client):
    response = client.post(
        ENDPOINT,
        content=b"x" * (MAX_REQUEST_BYTES + 1),
        headers={"Content-Type": "multipart/form-data; boundary=test"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["issues"][0]["code"] == "request_too_large"


def test_missing_multipart_boundary_is_a_safe_validation_error(client):
    response = client.post(
        ENDPOINT,
        content=b"private-content",
        headers={"Content-Type": "multipart/form-data"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["issues"][0]["code"] == "invalid_multipart"
    assert "private-content" not in response.text


def test_broken_multipart_syntax_is_a_safe_validation_error(client):
    response = client.post(
        ENDPOINT,
        content=b"not-a-multipart-body",
        headers={"Content-Type": "multipart/form-data; boundary=test"},
    )

    assert response.status_code == 422
    assert "error" in response.json()


def test_filename_and_mime_type_do_not_replace_content_validation(client):
    response = client.post(
        ENDPOINT, files={"file": ("../../private.bin", CSV, "application/octet-stream")}
    )

    assert response.status_code == 200
    assert "private" not in response.text


@pytest.mark.parametrize("mode", ["success", "invalid_form", "invalid_csv"])
def test_temporary_upload_resources_close_on_success_and_validation_failure(
    client, monkeypatch, mode
):
    closed_files = []
    original_close = UploadFile.close

    async def tracked_close(file):
        await original_close(file)
        closed_files.append(file.file.closed)

    monkeypatch.setattr(UploadFile, "close", tracked_close)
    monkeypatch.setattr(MultiPartParser, "spool_max_size", 1)
    contents = b"invalid csv" if mode == "invalid_csv" else CSV
    response = client.post(
        ENDPOINT,
        files={"file": ("synthetic.csv", contents)},
        data={"downsample_sec": "0" if mode == "invalid_form" else "1"},
    )

    assert response.status_code == (200 if mode == "success" else 422)
    assert closed_files and all(closed_files)


def test_unexpected_error_does_not_expose_data_or_paths(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("private flight data at /private/research/file.csv")

    monkeypatch.setattr("backend.main.build_flight_preview", fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(ENDPOINT, files={"file": ("synthetic.csv", CSV)})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "private" not in response.text


def test_swagger_and_openapi_document_the_upload_and_response_models(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][ENDPOINT]["post"]
    assert "multipart/form-data" in operation["requestBody"]["content"]
    assert {"200", "413", "422", "500"} <= set(operation["responses"])
    success = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert success["$ref"].endswith("/FlightPreview")
    validation = operation["responses"]["422"]["content"]["application/json"]["schema"]
    assert validation["$ref"].endswith("/ErrorResponse")


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"1")]])
def test_stream_limit_counts_received_bytes_without_trusting_content_length(headers):
    async def exercise():
        parser_called = False
        received_chunks = 0
        sent = []

        async def downstream(scope, receive, send):
            nonlocal parser_called
            parser_called = True

        async def receive():
            nonlocal received_chunks
            received_chunks += 1
            return {"type": "http.request", "body": b"1234", "more_body": True}

        async def send(message):
            sent.append(message)

        middleware = PreviewBodyLimitMiddleware(downstream, max_request_bytes=7)
        await middleware(
            {
                "type": "http",
                "method": "POST",
                "path": ENDPOINT,
                "headers": headers,
            },
            receive,
            send,
        )
        assert received_chunks == 2
        assert not parser_called
        assert sent[0]["status"] == 413

    asyncio.run(exercise())
