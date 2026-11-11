import logging

from app.shared.logging import LogEvent


class FileStored(LogEvent):
    message = "Uploaded file stored"
    operation = "file_store"
    file_row_id: int
    content_type: str
    size_bytes: int


class FileDeleted(LogEvent):
    message = "File deleted from the bucket and the table"
    operation = "file_delete"
    file_row_id: int


class UploadRefused(LogEvent):
    level = logging.WARNING
    message = "Upload refused: the bucket holds an object the API would not have signed for"
    operation = "file_store"
    reason: str
    content_type: str
    size_bytes: int
