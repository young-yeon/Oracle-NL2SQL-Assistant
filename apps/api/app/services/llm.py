from __future__ import annotations

import json
import re
from typing import Any

from app.config import Settings
from app.services.metadata import MetadataCatalog


class LLMService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def semantic_analysis(
        self, message: str, catalog: MetadataCatalog, matches: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if not self.settings.llm_configured:
            return {
                "intent": "data_query",
                "entities": matches,
                "filters": [],
                "plan": [
                    "Interpret the user question.",
                    "Resolve metadata and synonyms.",
                    "Generate read-only Oracle SQL.",
                    "Validate SQL before execution.",
                ],
                "warnings": ["LLM is not configured; using deterministic development analysis."],
            }

        prompt = {
            "question": message,
            "metadata_matches": matches,
            "catalog": catalog.to_prompt(),
        }
        content = await self._chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "You analyze natural-language business data questions for an Oracle NL2SQL system. "
                        "Return JSON only with keys: intent, entities, filters, measures, dimensions, plan, warnings."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ]
        )
        return content or {"intent": "data_query", "entities": matches, "filters": [], "plan": [], "warnings": []}

    async def generate_sql(
        self,
        message: str,
        catalog: MetadataCatalog,
        matches: list[dict[str, Any]],
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.settings.llm_configured:
            return self._fallback_sql(catalog, matches)

        prompt = {
            "question": message,
            "analysis": analysis,
            "metadata_matches": matches,
            "catalog": catalog.to_prompt(),
            "oracle_sql_version": self.settings.oracle_sql_version,
            "rules": [
                "Return Oracle SQL only in the sql field.",
                f"Target Oracle Database version is {self.settings.oracle_sql_version}.",
                "Use only tables and columns present in the catalog.",
                "Use SELECT or WITH SELECT only.",
                "Do not include semicolons, comments, DDL, DML, PL/SQL, or SELECT FOR UPDATE.",
                "For Oracle 11g compatibility, do not use FETCH FIRST, OFFSET/FETCH, or LIMIT.",
                "For row limiting, use ROWNUM in a subquery when needed.",
                "Prefer explicit column names over SELECT *.",
            ],
        }
        content = await self._chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "You generate safe read-only Oracle SQL from business metadata. "
                        f"Use Oracle Database {self.settings.oracle_sql_version} compatible syntax. "
                        "Return JSON only with keys: sql, explanation, warnings."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ]
        )
        if content and content.get("sql"):
            return {
                "sql": str(content.get("sql")),
                "explanation": str(content.get("explanation", "")),
                "warnings": list(content.get("warnings") or []),
            }
        fallback = self._fallback_sql(catalog, matches)
        fallback["warnings"].append("LLM did not return usable SQL; fallback SQL was generated.")
        return fallback

    async def synthesize_answer(
        self,
        message: str,
        sql: str,
        columns: list[str],
        rows: list[dict[str, Any]],
        warnings: list[str],
    ) -> str:
        if not rows:
            return "The query ran successfully, but it returned no rows."

        if not self.settings.llm_configured:
            return f"The query returned {len(rows)} row(s). Preview columns: {', '.join(columns)}."

        prompt = {
            "question": message,
            "sql": sql,
            "columns": columns,
            "rows_preview": rows[:50],
            "warnings": warnings,
        }
        content = await self._chat_text(
            [
                {
                    "role": "system",
                    "content": (
                        "You summarize Oracle query results for a business user. "
                        "Be concise, mention important caveats, and do not invent values."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, default=str)},
            ]
        )
        return content or f"The query returned {len(rows)} row(s)."

    async def _chat_json(self, messages: list[dict[str, str]]) -> dict[str, Any] | None:
        text = await self._chat_text(messages)
        if not text:
            return None
        return self._extract_json(text)

    async def _chat_text(self, messages: list[dict[str, str]]) -> str | None:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.settings.llm_api_key, base_url=self.settings.llm_base_url)
            response = await client.chat.completions.create(
                model=self.settings.llm_model or "",
                messages=messages,
                temperature=0,
            )
            return response.choices[0].message.content
        except Exception:
            return None

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

    def _fallback_sql(self, catalog: MetadataCatalog, matches: list[dict[str, Any]]) -> dict[str, Any]:
        metric_match = next(
            (match for match in matches if match.get("type") == "metric" and match.get("expression")),
            None,
        )
        if metric_match is None:
            metric_ref = next((match.get("target") for match in matches if match.get("type") == "metric"), None)
            metric_match = self._find_metric_match(catalog, str(metric_ref)) if metric_ref else None
        if metric_match and metric_match.get("expression"):
            table = self._qualified_table_name(
                catalog,
                str(metric_match.get("table") or ""),
            ) or (catalog.tables[0].qualified_name if catalog.tables else "")
            if table:
                return {
                    "sql": f"SELECT {metric_match['expression']} AS {metric_match['target']} FROM {table}",
                    "explanation": "Fallback metric query generated from metadata.",
                    "warnings": ["LLM is not configured; using deterministic fallback SQL."],
                }

        table = self._choose_table(catalog, matches)
        if not table:
            return {"sql": "", "explanation": "", "warnings": ["No table metadata is available."]}

        columns = catalog.columns_for_table(table.name)[:5]
        select_list = ", ".join(column.name for column in columns) if columns else "*"
        return {
            "sql": f"SELECT {select_list} FROM {table.qualified_name}",
            "explanation": "Fallback table preview query generated from metadata.",
            "warnings": ["LLM is not configured; using deterministic fallback SQL."],
        }

    def _choose_table(self, catalog: MetadataCatalog, matches: list[dict[str, Any]]):
        table_match = next((match for match in matches if match.get("type") == "table"), None)
        if table_match:
            table = catalog.get_table(str(table_match.get("target")))
            if table:
                return table
        return catalog.tables[0] if catalog.tables else None

    def _find_metric_match(self, catalog: MetadataCatalog, metric_name: str) -> dict[str, Any] | None:
        normalized = metric_name.strip().lower()
        for metric in catalog.metrics:
            if metric.name.lower() == normalized:
                return {
                    "type": "metric",
                    "target": metric.name,
                    "expression": metric.expression,
                    "table": metric.table,
                    "description": metric.description,
                }
        return None

    def _qualified_table_name(self, catalog: MetadataCatalog, table_name: str) -> str:
        if not table_name:
            return ""
        table = catalog.get_table(table_name)
        return table.qualified_name if table else table_name
