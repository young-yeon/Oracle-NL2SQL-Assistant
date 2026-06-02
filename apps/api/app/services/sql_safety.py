from __future__ import annotations

import re

import sqlglot
from pydantic import BaseModel, Field
from sqlglot import exp

from app.services.metadata import MetadataCatalog, normalize_identifier


class SqlValidationResult(BaseModel):
    is_safe: bool
    safe_sql: str | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)


class SqlSafetyValidator:
    DISALLOWED_PATTERN = re.compile(
        r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|commit|rollback|execute|exec|call|begin|declare)\b",
        re.IGNORECASE,
    )

    def __init__(self, max_rows: int):
        self.max_rows = max_rows

    def validate(self, sql: str, catalog: MetadataCatalog | None) -> SqlValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        raw_sql = sql.strip()

        if not raw_sql:
            return SqlValidationResult(is_safe=False, errors=["SQL is empty."])

        if "--" in raw_sql or "/*" in raw_sql or "*/" in raw_sql:
            errors.append("SQL comments are not allowed.")

        if self.DISALLOWED_PATTERN.search(raw_sql):
            errors.append("Only read-only SELECT/WITH statements are allowed.")

        normalized_sql = raw_sql.rstrip(";").strip()
        if ";" in normalized_sql:
            errors.append("Multiple SQL statements are not allowed.")

        try:
            parsed_statements = sqlglot.parse(normalized_sql, read="oracle")
        except sqlglot.errors.ParseError as exc:
            return SqlValidationResult(is_safe=False, errors=[*errors, f"SQL parse failed: {exc}"])

        if len(parsed_statements) != 1:
            errors.append("Exactly one SQL statement is allowed.")

        parsed = parsed_statements[0] if parsed_statements else None
        if parsed is None:
            errors.append("SQL parse returned no statement.")
        elif not isinstance(parsed, (exp.Select, exp.Union)):
            errors.append("The root SQL statement must be SELECT or WITH SELECT.")

        tables = self._extract_tables(parsed) if parsed is not None else []
        if catalog and catalog.tables:
            allowlist = catalog.table_allowlist()
            for table in tables:
                table_key = normalize_identifier(table)
                short_key = table_key.split(".")[-1]
                if table_key not in allowlist and short_key not in allowlist:
                    errors.append(f"Table '{table}' is not present in the metadata allowlist.")
        elif not catalog:
            warnings.append("No metadata catalog was supplied for table allowlist validation.")

        if re.search(r"\bfor\s+update\b", normalized_sql, flags=re.IGNORECASE):
            errors.append("SELECT FOR UPDATE is not allowed.")

        if errors:
            return SqlValidationResult(is_safe=False, errors=errors, warnings=warnings, tables=tables)

        return SqlValidationResult(
            is_safe=True,
            safe_sql=self._apply_row_limit(normalized_sql),
            errors=[],
            warnings=warnings,
            tables=tables,
        )

    def _extract_tables(self, parsed: exp.Expression | None) -> list[str]:
        if parsed is None:
            return []
        tables: list[str] = []
        for table in parsed.find_all(exp.Table):
            table_name = table.name
            db = table.args.get("db")
            if db:
                table_name = f"{db}.{table_name}"
            tables.append(table_name)
        return sorted(set(tables))

    def _apply_row_limit(self, sql: str) -> str:
        if re.search(r"\b(fetch\s+first|rownum)\b", sql, flags=re.IGNORECASE):
            return sql
        return f"SELECT * FROM (\n{sql}\n) WHERE ROWNUM <= {self.max_rows}"

