from typing import Any, Literal

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    name: str
    status: str = "pending"
    detail: str | None = None


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1)
    metadata_version: str | None = None


class SqlPreviewRequest(BaseModel):
    message: str = Field(min_length=1)
    metadata_version: str | None = None


class SqlExecuteRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1)
    sql: str = Field(min_length=1)
    metadata_version: str | None = None


class SqlValidationPayload(BaseModel):
    is_safe: bool
    errors: list[str] = []
    warnings: list[str] = []
    tables: list[str] = []


class ChatResponse(BaseModel):
    answer: str
    plan: list[PlanStep]
    sql: str | None = None
    rows_preview: list[dict[str, Any]] = []
    columns: list[str] = []
    warnings: list[str] = []
    metadata_version: str | None = None
    validation: SqlValidationPayload | None = None
    requires_execution_approval: bool = False
    executed: bool = False


class UploadResponse(BaseModel):
    version: str
    tables: int
    columns: int
    relationships: int
    terms: int
    metrics: int
    warnings: list[str] = []
    errors: list[str] = []


class CatalogResponse(BaseModel):
    version: str | None = None
    tables: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    terms: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    warnings: list[str] = []


class HealthResponse(BaseModel):
    status: str
    llm_configured: bool
    nemo_guardrails_enabled: bool
    nemo_guardrails_ready: bool
    oracle_configured: bool
    oracle_reachable: bool | None
    metadata_loaded: bool
    metadata_version: str | None


class OracleSettingsResponse(BaseModel):
    dsn: str | None = None
    user: str | None = None
    password_set: bool = False
    current_schema: str | None = None
    mode: Literal["thin", "thick"] = "thin"
    client_lib_dir: str | None = None
    sql_max_rows: int
    sql_timeout_seconds: int
    configured: bool


class OracleSettingsPayload(BaseModel):
    dsn: str | None = None
    user: str | None = None
    password: str | None = None
    clear_password: bool = False
    current_schema: str | None = None
    mode: Literal["thin", "thick"] = "thin"
    client_lib_dir: str | None = None
    sql_max_rows: int = Field(default=100, ge=1, le=5000)
    sql_timeout_seconds: int = Field(default=30, ge=1, le=600)


class OracleConnectionTestResponse(BaseModel):
    configured: bool
    reachable: bool | None
    message: str
