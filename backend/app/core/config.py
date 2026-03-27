from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Real Estate Marketplace API"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    supported_languages_csv: str = "en,ru,ky"

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str = "realestate_demo"
    db_user: str = "root"
    db_password: str = "root"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def supported_languages(self) -> list[str]:
        return [lang.strip() for lang in self.supported_languages_csv.split(",") if lang.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
