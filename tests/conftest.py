import pytest
import asyncio


from pangloss_core.settings import BaseSettings
from pangloss_core.database import initialise_database_driver
from pangloss_core.indexes import install_indexes_and_constraints
from pydantic import AnyHttpUrl


class Settings(BaseSettings):
    PROJECT_NAME: str = "MyTestApp"
    BACKEND_CORS_ORIGINS: list[AnyHttpUrl] = []

    DB_URL: str = "bolt://localhost:7688"
    DB_USER: str = "neo4j"
    DB_PASSWORD: str = "password"
    DB_DATABASE_NAME: str = "neo4j"

    INSTALLED_APPS: list[str] = ["pangloss_core"]
    authjwt_secret_key: str = "SECRET"

    INTERFACE_LANGUAGES: list[str] = ["en"]


settings = Settings()


initialise_database_driver(settings)
install_indexes_and_constraints()


@pytest.fixture(scope="session")
def event_loop(request):

    from pangloss_core.database import close_database_connection, Database

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.run_until_complete(Database.dangerously_clear_database())
    loop.run_until_complete(close_database_connection())
    loop.close()
