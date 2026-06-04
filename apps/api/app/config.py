from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    storage_dir: Path = Field(default=Path("storage"), alias="STORAGE_DIR")
    web_dist_dir: Path | None = Field(default=None, alias="WEB_DIST_DIR")
    admin_setup_token: str | None = Field(default=None, alias="ADMIN_SETUP_TOKEN")

    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_model: str | None = Field(default=None, alias="LLM_MODEL")

    embedding_base_url: str | None = Field(default=None, alias="EMBEDDING_BASE_URL")
    embedding_api_key: str | None = Field(default=None, alias="EMBEDDING_API_KEY")
    embedding_model: str | None = Field(default=None, alias="EMBEDDING_MODEL")

    nemo_guardrails_enabled: bool = Field(default=True, alias="NEMO_GUARDRAILS_ENABLED")
    nemo_config_path: Path = Field(default=Path("configs/guardrails"), alias="NEMO_CONFIG_PATH")

    oracle_dsn: str | None = Field(default=None, alias="ORACLE_DSN")
    oracle_user: str | None = Field(default=None, alias="ORACLE_USER")
    oracle_password: str | None = Field(default=None, alias="ORACLE_PASSWORD")
    oracle_current_schema: str | None = Field(default=None, alias="ORACLE_CURRENT_SCHEMA")
    oracle_mode: str = Field(default="thin", alias="ORACLE_MODE")
    oracle_client_lib_dir: str | None = Field(default=None, alias="ORACLE_CLIENT_LIB_DIR")
    oracle_sql_version: str = Field(default="11g", alias="ORACLE_SQL_VERSION")

    sql_max_rows: int = Field(default=100, ge=1, le=5000, alias="SQL_MAX_ROWS")
    sql_timeout_seconds: int = Field(default=30, ge=1, le=600, alias="SQL_TIMEOUT_SECONDS")
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
    )

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)

    @property
    def embedding_configured(self) -> bool:
        return bool(self.embedding_base_url and self.embedding_api_key and self.embedding_model)

    @property
    def oracle_configured(self) -> bool:
        return bool(self.oracle_dsn and self.oracle_user and self.oracle_password)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
