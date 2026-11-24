from fastapi import FastAPI

from app.starter.files.router import files_router


def add_option_routers(application: FastAPI) -> None:
    application.include_router(files_router)
