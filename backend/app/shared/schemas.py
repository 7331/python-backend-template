from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny


class ApiRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ApiResponse(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, json_schema_serialization_defaults_required=True)


class ErrorDetailCode(StrEnum):
    REQUIRED = "required"
    UNKNOWN_FIELD = "unknown_field"
    WRONG_TYPE = "wrong_type"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    PATTERN_MISMATCH = "pattern_mismatch"
    OUT_OF_RANGE = "out_of_range"
    NOT_ALLOWED = "not_allowed"
    INVALID_VALUE = "invalid_value"


class ErrorDetail(ApiResponse):
    code: ErrorDetailCode
    pointer: str


class ErrorParameters(ApiResponse):
    pass


class RequestBodyLimitParameters(ErrorParameters):
    maximum_bytes: int


class ErrorBody(ApiResponse):
    code: str
    message: str
    details: tuple[ErrorDetail, ...] = Field(default=(), exclude_if=lambda details: not details)
    parameters: SerializeAsAny[ErrorParameters] | None = Field(
        default=None, exclude_if=lambda parameters: parameters is None
    )
    request_id: str | None = Field(default=None, exclude_if=lambda request_id: request_id is None)


class ErrorResponse(ApiResponse):
    error: ErrorBody


class HealthResponse(ApiResponse):
    status: str
