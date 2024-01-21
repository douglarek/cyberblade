from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict()

    discord_bot_token: str

    jinrishici_token: Optional[str] = None
    jinrishici_api_endpoint: str = "https://v2.jinrishici.com"

    database_url: str = "sqlite+aiosqlite:///cyberblade.db"  # here an async database url must be used


settings = Settings()  # type: ignore
