from collections.abc import Iterator
from http import HTTPStatus

from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import JsonValue

from app.rate_limit_middleware import UNLIMITED_PATHS
from app.shared.error_responses import ERROR_CODES_EXTENSION, ERROR_PARAMETERS_EXTENSION
from app.shared.errors import (
    AppError,
    HostNotAllowedError,
    InvalidInputError,
    MalformedBodyError,
    RateLimitedError,
    RequestBodyTooLargeError,
)
from app.shared.schemas import ErrorResponse, RequestBodyLimitParameters

ERROR_RESPONSE_SCHEMA_NAME = "ErrorResponse"
REQUEST_ID_HEADER_NAME = "X-Request-ID"
REQUEST_ID_HEADER_COMPONENT_NAME = "RequestId"
REQUEST_ID_HEADERS: dict[str, JsonValue] = {
    REQUEST_ID_HEADER_NAME: {"$ref": f"#/components/headers/{REQUEST_ID_HEADER_COMPONENT_NAME}"}
}
SHARED_RESPONSE_HEADERS: dict[str, JsonValue] = {
    REQUEST_ID_HEADER_COMPONENT_NAME: {
        "description": "The server-minted id of this request. A 5xx body repeats it as `request_id`.",
        "schema": {"type": "string"},
    }
}
RETRY_AFTER_HEADERS: dict[str, JsonValue] = {"Retry-After": {"schema": {"type": "integer"}}}
ERROR_RESPONSE_CONTENT: dict[str, JsonValue] = {
    "application/json": {"schema": {"$ref": f"#/components/schemas/{ERROR_RESPONSE_SCHEMA_NAME}"}}
}
SHARED_ERROR_RESPONSES: dict[str, JsonValue] = {
    "ApiError": {
        "description": "Any error not listed for the operation, in the `ErrorResponse` shape.",
        "headers": REQUEST_ID_HEADERS,
        "content": ERROR_RESPONSE_CONTENT,
    },
}


def name_operation_after_handler(route: APIRoute) -> str:
    return route.name


def strip_titles_below(node: JsonValue) -> None:
    match node:
        case dict():
            match node.get("title"):
                case str():
                    del node["title"]
                case _:
                    pass
            for key, value in node.items():
                match (key, value):
                    case ("properties", dict()):
                        for property_schema in value.values():
                            strip_titles_below(property_schema)
                    case _:
                        strip_titles_below(value)
        case list():
            for item in node:
                strip_titles_below(item)
        case _:
            pass


def reference_shared_response(response_name: str) -> dict[str, JsonValue]:
    return {"$ref": f"#/components/responses/{response_name}"}


def read_object_member(container: dict[str, JsonValue], *, member_name: str) -> dict[str, JsonValue]:
    match container.setdefault(member_name, {}):
        case dict() as member:
            return member
        case _:
            return {}


def read_list_member(container: dict[str, JsonValue], *, member_name: str) -> list[JsonValue]:
    match container.setdefault(member_name, []):
        case list() as member:
            return member
        case _:
            return []


def iterate_strings(values: list[JsonValue]) -> Iterator[str]:
    for value in values:
        match value:
            case str():
                yield value
            case _:
                pass


def add_error_codes(
    responses: dict[str, JsonValue], *, status_code: HTTPStatus, error_codes: tuple[str, ...]
) -> dict[str, JsonValue]:
    status_response = read_object_member(responses, member_name=str(status_code.value))
    listed_codes = read_list_member(status_response, member_name=ERROR_CODES_EXTENSION)
    listed_codes.extend(error_code for error_code in error_codes if error_code not in listed_codes)
    return status_response


def is_error_status(status_code: str) -> bool:
    return status_code.isdigit() and int(status_code) >= HTTPStatus.BAD_REQUEST


