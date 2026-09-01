"""Shared API request and response types."""

from typing import Any, Self

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Validated offset pagination shared by list endpoints."""

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ErrorDetail(BaseModel):
    """Stable error payload used by API error envelopes."""

    code: str
    message: str
    details: Any | None = None


class ErrorEnvelope(BaseModel):
    """Stable top-level API error response."""

    error: ErrorDetail

    @classmethod
    def from_parts(
        cls, code: str, message: str, details: Any | None = None
    ) -> Self:
        return cls(error=ErrorDetail(code=code, message=message, details=details))
