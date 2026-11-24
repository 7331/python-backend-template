from app.shared.errors import AppError


class ObjectStorageUnavailableError(AppError):
    code = "object_storage_unavailable"
    status_code = 503


class ObjectChangedError(Exception):
    pass


class ObjectMissingError(Exception):
    pass
