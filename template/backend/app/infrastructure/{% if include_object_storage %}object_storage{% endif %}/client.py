from collections.abc import Callable
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from functools import partial

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from botocore.session import get_session
from pydantic import BaseModel, ConfigDict, Field

from app.infrastructure.object_storage.configuration import ObjectStorageSettings, read_object_storage_settings
from app.infrastructure.object_storage.errors import (
    ObjectChangedError,
    ObjectMissingError,
    ObjectStorageUnavailableError,
)
from app.infrastructure.object_storage.log_events import ObjectStorageCallFailed, ObjectStorageClientOpened
from app.infrastructure.object_storage.types import PresignedUrl, StoredObject
from app.shared import logging as log
from app.shared.blocking_executor import BlockingExecutor

logger = log.get_logger(__name__)

OBJECT_STORAGE_EXECUTOR_WORKERS = 8
OBJECT_STORAGE_CONNECT_TIMEOUT_SECONDS = 3
OBJECT_STORAGE_READ_TIMEOUT_SECONDS = 10
OBJECT_STORAGE_MAXIMUM_ATTEMPTS = 2
MAXIMUM_SINGLE_REQUEST_OBJECT_BYTES = 5 * 1024 * 1024 * 1024
OBJECT_MISSING_ERROR_CODES = frozenset({"404", "NoSuchKey", "NotFound"})
OBJECT_CHANGED_ERROR_CODES = frozenset({"412", "PreconditionFailed"})
ATTACHMENT_CONTENT_DISPOSITION = "attachment"


class ObjectStorageErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    code: str = Field(default="", validation_alias="Code")


class ObjectStorageErrorReply(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    error: ObjectStorageErrorDetail = Field(default=ObjectStorageErrorDetail(), validation_alias="Error")


def read_error_code(client_error: ClientError) -> str:
    return ObjectStorageErrorReply.model_validate(client_error.response).error.code


def build_unavailable_error(error: BotoCoreError | ClientError, *, call_name: str) -> ObjectStorageUnavailableError:
    error_code = read_error_code(error) if isinstance(error, ClientError) else ""
    log.emit(
        logger,
        event=ObjectStorageCallFailed(call_name=call_name, error_type=type(error).__name__, error_code=error_code),
    )
    return ObjectStorageUnavailableError("object storage did not complete the call")


class ObjectStorageClient:
    def __init__(self, object_storage_settings: ObjectStorageSettings, *, blocking_executor: BlockingExecutor) -> None:
        self.bucket = object_storage_settings.bucket
        self.upload_url_lifetime = timedelta(seconds=object_storage_settings.upload_url_lifetime_seconds)
        self.download_url_lifetime = timedelta(seconds=object_storage_settings.download_url_lifetime_seconds)
        self.blocking_executor = blocking_executor
        session = get_session()
        client_configuration = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if object_storage_settings.uses_path_style_addressing else "virtual"},
            connect_timeout=OBJECT_STORAGE_CONNECT_TIMEOUT_SECONDS,
            read_timeout=OBJECT_STORAGE_READ_TIMEOUT_SECONDS,
            retries={"total_max_attempts": OBJECT_STORAGE_MAXIMUM_ATTEMPTS, "mode": "standard"},
        )
        self.call_client = session.create_client(
            "s3",
            endpoint_url=object_storage_settings.endpoint_url,
            region_name=object_storage_settings.region,
            aws_access_key_id=object_storage_settings.access_key_id,
            aws_secret_access_key=object_storage_settings.secret_access_key.get_secret_value(),
            config=client_configuration,
        )
        self.signing_client = session.create_client(
            "s3",
            endpoint_url=object_storage_settings.public_endpoint_url,
            region_name=object_storage_settings.region,
            aws_access_key_id=object_storage_settings.access_key_id,
            aws_secret_access_key=object_storage_settings.secret_access_key.get_secret_value(),
            config=client_configuration,
        )

    def create_upload_url(self, object_key: str, *, content_type: str, size_bytes: int) -> PresignedUrl:
        if not 0 < size_bytes <= MAXIMUM_SINGLE_REQUEST_OBJECT_BYTES:
            raise ValueError("this client signs no single upload over 5 GiB; a larger object needs a multipart upload")
        expires_at = datetime.now(UTC) + self.upload_url_lifetime
        return PresignedUrl(
            url=self.signing_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": object_key,
                    "ContentType": content_type,
                    "ContentLength": size_bytes,
                },
                ExpiresIn=int(self.upload_url_lifetime.total_seconds()),
            ),
            expires_at=expires_at,
        )

    def create_download_url(self, object_key: str) -> PresignedUrl:
        expires_at = datetime.now(UTC) + self.download_url_lifetime
        return PresignedUrl(
            url=self.signing_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": object_key},
                ExpiresIn=int(self.download_url_lifetime.total_seconds()),
            ),
            expires_at=expires_at,
        )

    async def run_call[ReplyType](self, call: Callable[[], ReplyType], *, call_name: str) -> ReplyType:
        try:
            return await self.blocking_executor.run_blocking(call)
        except ClientError as client_error:
            error_code = read_error_code(client_error)
            if error_code in OBJECT_MISSING_ERROR_CODES:
                raise ObjectMissingError(call_name) from client_error
            if error_code in OBJECT_CHANGED_ERROR_CODES:
                raise ObjectChangedError(call_name) from client_error
            raise build_unavailable_error(client_error, call_name=call_name) from client_error
        except BotoCoreError as transport_error:
            raise build_unavailable_error(transport_error, call_name=call_name) from transport_error

    async def find_stored_object(self, object_key: str) -> StoredObject | None:
        try:
            reply = await self.run_call(
                partial(self.call_client.head_object, Bucket=self.bucket, Key=object_key), call_name="head_object"
            )
        except ObjectMissingError:
            return None
        return StoredObject.model_validate(reply)

    async def copy_object_as_attachment(
        self, source_object: StoredObject, *, source_object_key: str, destination_object_key: str
    ) -> None:
        await self.run_call(
            partial(
                self.call_client.copy_object,
                Bucket=self.bucket,
                Key=destination_object_key,
                CopySource={"Bucket": self.bucket, "Key": source_object_key},
                CopySourceIfMatch=source_object.entity_tag,
                MetadataDirective="REPLACE",
                ContentType=source_object.content_type,
                ContentDisposition=ATTACHMENT_CONTENT_DISPOSITION,
            ),
            call_name="copy_object",
        )

    async def delete_object(self, object_key: str) -> None:
        await self.run_call(
            partial(self.call_client.delete_object, Bucket=self.bucket, Key=object_key), call_name="delete_object"
        )

    def close(self) -> None:
        self.call_client.close()
        self.signing_client.close()


def open_object_storage_client(exit_stack: AsyncExitStack) -> ObjectStorageClient:
    object_storage_settings = read_object_storage_settings()
    blocking_executor = BlockingExecutor(
        executor_name="object_storage", maximum_workers=OBJECT_STORAGE_EXECUTOR_WORKERS
    )
    exit_stack.callback(blocking_executor.close)
    object_storage_client = ObjectStorageClient(object_storage_settings, blocking_executor=blocking_executor)
    exit_stack.callback(object_storage_client.close)
    log.emit(
        logger,
        event=ObjectStorageClientOpened(
            endpoint_url=object_storage_settings.endpoint_url,
            public_endpoint_url=object_storage_settings.public_endpoint_url,
            bucket=object_storage_settings.bucket,
        ),
    )
    return object_storage_client
