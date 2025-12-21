from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # `.env.prod` имеет приоритет над `.env`
        env_file=(".env", ".env.prod")
    )

    api_key: str


settings = Settings()
