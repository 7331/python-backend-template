from enum import StrEnum
from ipaddress import IPv4Network, IPv6Network
from typing import TypedDict

from pydantic import BaseModel, ConfigDict

from app.infrastructure.object_storage.client import ObjectStorageClient
from app.infrastructure.postgres.client import Database
from app.infrastructure.rate_limit.postgres_limiter_store import PostgresRateLimiter
from app.shared.blocking_executor import BlockingExecutor


class Resources(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    file_read_executor: BlockingExecutor
    database: Database
    object_storage: ObjectStorageClient
    rate_limiter: PostgresRateLimiter
    trusted_proxy_networks: tuple[IPv4Network | IPv6Network, ...]


class ApiLifespanState(TypedDict):
    resources: Resources


class ProcessRole(StrEnum):
    WORKER = "worker"
    COMMAND = "command"


class ProcessResources(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    file_read_executor: BlockingExecutor
    database: Database
