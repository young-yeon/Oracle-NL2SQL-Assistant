from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field


def normalize_identifier(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9_.]", "", str(value).strip().lower())


def split_aliases(value: Any) -> list[str]:
    if value is None or pd.isna(value):
        return []
    parts = re.split(r"[,;|]", str(value))
    return [part.strip() for part in parts if part and part.strip()]


def clean_value(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


class TableDefinition(BaseModel):
    name: str
    schema_name: str | None = None
    display_name: str = ""
    description: str = ""
    synonyms: list[str] = Field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        return f"{self.schema_name}.{self.name}" if self.schema_name else self.name


class ColumnDefinition(BaseModel):
    table: str
    name: str
    data_type: str = ""
    display_name: str = ""
    description: str = ""
    synonyms: list[str] = Field(default_factory=list)
    semantic_type: str = ""
    nullable: str = ""


class RelationshipDefinition(BaseModel):
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    join_type: str = "inner"
    description: str = ""


class TermDefinition(BaseModel):
    term: str
    canonical_type: str = "concept"
    canonical_value: str = ""
    synonyms: list[str] = Field(default_factory=list)
    description: str = ""


class MetricDefinition(BaseModel):
    name: str
    expression: str
    table: str = ""
    grain: str = ""
    synonyms: list[str] = Field(default_factory=list)
    description: str = ""


class MetadataCatalog(BaseModel):
    version: str
    created_at: str
    source_filename: str = ""
    tables: list[TableDefinition] = Field(default_factory=list)
    columns: list[ColumnDefinition] = Field(default_factory=list)
    relationships: list[RelationshipDefinition] = Field(default_factory=list)
    terms: list[TermDefinition] = Field(default_factory=list)
    metrics: list[MetricDefinition] = Field(default_factory=list)

    def table_allowlist(self) -> set[str]:
        allowed: set[str] = set()
        for table in self.tables:
            allowed.add(normalize_identifier(table.name))
            allowed.add(normalize_identifier(table.qualified_name))
        return {item for item in allowed if item}

    def get_table(self, name: str) -> TableDefinition | None:
        key = normalize_identifier(name)
        for table in self.tables:
            if key in {normalize_identifier(table.name), normalize_identifier(table.qualified_name)}:
                return table
        return None

    def columns_for_table(self, table_name: str) -> list[ColumnDefinition]:
        key = normalize_identifier(table_name).split(".")[-1]
        return [col for col in self.columns if normalize_identifier(col.table).split(".")[-1] == key]

    def to_prompt(self, max_tables: int = 20, max_columns: int = 160) -> str:
        lines = ["Catalog:"]
        for table in self.tables[:max_tables]:
            lines.append(
                f"- table={table.qualified_name}; display={table.display_name}; description={table.description}"
            )
            for column in self.columns_for_table(table.name)[:max_columns]:
                details = ", ".join(
                    item
                    for item in [
                        f"type={column.data_type}" if column.data_type else "",
                        f"display={column.display_name}" if column.display_name else "",
                        f"semantic={column.semantic_type}" if column.semantic_type else "",
                        f"description={column.description}" if column.description else "",
                    ]
                    if item
                )
                lines.append(f"  - column={column.name}; {details}")
        if self.metrics:
            lines.append("Metrics:")
            for metric in self.metrics[:80]:
                lines.append(
                    f"- metric={metric.name}; expression={metric.expression}; table={metric.table}; grain={metric.grain}; description={metric.description}"
                )
        if self.relationships:
            lines.append("Relationships:")
            for rel in self.relationships[:80]:
                lines.append(
                    f"- {rel.left_table}.{rel.left_column} {rel.join_type} join {rel.right_table}.{rel.right_column}; {rel.description}"
                )
        return "\n".join(lines)

    def summary(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "tables": [table.model_dump() | {"qualified_name": table.qualified_name} for table in self.tables],
            "columns": [column.model_dump() for column in self.columns],
            "relationships": [rel.model_dump() for rel in self.relationships],
            "terms": [term.model_dump() for term in self.terms],
            "metrics": [metric.model_dump() for metric in self.metrics],
        }


class ImportResult(BaseModel):
    catalog: MetadataCatalog
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class MetadataImporter:
    SHEETS = ("tables", "columns", "relationships", "terms", "metrics")
    COMMON_HEADER_ALIASES: dict[str, set[str]] = {
        "schema": {"schema", "owner", "schemaname"},
        "display_name": {"displayname", "display", "businessname", "label"},
        "description": {"description", "desc", "comment", "comments", "definition"},
        "synonyms": {"synonyms", "aliases", "alias", "terms"},
        "data_type": {"datatype", "type", "columntype", "data_type"},
        "semantic_type": {"semantictype", "semantic", "role"},
        "nullable": {"nullable", "null", "isnullable"},
        "left_table": {"lefttable", "fromtable", "sourcetable"},
        "left_column": {"leftcolumn", "fromcolumn", "sourcecolumn"},
        "right_table": {"righttable", "totable", "targettable"},
        "right_column": {"rightcolumn", "tocolumn", "targetcolumn"},
        "join_type": {"jointype", "join", "type"},
        "term": {"term", "phrase", "word"},
        "canonical_type": {"canonicaltype", "targettype", "type"},
        "canonical_value": {"canonicalvalue", "target", "targetvalue", "value"},
        "expression": {"expression", "sqlexpression", "formula"},
        "grain": {"grain", "level"},
    }

    def from_excel(self, content: bytes, filename: str = "") -> ImportResult:
        warnings: list[str] = []
        errors: list[str] = []
        excel = pd.ExcelFile(BytesIO(content))
        frames: dict[str, pd.DataFrame] = {}

        for sheet_name in self.SHEETS:
            actual = self._find_sheet(excel.sheet_names, sheet_name)
            if actual is None:
                warnings.append(f"Missing sheet '{sheet_name}'.")
                frames[sheet_name] = pd.DataFrame()
                continue
            frames[sheet_name] = self._canonicalize_headers(pd.read_excel(excel, sheet_name=actual), sheet_name)

        version = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        catalog = MetadataCatalog(version=version, created_at=datetime.now(UTC).isoformat(), source_filename=filename)

        catalog.tables = self._parse_tables(frames["tables"], warnings, errors)
        catalog.columns = self._parse_columns(frames["columns"], warnings, errors)
        catalog.relationships = self._parse_relationships(frames["relationships"], warnings)
        catalog.terms = self._parse_terms(frames["terms"], warnings)
        catalog.metrics = self._parse_metrics(frames["metrics"], warnings, errors)

        if not catalog.tables:
            errors.append("No valid tables were imported.")
        if not catalog.columns:
            warnings.append("No valid columns were imported. SQL generation quality will be limited.")

        return ImportResult(catalog=catalog, warnings=warnings, errors=errors)

    def _find_sheet(self, sheet_names: list[str], target: str) -> str | None:
        normalized = {normalize_identifier(name): name for name in sheet_names}
        return normalized.get(target)

    def _canonicalize_headers(self, frame: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
        renamed: dict[str, str] = {}
        aliases_by_name = self._aliases_for_sheet(sheet_name)
        for column in frame.columns:
            raw = str(column)
            key = normalize_identifier(raw).replace("_", "")
            for canonical, aliases in aliases_by_name.items():
                if key in {normalize_identifier(alias).replace("_", "") for alias in aliases}:
                    renamed[raw] = canonical
                    break
        frame = frame.rename(columns=renamed)
        return frame.where(pd.notnull(frame), None)

    def _aliases_for_sheet(self, sheet_name: str) -> dict[str, set[str]]:
        aliases = dict(self.COMMON_HEADER_ALIASES)
        if sheet_name == "tables":
            aliases["name"] = {"name", "tablename", "table", "table_name"}
        elif sheet_name == "columns":
            aliases["table"] = {"table", "tablename", "table_name"}
            aliases["name"] = {"name", "columnname", "column", "column_name"}
        elif sheet_name == "metrics":
            aliases["name"] = {"name", "metric", "metricname", "metric_name"}
            aliases["table"] = {"table", "tablename", "table_name"}
        elif sheet_name == "terms":
            aliases["term"] = {"term", "phrase", "word", "name"}
        return aliases

    def _parse_tables(
        self, frame: pd.DataFrame, warnings: list[str], errors: list[str]
    ) -> list[TableDefinition]:
        rows: list[TableDefinition] = []
        for idx, row in frame.iterrows():
            name = clean_value(row.get("name") or row.get("table"))
            if not name:
                warnings.append(f"tables row {idx + 2}: missing table name.")
                continue
            rows.append(
                TableDefinition(
                    name=name,
                    schema_name=clean_value(row.get("schema")) or None,
                    display_name=clean_value(row.get("display_name")),
                    description=clean_value(row.get("description")),
                    synonyms=split_aliases(row.get("synonyms")),
                )
            )
        return rows

    def _parse_columns(
        self, frame: pd.DataFrame, warnings: list[str], errors: list[str]
    ) -> list[ColumnDefinition]:
        rows: list[ColumnDefinition] = []
        for idx, row in frame.iterrows():
            table = clean_value(row.get("table"))
            name = clean_value(row.get("name") or row.get("column"))
            if not table or not name:
                warnings.append(f"columns row {idx + 2}: missing table or column name.")
                continue
            rows.append(
                ColumnDefinition(
                    table=table,
                    name=name,
                    data_type=clean_value(row.get("data_type")),
                    display_name=clean_value(row.get("display_name")),
                    description=clean_value(row.get("description")),
                    synonyms=split_aliases(row.get("synonyms")),
                    semantic_type=clean_value(row.get("semantic_type")),
                    nullable=clean_value(row.get("nullable")),
                )
            )
        return rows

    def _parse_relationships(self, frame: pd.DataFrame, warnings: list[str]) -> list[RelationshipDefinition]:
        rows: list[RelationshipDefinition] = []
        for idx, row in frame.iterrows():
            values = {key: clean_value(row.get(key)) for key in ["left_table", "left_column", "right_table", "right_column"]}
            if not all(values.values()):
                if any(values.values()):
                    warnings.append(f"relationships row {idx + 2}: incomplete relationship skipped.")
                continue
            rows.append(
                RelationshipDefinition(
                    **values,
                    join_type=clean_value(row.get("join_type")) or "inner",
                    description=clean_value(row.get("description")),
                )
            )
        return rows

    def _parse_terms(self, frame: pd.DataFrame, warnings: list[str]) -> list[TermDefinition]:
        rows: list[TermDefinition] = []
        for idx, row in frame.iterrows():
            term = clean_value(row.get("term") or row.get("name"))
            if not term:
                if any(clean_value(value) for value in row.to_dict().values()):
                    warnings.append(f"terms row {idx + 2}: missing term.")
                continue
            rows.append(
                TermDefinition(
                    term=term,
                    canonical_type=clean_value(row.get("canonical_type")) or "concept",
                    canonical_value=clean_value(row.get("canonical_value")),
                    synonyms=split_aliases(row.get("synonyms")),
                    description=clean_value(row.get("description")),
                )
            )
        return rows

    def _parse_metrics(
        self, frame: pd.DataFrame, warnings: list[str], errors: list[str]
    ) -> list[MetricDefinition]:
        rows: list[MetricDefinition] = []
        for idx, row in frame.iterrows():
            name = clean_value(row.get("name") or row.get("term"))
            expression = clean_value(row.get("expression"))
            if not name and not expression:
                continue
            if not name or not expression:
                warnings.append(f"metrics row {idx + 2}: missing name or expression.")
                continue
            rows.append(
                MetricDefinition(
                    name=name,
                    expression=expression,
                    table=clean_value(row.get("table")),
                    grain=clean_value(row.get("grain")),
                    synonyms=split_aliases(row.get("synonyms")),
                    description=clean_value(row.get("description")),
                )
            )
        return rows


class CatalogStore:
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.catalog_dir = storage_dir / "catalogs"
        self.current_file = storage_dir / "current_catalog.json"
        self.catalog_dir.mkdir(parents=True, exist_ok=True)

    def save(self, catalog: MetadataCatalog) -> None:
        target = self.catalog_dir / f"{catalog.version}.json"
        target.write_text(catalog.model_dump_json(indent=2), encoding="utf-8")
        self.current_file.write_text(json.dumps({"version": catalog.version}), encoding="utf-8")

    def load(self, version: str | None = None) -> MetadataCatalog | None:
        resolved_version = version or self.current_version()
        if not resolved_version:
            return None
        target = self.catalog_dir / f"{resolved_version}.json"
        if not target.exists():
            return None
        return MetadataCatalog.model_validate_json(target.read_text(encoding="utf-8"))

    def current_version(self) -> str | None:
        if not self.current_file.exists():
            return None
        try:
            payload = json.loads(self.current_file.read_text(encoding="utf-8"))
            return payload.get("version")
        except json.JSONDecodeError:
            return None
