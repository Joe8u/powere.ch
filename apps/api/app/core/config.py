from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    APP_NAME: str = "PowerE API"
    ALLOW_ORIGINS: List[str] = ["*"]
    DEFAULT_TZ: str = "Europe/Zurich"
    API_PREFIX: str = "/v1"

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()
