from pydantic import JsonValue

from app.shared.errors import AppError

ERROR_CODES_EXTENSION = "x-error-codes"
ERROR_PARAMETERS_EXTENSION = "x-error-parameters"


def describe_status_error_response(status_error_classes: tuple[type[AppError], ...]) -> dict[str, JsonValue]:
    error_codes: list[JsonValue] = [*sorted({error_class.code for error_class in status_error_classes})]
    error_parameters: dict[str, JsonValue] = {
        error_class.code: error_class.parameters_model.model_json_schema()
        for error_class in status_error_classes
        if error_class.parameters_model is not None
    }
    if not error_parameters:
        return {ERROR_CODES_EXTENSION: error_codes}
    return {ERROR_CODES_EXTENSION: error_codes, ERROR_PARAMETERS_EXTENSION: error_parameters}


def describe_error_responses(error_classes: tuple[type[AppError], ...]) -> dict[int | str, dict[str, JsonValue]]:
    return {
        status_code: describe_status_error_response(
            tuple(error_class for error_class in error_classes if error_class.status_code == status_code)
        )
        for status_code in sorted({error_class.status_code for error_class in error_classes})
    }
