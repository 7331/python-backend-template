from collections.abc import Sequence
from http import HTTPStatus

from asgi_correlation_id.context import correlation_id
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.utils import is_body_allowed_for_status_code
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.errors import AppError, InvalidInputError, MalformedBodyError
from app.shared.schemas import ErrorBody, ErrorDetail, ErrorDetailCode, ErrorResponse

NO_STORE_HEADERS: dict[str, str] = {"Cache-Control": "no-store"}
UNNAMED_HTTP_ERROR_CODE = "http_error"
MALFORMED_JSON_ERROR_TYPE = "json_invalid"
DETAIL_CODES_BY_ERROR_TYPE: dict[str, ErrorDetailCode] = {
    "missing": ErrorDetailCode.REQUIRED,
    "extra_forbidden": ErrorDetailCode.UNKNOWN_FIELD,
    "string_pattern_mismatch": ErrorDetailCode.PATTERN_MISMATCH,
    "greater_than": ErrorDetailCode.OUT_OF_RANGE,
    "greater_than_equal": ErrorDetailCode.OUT_OF_RANGE,
    "less_than": ErrorDetailCode.OUT_OF_RANGE,
    "less_than_equal": ErrorDetailCode.OUT_OF_RANGE,
    "multiple_of": ErrorDetailCode.OUT_OF_RANGE,
    "enum": ErrorDetailCode.NOT_ALLOWED,
    "literal_error": ErrorDetailCode.NOT_ALLOWED,
}
DETAIL_CODES_BY_ERROR_TYPE_SUFFIX: tuple[tuple[str, ErrorDetailCode], ...] = (
    ("too_short", ErrorDetailCode.TOO_SHORT),
    ("too_long", ErrorDetailCode.TOO_LONG),
    ("_type", ErrorDetailCode.WRONG_TYPE),
    ("_parsing", ErrorDetailCode.WRONG_TYPE),
)


def find_request_id_for_server_error(status_code: int) -> str | None:
    return correlation_id.get() if status_code >= HTTPStatus.INTERNAL_SERVER_ERROR else None


def build_error_json_response(status_code: int, *, error_body: ErrorBody, headers: dict[str, str]) -> JSONResponse:
    body = ErrorResponse(error=error_body)
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"), headers=headers)


def build_app_error_response(error: AppError) -> JSONResponse:
    headers = dict(NO_STORE_HEADERS) | dict(error.response_headers)
    if error.retry_after_seconds is not None:
        headers["Retry-After"] = str(error.retry_after_seconds)
    error_body = ErrorBody(
        code=error.code,
        message=error.message,
        details=error.details,
        parameters=error.parameters,
        request_id=find_request_id_for_server_error(error.status_code),
    )
    return build_error_json_response(error.status_code, error_body=error_body, headers=headers)


def name_http_error_code(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase.lower().replace(" ", "_").replace("-", "_")
    except ValueError:
        return UNNAMED_HTTP_ERROR_CODE


def build_http_exception_response(error: StarletteHTTPException) -> Response:
    headers = dict(NO_STORE_HEADERS) | dict(error.headers or {})
    if not is_body_allowed_for_status_code(error.status_code):
        return Response(status_code=error.status_code, headers=headers)
    error_body = ErrorBody(
        code=name_http_error_code(error.status_code),
        message=str(error.detail).lower(),
        request_id=find_request_id_for_server_error(error.status_code),
    )
    return build_error_json_response(error.status_code, error_body=error_body, headers=headers)


def name_error_detail_code(error_type: str) -> ErrorDetailCode:
    detail_code = DETAIL_CODES_BY_ERROR_TYPE.get(error_type)
    if detail_code is not None:
        return detail_code
    for error_type_suffix, suffix_detail_code in DETAIL_CODES_BY_ERROR_TYPE_SUFFIX:
        if error_type.endswith(error_type_suffix):
            return suffix_detail_code
    return ErrorDetailCode.INVALID_VALUE


def build_json_pointer(location: Sequence[str | int]) -> str:
    return "".join(f"/{str(part).replace('~', '~0').replace('/', '~1')}" for part in location)


def translate_validation_error(error: RequestValidationError) -> AppError:
    validation_errors = error.errors()
    if any(validation_error["type"] == MALFORMED_JSON_ERROR_TYPE for validation_error in validation_errors):
        return MalformedBodyError("the request body is not valid JSON")
    details = tuple(
        ErrorDetail(code=name_error_detail_code(validation_error["type"]), pointer=build_json_pointer(validation_error["loc"]))
        for validation_error in validation_errors
    )
    return InvalidInputError("the request is not valid; see details", details=details)


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(AppError)
    async def handle_app_error(_request: Request, error: AppError) -> JSONResponse:
        return build_app_error_response(error)

    @application.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_request: Request, error: StarletteHTTPException) -> Response:
        return build_http_exception_response(error)

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, error: RequestValidationError) -> JSONResponse:
        return build_app_error_response(translate_validation_error(error))
