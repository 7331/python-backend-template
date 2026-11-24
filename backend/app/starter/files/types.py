from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.infrastructure.object_storage.types import PresignedUrl

MAXIMUM_FILE_SIZE_BYTES = 10 * 1024 * 1024


class FileUpload(BaseModel):
    model_config = ConfigDict(frozen=True)

    upload_id: str
    content_type: str
    upload_url: PresignedUrl


class StoredFile(BaseModel):
    model_config = ConfigDict(frozen=True)

    file_id: str
    content_type: str
    size_bytes: int
    created_at: datetime
    download_url: PresignedUrl
