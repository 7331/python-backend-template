from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StoredObject(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    size_bytes: int = Field(validation_alias="ContentLength")
    content_type: str = Field(validation_alias="ContentType")
    entity_tag: str = Field(validation_alias="ETag")


class PresignedUrl(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    expires_at: datetime
