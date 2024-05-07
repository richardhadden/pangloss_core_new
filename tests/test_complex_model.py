import pytest
import pytest_asyncio

import asyncio
import typing
import uuid

from pydantic import AnyHttpUrl

from pangloss_core.model_setup.model_manager import ModelManager
from pangloss_core.settings import BaseSettings
from pangloss_core.application import get_application
from pangloss_core.database import Database
from pangloss_core.users import create_user, UserInDB


from .test_application.models import ZoteroEntry, Factoid, Person, Statement
from pangloss_core.model_setup.setup_procedures import setup_build_model_definition


class Settings(BaseSettings):
    PROJECT_NAME: str = "MyTestApp"
    BACKEND_CORS_ORIGINS: list[AnyHttpUrl] = []

    DB_URL: str = "bolt://localhost:7688"
    DB_USER: str = "neo4j"
    DB_PASSWORD: str = "password"
    DB_DATABASE_NAME: str = "neo4j"

    INSTALLED_APPS: list[str] = ["pangloss_core", "test_application"]
    authjwt_secret_key: str = "SECRET"

    INTERFACE_LANGUAGES: list[str] = ["en"]


settings = Settings()
application = get_application(settings)


def test_something_or_other():
    pass
    # assert setup_build_model_config(Statement) == {}
