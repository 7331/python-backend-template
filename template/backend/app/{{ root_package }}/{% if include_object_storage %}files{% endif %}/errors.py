from app.shared.errors import AppError


class UploadNotFoundError(AppError):
    code = "upload_not_found"
    status_code = 404


class UploadNotAllowedError(AppError):
    code = "upload_not_allowed"
    status_code = 400


class UploadChangedError(AppError):
    code = "upload_changed"
    status_code = 409


class FileMissingError(AppError):
    code = "file_not_found"
    status_code = 404
