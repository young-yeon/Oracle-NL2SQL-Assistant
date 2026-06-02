from __future__ import annotations

from typing import Any

from app.config import Settings
from app.schemas import ChatResponse, PlanStep, SqlValidationPayload
from app.services.audit import AuditLogger
from app.services.guardrails import GuardrailsService
from app.services.llm import LLMService
from app.services.metadata import CatalogStore
from app.services.oracle import OracleClient
from app.services.sql_safety import SqlSafetyValidator
from app.services.synonyms import SynonymResolver


class QueryPipeline:
    def __init__(
        self,
        settings: Settings,
        catalog_store: CatalogStore,
        guardrails: GuardrailsService,
        llm: LLMService,
        oracle: OracleClient,
        audit: AuditLogger,
    ):
        self.settings = settings
        self.catalog_store = catalog_store
        self.guardrails = guardrails
        self.llm = llm
        self.oracle = oracle
        self.audit = audit
        self.synonyms = SynonymResolver()
        self.validator = SqlSafetyValidator(max_rows=settings.sql_max_rows)

    def refresh_settings(self) -> None:
        self.validator = SqlSafetyValidator(max_rows=self.settings.sql_max_rows)

    async def preview(self, message: str, metadata_version: str | None = None) -> ChatResponse:
        plan: list[PlanStep] = []
        warnings: list[str] = []

        guard = await self.guardrails.check_input(message)
        plan.append(PlanStep(name="input_guardrail", status="complete", detail=guard.reason))
        if not guard.allowed:
            return ChatResponse(
                answer="I can only help with read-only Oracle data questions.",
                plan=plan,
                warnings=[guard.reason],
                metadata_version=metadata_version or self.catalog_store.current_version(),
            )

        catalog = self.catalog_store.load(metadata_version)
        if catalog is None:
            plan.append(PlanStep(name="metadata_resolution", status="blocked", detail="No metadata catalog loaded."))
            return ChatResponse(
                answer="Upload an Excel metadata workbook before asking data questions.",
                plan=plan,
                warnings=["No metadata catalog is loaded."],
                metadata_version=None,
            )

        matches = self.synonyms.resolve(message, catalog)
        plan.append(
            PlanStep(
                name="synonym_resolution",
                status="complete",
                detail=f"Resolved {len(matches)} metadata match(es).",
            )
        )

        analysis = await self.llm.semantic_analysis(message, catalog, matches)
        plan.append(
            PlanStep(
                name="semantic_analysis",
                status="complete",
                detail=str(analysis.get("intent", "data_query")),
            )
        )
        warnings.extend(str(item) for item in analysis.get("warnings", []) if item)

        sql_payload = await self.llm.generate_sql(message, catalog, matches, analysis)
        candidate_sql = str(sql_payload.get("sql") or "").strip()
        warnings.extend(str(item) for item in sql_payload.get("warnings", []) if item)
        plan.append(
            PlanStep(
                name="sql_generation",
                status="complete" if candidate_sql else "blocked",
                detail=str(sql_payload.get("explanation") or ""),
            )
        )

        if not candidate_sql:
            return ChatResponse(
                answer="I could not generate SQL from the available metadata.",
                plan=plan,
                warnings=warnings,
                metadata_version=catalog.version,
            )

        validation = self.validator.validate(candidate_sql, catalog)
        plan.append(
            PlanStep(
                name="sql_validation",
                status="complete" if validation.is_safe else "blocked",
                detail="; ".join(validation.errors or validation.warnings),
            )
        )

        return ChatResponse(
            answer="SQL preview is ready." if validation.is_safe else "Generated SQL did not pass safety validation.",
            plan=plan,
            sql=validation.safe_sql if validation.is_safe else candidate_sql,
            warnings=[*warnings, *validation.warnings, *validation.errors],
            metadata_version=catalog.version,
            validation=SqlValidationPayload(
                is_safe=validation.is_safe,
                errors=validation.errors,
                warnings=validation.warnings,
                tables=validation.tables,
            ),
        )

    async def chat(self, session_id: str | None, message: str, metadata_version: str | None = None) -> ChatResponse:
        response = await self.preview(message, metadata_version)
        if not response.sql or not response.validation or not response.validation.is_safe:
            self._audit(session_id, message, response)
            return response

        if not self.oracle.configured:
            response.answer = "SQL was generated and validated, but Oracle connection settings are not configured."
            response.warnings.append("Oracle connection is not configured.")
            self._audit(session_id, message, response)
            return response

        response.answer = "SQL was generated and validated. Review the query, then approve execution to run it."
        response.requires_execution_approval = True
        response.plan.append(PlanStep(name="user_execution_approval", status="pending", detail="Awaiting user approval."))
        self._audit(session_id, message, response)
        return response

    async def execute_approved_sql(
        self,
        session_id: str | None,
        message: str,
        sql: str,
        metadata_version: str | None = None,
    ) -> ChatResponse:
        plan: list[PlanStep] = [
            PlanStep(name="user_execution_approval", status="complete", detail="Approved by user.")
        ]
        catalog = self.catalog_store.load(metadata_version)
        if catalog is None:
            response = ChatResponse(
                answer="Upload an Excel metadata workbook before executing SQL.",
                plan=[*plan, PlanStep(name="metadata_resolution", status="blocked", detail="No metadata catalog loaded.")],
                sql=sql,
                warnings=["No metadata catalog is loaded."],
                metadata_version=None,
            )
            self._audit(session_id, message, response, event="sql_execute")
            return response

        validation = self.validator.validate(sql, catalog)
        plan.append(
            PlanStep(
                name="sql_validation",
                status="complete" if validation.is_safe else "blocked",
                detail="; ".join(validation.errors or validation.warnings),
            )
        )
        response = ChatResponse(
            answer="Approved SQL did not pass safety validation." if not validation.is_safe else "Approved SQL is ready.",
            plan=plan,
            sql=validation.safe_sql if validation.is_safe else sql,
            warnings=[*validation.warnings, *validation.errors],
            metadata_version=catalog.version,
            validation=SqlValidationPayload(
                is_safe=validation.is_safe,
                errors=validation.errors,
                warnings=validation.warnings,
                tables=validation.tables,
            ),
        )

        if not validation.is_safe:
            self._audit(session_id, message, response, event="sql_execute")
            return response

        if not self.oracle.configured:
            response.answer = "SQL was approved and validated, but Oracle connection settings are not configured."
            response.warnings.append("Oracle connection is not configured.")
            self._audit(session_id, message, response, event="sql_execute")
            return response

        try:
            columns, rows = await self.oracle.execute(response.sql or sql, max_rows=self.settings.sql_max_rows)
            response.columns = columns
            response.rows_preview = rows
            response.answer = await self.llm.synthesize_answer(message, response.sql or sql, columns, rows, response.warnings)
            response.executed = True
            response.requires_execution_approval = False
            response.plan.append(
                PlanStep(name="oracle_execution", status="complete", detail=f"Fetched {len(rows)} row(s).")
            )
            response.plan.append(PlanStep(name="answer_synthesis", status="complete"))
        except Exception as exc:
            response.answer = "The SQL was generated, but Oracle execution failed."
            response.warnings.append(str(exc))
            response.plan.append(PlanStep(name="oracle_execution", status="blocked", detail=str(exc)))

        self._audit(session_id, message, response, event="sql_execute")
        return response

    def _audit(self, session_id: str | None, message: str, response: ChatResponse, event: str = "chat") -> None:
        payload: dict[str, Any] = {
            "session_id": session_id,
            "message": message,
            "metadata_version": response.metadata_version,
            "sql": response.sql,
            "warnings": response.warnings,
            "requires_execution_approval": response.requires_execution_approval,
            "executed": response.executed,
            "validation": response.validation.model_dump() if response.validation else None,
        }
        self.audit.write(event, payload)
