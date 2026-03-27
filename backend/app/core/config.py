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
    refresh_token_expire_days: int = 14
    password_reset_token_expire_minutes: int = 15
    expose_password_reset_token: bool = True
    supported_languages_csv: str = "en,ru,ky"
    media_root: str = "storage"
    message_attachments_subdir: str = "message_attachments"
    message_attachment_max_size_mb: int = 10
    message_attachment_max_files_per_message: int = 5
    message_attachment_allowed_mime_csv: str = "image/jpeg,image/png,image/webp,application/pdf"
    listing_media_subdir: str = "listing_media"
    listing_media_max_size_mb: int = 10
    listing_media_max_files_per_listing: int = 20
    listing_media_allowed_mime_csv: str = "image/jpeg,image/png,image/webp"

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

    @property
    def message_attachment_allowed_mime_types(self) -> list[str]:
        return [
            mime_type.strip().lower()
            for mime_type in self.message_attachment_allowed_mime_csv.split(",")
            if mime_type.strip()
        ]

    @property
    def listing_media_allowed_mime_types(self) -> list[str]:
        return [
            mime_type.strip().lower()
            for mime_type in self.listing_media_allowed_mime_csv.split(",")
            if mime_type.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
