"""Local flight-preview API: python -m uvicorn backend.main:app --reload."""

from typing import Annotated

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from simulator.preview import (
    MAX_UPLOAD_BYTES,
    FlightPreview,
    PreviewValidationError,
    build_flight_preview,
)

from .body_limit import PreviewBodyLimitMiddleware
from .schemas import ErrorResponse


app = FastAPI(
    title="Electric Aircraft Flight Preview API",
    description="Validate a flight CSV and preview its waypoints before simulation.",
    version="0.1.0",
)
app.add_middleware(PreviewBodyLimitMiddleware)


@app.exception_handler(PreviewValidationError)
async def preview_validation_error(
    request: Request, error: PreviewValidationError
) -> JSONResponse:
    status = 413 if error.issue.code == "file_too_large" else 422
    return JSONResponse(
        error.to_dict(), status_code=status, headers={"Cache-Control": "no-store"}
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    # Framework validation errors can contain raw submitted values. Only inspect
    # the known location/type; do not serialize the original error or request.
    first = error.errors()[0]
    field = first["loc"][-1]
    if field == "file":
        code = "missing_file" if first["type"] == "missing" else "invalid_file"
        message = "Upload one CSV file in the file field."
    elif field == "downsample_sec":
        code = "invalid_downsample_sec"
        message = "downsample_sec must be finite and positive."
    else:
        code = "invalid_request"
        message = "The upload request is invalid."
    safe_error = PreviewValidationError(code, message)
    return await preview_validation_error(request, safe_error)


@app.exception_handler(HTTPException)
async def http_error(request: Request, error: HTTPException) -> JSONResponse:
    if error.status_code == 400:
        safe_error = PreviewValidationError(
            "invalid_multipart", "The multipart upload could not be read."
        )
        return await preview_validation_error(request, safe_error)
    safe_error = PreviewValidationError(
        "http_error", "The request could not be handled."
    )
    headers = dict(error.headers or {})
    headers["Cache-Control"] = "no-store"
    return JSONResponse(
        safe_error.to_dict(), status_code=error.status_code, headers=headers
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
    return JSONResponse(
        {
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred.",
                "issues": [],
            }
        },
        status_code=500,
        headers={"Cache-Control": "no-store"},
    )


@app.post(
    "/api/flight-previews",
    response_model=FlightPreview,
    summary="Validate a CSV and preview its waypoints",
    description=(
        "Upload a UTF-8 CSV with time(ms), LAT, LNG, and PRESSURE_ALT. "
        "Units are milliseconds, degrees, degrees, and meters. "
        "File limit: 10 MiB. The simulation is not executed."
    ),
    responses={
        413: {"model": ErrorResponse, "description": "File or request size exceeded"},
        422: {
            "model": ErrorResponse,
            "description": "CSV or request validation failed",
        },
        500: {"model": ErrorResponse, "description": "Unexpected internal error"},
    },
)
async def create_flight_preview(
    file: Annotated[UploadFile, File(description="Flight CSV, at most 10 MiB")],
    downsample_sec: Annotated[
        float,
        Form(gt=0, allow_inf_nan=False, description="Waypoint selection interval (s)"),
    ] = 1.0,
) -> FlightPreview:
    try:
        contents = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(contents) > MAX_UPLOAD_BYTES:
            raise PreviewValidationError(
                "file_too_large", "CSV must be at most 10 MiB."
            )
        # CSV parsing/coordinate calculation is synchronous work. Keep it off
        # the server event loop so other requests can still be served.
        return await run_in_threadpool(
            build_flight_preview, contents, downsample_sec=downsample_sec
        )
    finally:
        await file.close()
