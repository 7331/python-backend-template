from fastapi import FastAPI

from app.allowed_host_middleware import AllowedHostMiddleware
from app.configuration import read_application_settings
from app.lifespan.api_lifespan import run_api_lifespan
from app.lifespan.dependencies import ResourcesDependency
from app.openapi_contract import install_openapi_contract, name_operation_after_handler
from app.option_routers import add_option_routers
from app.rate_limit_middleware import RateLimitRequestsMiddleware
from app.request_body_limit_middleware import RequestBodyLimitMiddleware
from app.request_log_middleware import RequestLogMiddleware
from app.shared.correlation import ServerMintedCorrelationIdMiddleware
from app.shared.exception_handlers import register_exception_handlers
from app.shared.logging import configure_logging
from app.shared.schemas import HealthResponse
from app.starter.accounts.configuration import read_relying_party
from app.starter.accounts.router import accounts_router
from app.unhandled_error_middleware import UnhandledErrorMiddleware


async def read_health() -> HealthResponse:
    return HealthResponse(status="ok")


async def read_readiness(resources: ResourcesDependency) -> HealthResponse:
    await resources.database.refuse_unreachable_database()
    return HealthResponse(status="ok")


def create_app() -> FastAPI:
    application_settings = read_application_settings()
    configure_logging(application_settings.log_level)
    application = FastAPI(
        title=application_settings.service_name,
        lifespan=run_api_lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        generate_unique_id_function=name_operation_after_handler,
    )
    add_option_routers(application)
    application.add_api_route("/ready", read_readiness, methods=["GET", "HEAD"], include_in_schema=False)
    application.add_api_route("/health", read_health, methods=["GET", "HEAD"], include_in_schema=False)
    application.include_router(accounts_router)
    application.add_middleware(RateLimitRequestsMiddleware)
    application.add_middleware(RequestBodyLimitMiddleware)
    application.add_middleware(
        AllowedHostMiddleware,
        allowed_hosts=(*application_settings.list_allowed_hosts(), read_relying_party().relying_party_id),
    )
    application.add_middleware(UnhandledErrorMiddleware)
    application.add_middleware(RequestLogMiddleware)
    application.add_middleware(ServerMintedCorrelationIdMiddleware)
    register_exception_handlers(application)
    install_openapi_contract(application)
    return application
