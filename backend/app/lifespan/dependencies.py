from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import Scope

from app.lifespan.resources import Resources


def read_resources_of_scope(connection_scope: Scope) -> Resources:
    return connection_scope["state"]["resources"]


def get_resources(request: Request) -> Resources:
    return read_resources_of_scope(request.scope)


ResourcesDependency = Annotated[Resources, Depends(get_resources)]


async def get_database_session(resources: ResourcesDependency) -> AsyncIterator[AsyncSession]:
    async with resources.database.session_factory() as session, session.begin():
        yield session


DatabaseSession = Annotated[AsyncSession, Depends(get_database_session, scope="function")]
