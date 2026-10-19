"""HTTP error schemas; successful previews use the domain dataclass directly."""

from pydantic import BaseModel

from simulator.preview import ValidationIssue


class ErrorDetail(BaseModel):
    code: str
    message: str
    issues: list[ValidationIssue]


class ErrorResponse(BaseModel):
    error: ErrorDetail
