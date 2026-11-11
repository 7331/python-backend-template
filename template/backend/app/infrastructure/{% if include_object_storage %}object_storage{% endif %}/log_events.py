import logging

from app.shared.logging import LogEvent


class ObjectStorageClientOpened(LogEvent):
    message = "Object storage client opened; the bucket is first reached by a request"
    operation = "object_storage_open"
    endpoint_url: str
    public_endpoint_url: str
    bucket: str


class ObjectStorageCallFailed(LogEvent):
    level = logging.ERROR
    message = "Object storage call failed"
    operation = "object_storage_call"
    call_name: str
    error_type: str
    error_code: str
