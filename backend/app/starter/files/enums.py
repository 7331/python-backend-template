from enum import StrEnum


class FileContentType(StrEnum):
    PNG = "image/png"
    JPEG = "image/jpeg"
    PDF = "application/pdf"


class UploadRefusalReason(StrEnum):
    CONTENT_TYPE_NOT_ALLOWED = "content_type_not_allowed"
    SIZE_NOT_ALLOWED = "size_not_allowed"
