from pydantic import BaseSettings
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "PowerE API"
    ALLOW_ORIGINS: List[str] = ["*"]
    DEFAULT_TZ: str = "Europe/Zurich"
    API_PREFIX: str = "/v1"

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()