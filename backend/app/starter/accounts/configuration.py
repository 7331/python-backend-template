from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class AccountSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STARTER_ACCOUNTS_", extra="ignore")

    relying_party_name: str = "starter-app"
    public_base_url: str = "http://localhost:8000"


class RelyingParty(BaseModel):
    model_config = ConfigDict(frozen=True)

    relying_party_name: str
    relying_party_id: str
    expected_origin: str


def build_relying_party(account_settings: AccountSettings) -> RelyingParty:
    parts = urlsplit(account_settings.public_base_url.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("STARTER_ACCOUNTS_PUBLIC_BASE_URL must be an http(s) origin")
    return RelyingParty(
        relying_party_name=account_settings.relying_party_name,
        relying_party_id=parts.hostname,
        expected_origin=f"{parts.scheme}://{parts.netloc}".lower(),
    )


@lru_cache
def read_relying_party() -> RelyingParty:
    return build_relying_party(AccountSettings())
