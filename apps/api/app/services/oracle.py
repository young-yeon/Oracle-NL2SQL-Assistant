from __future__ import annotations

import asyncio
import re
from typing import Any

from app.config import Settings


class OracleClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._thick_initialized = False

    @property
    def configured(self) -> bool:
        return self.settings.oracle_configured

    def reset(self) -> None:
        self._thick_initialized = False

    async def healthcheck(self) -> bool | None:
        if not self.configured:
            return None
        try:
            await self.execute("SELECT 1 AS OK FROM DUAL", max_rows=1)
            return True
        except Exception:
            return False

    async def execute(self, sql: str, max_rows: int | None = None) -> tuple[list[str], list[dict[str, Any]]]:
        if not self.configured:
            raise RuntimeError("Oracle connection is not configured.")
        return await asyncio.to_thread(self._execute_sync, sql, max_rows or self.settings.sql_max_rows)

    def _execute_sync(self, sql: str, max_rows: int) -> tuple[list[str], list[dict[str, Any]]]:
        import oracledb

        if self.settings.oracle_mode.lower() == "thick" and not self._thick_initialized:
            kwargs = {}
            if self.settings.oracle_client_lib_dir:
                kwargs["lib_dir"] = self.settings.oracle_client_lib_dir
            oracledb.init_oracle_client(**kwargs)
            self._thick_initialized = True

        with oracledb.connect(
            user=self.settings.oracle_user,
            password=self.settings.oracle_password,
            dsn=self.settings.oracle_dsn,
        ) as connection:
            if self.settings.oracle_current_schema:
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_$#]*", self.settings.oracle_current_schema):
                    raise ValueError("ORACLE_CURRENT_SCHEMA must be a valid Oracle identifier.")
                with connection.cursor() as schema_cursor:
                    schema_cursor.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {self.settings.oracle_current_schema}")
            connection.call_timeout = self.settings.sql_timeout_seconds * 1000
            with connection.cursor() as cursor:
                cursor.execute(sql)
                columns = [item[0] for item in cursor.description or []]
                rows = cursor.fetchmany(max_rows)
                payload = [dict(zip(columns, row, strict=False)) for row in rows]
                return columns, payload
