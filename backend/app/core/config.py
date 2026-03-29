from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
    supported_languages_csv: str = "en,ru"
    media_root: str = "storage"
    message_attachments_subdir: str = "message_attachments"
    message_attachment_max_size_mb: int = 10
    message_attachment_max_files_per_message: int = 5
    message_attachment_allowed_mime_csv: str = "image/jpeg,image/png,image/webp,application/pdf"
    report_attachments_subdir: str = "report_attachments"
    report_attachment_max_size_mb: int = 10
    report_attachment_max_files_per_report: int = 5
    report_attachment_allowed_mime_csv: str = "image/jpeg,image/png,image/webp,application/pdf,text/plain"
    verification_documents_subdir: str = "verification_documents"
    verification_document_max_size_mb: int = 10
    verification_document_max_files_per_request: int = 5
    verification_document_allowed_mime_csv: str = "image/jpeg,image/png,image/webp,application/pdf"
    listing_media_subdir: str = "listing_media"
    listing_media_max_size_mb: int = 10
    listing_media_max_files_per_listing: int = 20
    listing_media_allowed_mime_csv: str = "image/jpeg,image/png,image/webp"
    cors_allowed_origins_csv: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"
    cors_allowed_methods_csv: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    cors_allowed_headers_csv: str = "*"
    cors_allow_credentials: bool = True
    trusted_hosts_csv: str = "localhost,127.0.0.1,testserver"
    gzip_minimum_size: int = 500
    enable_rate_limit: bool = True
    auth_rate_limit_requests: int = 20
    auth_rate_limit_window_seconds: int = 60
    sensitive_rate_limit_requests: int = 60
    sensitive_rate_limit_window_seconds: int = 60

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
        return self._split_csv(self.supported_languages_csv)

    @property
    def cors_allowed_origins(self) -> list[str]:
        return self._split_csv(self.cors_allowed_origins_csv)

    @property
    def cors_allowed_methods(self) -> list[str]:
        return self._split_csv(self.cors_allowed_methods_csv)

    @property
    def cors_allowed_headers(self) -> list[str]:
        return self._split_csv(self.cors_allowed_headers_csv)

    @property
    def trusted_hosts(self) -> list[str]:
        hosts = self._split_csv(self.trusted_hosts_csv)
        return hosts or ["*"]

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

    @property
    def report_attachment_allowed_mime_types(self) -> list[str]:
        return [
            mime_type.strip().lower()
            for mime_type in self.report_attachment_allowed_mime_csv.split(",")
            if mime_type.strip()
        ]

    @property
    def verification_document_allowed_mime_types(self) -> list[str]:
        return [
            mime_type.strip().lower()
            for mime_type in self.verification_document_allowed_mime_csv.split(",")
            if mime_type.strip()
        ]

    @staticmethod
    def _split_csv(raw_value: str) -> list[str]:
        return [item.strip() for item in raw_value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
