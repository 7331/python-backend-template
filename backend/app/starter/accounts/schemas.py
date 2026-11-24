from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, JsonValue

from app.shared.schemas import ApiRequest, ApiResponse, ErrorParameters

AccountUsername = Annotated[str, Field(pattern=r"^[a-z0-9_]{3,32}$")]
PasskeyLabel = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[^\x00-\x1f\x7f]+$")]


class PasskeyRegistrationOptionsRequest(ApiRequest):
    username: AccountUsername


class PasskeyRegistrationRequest(ApiRequest):
    credential: dict[str, JsonValue]
    label: PasskeyLabel = "passkey"


class PasskeyAuthenticationRequest(ApiRequest):
    credential: dict[str, JsonValue]


class AccountResponse(ApiResponse):
    account_id: str
    username: str
    created_at: datetime


class CredentialIdLengthParameters(ErrorParameters):
    maximum_bytes: int


class PasskeyClientDataCarrier(BaseModel):
    client_data_json: str = Field(validation_alias="clientDataJSON")


class PasskeyCredentialEnvelope(BaseModel):
    response: PasskeyClientDataCarrier
