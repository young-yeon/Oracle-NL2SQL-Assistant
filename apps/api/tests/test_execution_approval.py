import asyncio

from app.config import Settings
from app.schemas import SqlValidationPayload
from app.services.metadata import MetadataCatalog
from app.services.pipeline import QueryPipeline


class CatalogStoreStub:
    catalog = MetadataCatalog(version="test", created_at="now")

    def current_version(self):
        return "test"

    def load(self, version=None):
        return self.catalog


class GuardrailsStub:
    async def check_input(self, message):
        class Decision:
            allowed = True
            reason = "allowed"

        return Decision()


class LLMStub:
    async def semantic_analysis(self, message, catalog, matches):
        return {"intent": "data_query"}

    async def generate_sql(self, message, catalog, matches, analysis):
        return {"sql": "SELECT 1 AS OK FROM DUAL", "explanation": "test"}

    async def synthesize_answer(self, message, sql, columns, rows, warnings):
        return "done"


class OracleStub:
    configured = True

    def __init__(self):
        self.calls = 0

    async def execute(self, sql, max_rows=None):
        self.calls += 1
        return ["OK"], [{"OK": 1}]


class AuditStub:
    def write(self, event, payload):
        pass


class ValidatorStub:
    def validate(self, sql, catalog):
        class Result:
            is_safe = True
            safe_sql = "SELECT 1 AS OK FROM DUAL"
            errors = []
            warnings = []
            tables = []

        return Result()


def test_chat_requires_approval_before_oracle_execution():
    asyncio.run(_test_chat_requires_approval_before_oracle_execution())


async def _test_chat_requires_approval_before_oracle_execution():
    settings = Settings()
    oracle = OracleStub()
    pipeline = QueryPipeline(settings, CatalogStoreStub(), GuardrailsStub(), LLMStub(), oracle, AuditStub())
    pipeline.validator = ValidatorStub()

    response = await pipeline.chat("session", "show ok")

    assert response.requires_execution_approval
    assert not response.executed
    assert oracle.calls == 0


def test_approved_sql_executes_after_revalidation():
    asyncio.run(_test_approved_sql_executes_after_revalidation())


async def _test_approved_sql_executes_after_revalidation():
    settings = Settings()
    oracle = OracleStub()
    pipeline = QueryPipeline(settings, CatalogStoreStub(), GuardrailsStub(), LLMStub(), oracle, AuditStub())
    pipeline.validator = ValidatorStub()

    response = await pipeline.execute_approved_sql("session", "show ok", "SELECT 1 AS OK FROM DUAL")

    assert response.executed
    assert not response.requires_execution_approval
    assert response.validation == SqlValidationPayload(is_safe=True, errors=[], warnings=[], tables=[])
    assert oracle.calls == 1
