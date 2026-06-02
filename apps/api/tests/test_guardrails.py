import asyncio

from app.config import Settings
from app.services.guardrails import GuardrailsService


def test_deterministic_guardrail_blocks_destructive_language(tmp_path):
    settings = Settings(
        STORAGE_DIR=tmp_path,
        NEMO_GUARDRAILS_ENABLED=False,
    )
    decision = asyncio.run(GuardrailsService(settings).check_input("delete all sales rows"))

    assert not decision.allowed
