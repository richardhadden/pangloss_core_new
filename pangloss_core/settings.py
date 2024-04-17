from __future__ import annotations

import typing

from pydantic import AnyHttpUrl, field_validator, AnyUrl
from pydantic_settings import BaseSettings as PydanticBaseSettings, SettingsConfigDict


class BaseSettings(PydanticBaseSettings):
    PROJECT_NAME: str
    BACKEND_CORS_ORIGINS: list[typing.Any]
    INSTALLED_APPS: list[str]
    DB_URL: str
    DB_USER: str
    DB_PASSWORD: str
    DB_DATABASE_NAME: str

    INTERFACE_LANGUAGES: list[str]
    DEFAULT_INTERFACE_LANGUAGE: str = "en"

    authjwt_secret_key: str

    INTERFACE_LANGUAGES: list[str]

    @field_validator("BACKEND_CORS_ORIGINS")
    def assemble_cors_origins(
        cls, v: typing.Union[str, list[str]]
    ) -> typing.Union[list[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

    def __init__(self, *args, **kwargs):
        # When initialising settings, copy it to this global var for access
        # within pangloss_core
        global SETTINGS

        SETTINGS = self
        super().__init__(*args, **kwargs)


SETTINGS: BaseSettings
