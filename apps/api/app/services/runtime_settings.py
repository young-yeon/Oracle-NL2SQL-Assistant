from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings


class RuntimeSettingsStore:
    def __init__(self, storage_dir: Path):
        self.path = storage_dir / "runtime_settings.json"

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def apply(self, settings: Settings) -> None:
        oracle = self.load().get("oracle")
        if isinstance(oracle, dict):
            apply_oracle_values(settings, oracle)

    def save_oracle(self, settings: Settings) -> None:
        payload = self.load()
        payload["oracle"] = oracle_values_from_settings(settings)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(temp_path, 0o600)
        except OSError:
            pass
        temp_path.replace(self.path)


def oracle_values_from_settings(settings: Settings) -> dict[str, Any]:
    return {
        "dsn": settings.oracle_dsn,
        "user": settings.oracle_user,
        "password": settings.oracle_password,
        "current_schema": settings.oracle_current_schema,
        "mode": settings.oracle_mode,
        "client_lib_dir": settings.oracle_client_lib_dir,
        "sql_max_rows": settings.sql_max_rows,
        "sql_timeout_seconds": settings.sql_timeout_seconds,
    }


def apply_oracle_values(settings: Settings, values: dict[str, Any]) -> None:
    if "dsn" in values:
        settings.oracle_dsn = _clean_optional(values.get("dsn"))
    if "user" in values:
        settings.oracle_user = _clean_optional(values.get("user"))
    if "password" in values:
        settings.oracle_password = _clean_optional(values.get("password"))
    if "current_schema" in values:
        settings.oracle_current_schema = _clean_optional(values.get("current_schema"))
    if "mode" in values:
        mode = str(values.get("mode") or "thin").strip().lower()
        settings.oracle_mode = mode if mode in {"thin", "thick"} else "thin"
    if "client_lib_dir" in values:
        settings.oracle_client_lib_dir = _clean_optional(values.get("client_lib_dir"))
    if "sql_max_rows" in values:
        settings.sql_max_rows = int(values.get("sql_max_rows") or settings.sql_max_rows)
    if "sql_timeout_seconds" in values:
        settings.sql_timeout_seconds = int(values.get("sql_timeout_seconds") or settings.sql_timeout_seconds)


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
