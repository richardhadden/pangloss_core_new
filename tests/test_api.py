import pytest
import pytest_asyncio

import typing
import uuid

from fastapi.testclient import TestClient
from pydantic import AnyHttpUrl

from pangloss_core.model_setup.model_manager import ModelManager
from pangloss_core.settings import BaseSettings
from pangloss_core.application import get_application
from pangloss_core.database import Database
from pangloss_core.users import create_user, UserInDB

from .test_application.models import ZoteroEntry

import httpx


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

# client = TestClient(application)


@pytest_asyncio.fixture()
async def client() -> typing.AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        app=application, base_url="http://test", follow_redirects=True
    ) as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_sanity(client):
    """Make sure client is fired up and returning docs; and that application setup runs
    and imports the test_application models"""
    response = await client.get("/docs")
    assert response.status_code == 200

    assert (
        ModelManager._registered_models != []
    )  # Quick test to make sure there are some models


ZOTERO_ENTRY_UID = uuid.uuid4()


def not_none[T](obj: typing.Optional[T]) -> T:
    assert obj is not None
    return obj


@pytest_asyncio.fixture(scope="function")
async def zotero_entry() -> typing.AsyncIterator[ZoteroEntry]:
    zotero_entry = ZoteroEntry(
        uid=ZOTERO_ENTRY_UID, label="A Test Zotero Entry", real_type="ZoteroEntry"
    )
    await zotero_entry.create()
    yield zotero_entry
    await Database.dangerously_clear_database()


USERNAME = "jsmith"
EMAIL = "jsmith@jsmith.net"
PASSWORD = "password"


@pytest_asyncio.fixture
async def user():
    yield (
        await create_user(
            username=USERNAME, email=EMAIL, password=PASSWORD, admin=False
        )
    )
    await Database.dangerously_clear_database()


@pytest.mark.asyncio
async def test_user_fixture(user: str):
    user_in_db = await UserInDB.get(username=USERNAME)
    assert user_in_db
    assert user_in_db.username == user


@pytest.mark.asyncio
async def test_login(user, client: httpx.AsyncClient):
    response = await client.post("/api/users/login")
    # Test not providing username or password returns
    # status code for unprocessable entity
    assert response.status_code == 422

    response = await client.post(
        "/api/users/login", data={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.cookies["access_token"]
    assert response.cookies["logged_in_user_name"]


@pytest_asyncio.fixture
async def logged_in_client(user, client):
    response = await client.post(
        "/api/users/login", data={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 200
    async with httpx.AsyncClient(
        app=application,
        base_url="http://test",
        cookies=response.cookies,
        follow_redirects=True,
    ) as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_zotero_entry_written(zotero_entry: ZoteroEntry):
    """Tests the zotero_entry fixture"""
    z = await ZoteroEntry.get_view(uid=not_none(zotero_entry.uid))
    assert z.uid == zotero_entry.uid


@pytest.mark.asyncio
async def test_api_get_zotero_entry_when_unauthorised_is_wrong(
    client: httpx.AsyncClient, zotero_entry
):

    response = await client.get(
        f"/api/ZoteroEntry/{ZOTERO_ENTRY_UID}", follow_redirects=True
    )
    assert response.status_code == 401
    data = response.json()

    assert data == {"detail": "Not authenticated"}


@pytest.mark.asyncio
async def test_api_get_zotero_entry_when_logged_in(
    logged_in_client: httpx.AsyncClient, zotero_entry: ZoteroEntry
):
    response = await logged_in_client.get(f"/api/ZoteroEntry/{ZOTERO_ENTRY_UID}")
    assert response.status_code == 200
    data = response.json()
    assert uuid.UUID(data["uid"]) == zotero_entry.uid
    assert data["realType"] == "ZoteroEntry"
    assert data["label"] == "A Test Zotero Entry"


@pytest.mark.asyncio
async def test_list_item_with_api(client: httpx.AsyncClient, zotero_entry: ZoteroEntry):
    response = await client.get("/api/ZoteroEntry", follow_redirects=True)
    assert response.status_code == 200
    data = response.json()
    assert data

    assert len(data["results"]) == 1
    assert data["count"] == 1
    assert data["nextUrl"] is None
    assert data["nextPage"] is None
    assert data["previousPage"] is None
    assert data["previousUrl"] is None
    item = data["results"][0]

    assert uuid.UUID(item["uid"]) == zotero_entry.uid
    assert item["realType"] == "ZoteroEntry"
    assert item["label"] == "A Test Zotero Entry"
