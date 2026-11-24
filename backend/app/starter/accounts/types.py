from datetime import datetime

from pydantic import BaseModel, ConfigDict, SecretStr

ACCOUNT_SESSION_COOKIE_NAME = "__Host-starter_account_session"


class AccountAccess(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_id: int
    account_public_id: str
    username: str
    account_session_id: int


class AccountSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_id: int
    account_public_id: str
    username: str
    created_at: datetime


class StartedAccountSession(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_token: SecretStr
    expires_at: datetime
    account: AccountSummary


class ConsumedPasskeyChallenge(BaseModel):
    model_config = ConfigDict(frozen=True)

    challenge: bytes
    sign_up_username: str | None
    sign_up_user_handle: bytes | None
