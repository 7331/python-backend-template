from fastapi import APIRouter

from app.configuration import read_application_settings
from app.sample.notices.schemas import ServiceNoticeResponse
from app.shared.path_params import API_PREFIX

notices_router = APIRouter(prefix=API_PREFIX, tags=["notices"])


@notices_router.get("/notices/current")
async def read_current_service_notice() -> ServiceNoticeResponse:
    return ServiceNoticeResponse(message=read_application_settings().service_notice_message)