def complete_error_response(response: dict[str, JsonValue]) -> None:
    listed_codes = read_list_member(response, member_name=ERROR_CODES_EXTENSION)
    sorted_codes = sorted(iterate_strings(listed_codes))
    listed_codes[:] = sorted_codes
    response["description"] = "Error codes: " + ", ".join(f"`{error_code}`" for error_code in sorted_codes) + "."
    response["content"] = ERROR_RESPONSE_CONTENT


def add_request_body_limit_error(responses: dict[str, JsonValue]) -> None:
    too_large_response = add_error_codes(
        responses, status_code=HTTPStatus.CONTENT_TOO_LARGE, error_codes=(RequestBodyTooLargeError.code,)
    )
    error_parameters = read_object_member(too_large_response, member_name=ERROR_PARAMETERS_EXTENSION)
    error_parameters[RequestBodyTooLargeError.code] = RequestBodyLimitParameters.model_json_schema()


def document_operation_errors(operation: JsonValue, *, path: str) -> None:
    match operation:
        case dict():
            responses = read_object_member(operation, member_name="responses")
            add_error_codes(responses, status_code=HTTPStatus.BAD_REQUEST, error_codes=(HostNotAllowedError.code,))
            if "requestBody" in operation:
                add_request_body_limit_error(responses)
            if responses.pop("422", None) is not None:
                validation_codes = (
                    (InvalidInputError.code, MalformedBodyError.code)
                    if "requestBody" in operation
                    else (InvalidInputError.code,)
                )
                add_error_codes(responses, status_code=HTTPStatus.BAD_REQUEST, error_codes=validation_codes)
            if path not in UNLIMITED_PATHS:
                rate_limited_response = add_error_codes(
                    responses, status_code=HTTPStatus.TOO_MANY_REQUESTS, error_codes=(RateLimitedError.code,)
                )
                read_object_member(rate_limited_response, member_name="headers").update(RETRY_AFTER_HEADERS)
            add_error_codes(responses, status_code=HTTPStatus.INTERNAL_SERVER_ERROR, error_codes=(AppError.code,))
            for status_code, response in responses.items():
                match response:
                    case dict():
                        if is_error_status(status_code):
                            complete_error_response(response)
                        read_object_member(response, member_name="headers").update(REQUEST_ID_HEADERS)
                    case _:
                        pass
            responses.setdefault("default", reference_shared_response("ApiError"))
        case _:
            pass


def add_error_components(components: dict[str, JsonValue]) -> None:
    component_schemas = read_object_member(components, member_name="schemas")
    component_schemas.pop("HTTPValidationError", None)
    component_schemas.pop("ValidationError", None)
    error_response_schema: dict[str, JsonValue] = ErrorResponse.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    component_schemas.update(read_object_member(error_response_schema, member_name="$defs"))
    error_response_schema.pop("$defs")
    component_schemas[ERROR_RESPONSE_SCHEMA_NAME] = error_response_schema
    read_object_member(components, member_name="responses").update(SHARED_ERROR_RESPONSES)
    read_object_member(components, member_name="headers").update(SHARED_RESPONSE_HEADERS)


def document_path_errors(path_item: JsonValue, *, path: str) -> None:
    match path_item:
        case dict():
            for operation in path_item.values():
                document_operation_errors(operation, path=path)
        case _:
            pass


def build_contract_openapi(openapi_schema: dict[str, JsonValue]) -> dict[str, JsonValue]:
    add_error_components(read_object_member(openapi_schema, member_name="components"))
    for path, path_item in read_object_member(openapi_schema, member_name="paths").items():
        document_path_errors(path_item, path=path)
    for section_name in ("paths", "components"):
        strip_titles_below(openapi_schema.get(section_name))
    return openapi_schema


def install_openapi_contract(application: FastAPI) -> None:
    generate_default_openapi = application.openapi

    def generate_contract_openapi() -> dict[str, JsonValue]:
        if application.openapi_schema is None:
            application.openapi_schema = build_contract_openapi(generate_default_openapi())
        return application.openapi_schema

    application.openapi = generate_contract_openapi  # ty: ignore[invalid-assignment]  # FastAPI's override point
