from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.config import Settings


class GuardrailsDecision(BaseModel):
    allowed: bool
    reason: str = ""
    source: str = "deterministic"


class GuardrailsService:
    DANGEROUS = re.compile(
        r"\b(ignore previous|system prompt|developer message|jailbreak|drop|truncate|delete|update|insert|merge|alter|create|grant|revoke|execute|exec|call)\b",
        re.IGNORECASE,
    )

    def __init__(self, settings: Settings):
        self.settings = settings
        self.rails = None
        self.ready = False
        self._initialize()

    def _initialize(self) -> None:
        if not self.settings.nemo_guardrails_enabled or not self.settings.llm_configured:
            return
        try:
            from nemoguardrails import LLMRails, RailsConfig

            runtime_dir = self.settings.storage_dir / "runtime_guardrails"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            self._write_runtime_config(runtime_dir)
            config = RailsConfig.from_path(str(runtime_dir))
            self.rails = LLMRails(config)
            self.ready = True
        except Exception:
            self.rails = None
            self.ready = False

    def _write_runtime_config(self, runtime_dir: Path) -> None:
        source_dir = self.settings.nemo_config_path
        for filename in ["prompts.yml", "rails.co"]:
            source = source_dir / filename
            if source.exists():
                shutil.copyfile(source, runtime_dir / filename)

        config = {
            "models": [
                {
                    "type": "main",
                    "engine": "openai",
                    "model": self.settings.llm_model,
                    "parameters": {
                        "base_url": self.settings.llm_base_url,
                        "api_key": self.settings.llm_api_key,
                    },
                }
            ],
            "rails": {"input": {"flows": ["self check input"]}},
        }
        (runtime_dir / "config.yml").write_text(yaml.safe_dump(config), encoding="utf-8")

    async def check_input(self, message: str) -> GuardrailsDecision:
        if self.rails is not None:
            decision = await self._check_with_nemo(message)
            if decision is not None:
                return decision
        return self._deterministic_check(message)

    async def _check_with_nemo(self, message: str) -> GuardrailsDecision | None:
        try:
            check_async = getattr(self.rails, "check_async", None)
            if check_async is None:
                return None
            rail_types = None
            try:
                from nemoguardrails.rails.llm.options import RailType

                rail_types = [RailType.INPUT]
            except Exception:
                rail_types = None
            kwargs = {"messages": [{"role": "user", "content": message}]}
            if rail_types is not None:
                kwargs["rail_types"] = rail_types
            result = await check_async(**kwargs)
            status = str(getattr(result, "status", "")).lower()
            blocked = bool(getattr(result, "blocked", False))
            content = str(getattr(result, "content", "") or "")
            if blocked or "block" in status or "fail" in status:
                return GuardrailsDecision(allowed=False, reason=content or "Blocked by NeMo Guardrails.", source="nemo")
            return GuardrailsDecision(allowed=True, reason="Allowed by NeMo Guardrails.", source="nemo")
        except Exception:
            return None

    def _deterministic_check(self, message: str) -> GuardrailsDecision:
        if not message.strip():
            return GuardrailsDecision(allowed=False, reason="Message is empty.")
        if self.DANGEROUS.search(message):
            return GuardrailsDecision(
                allowed=False,
                reason="Request appears to violate the read-only database assistant policy.",
            )
        return GuardrailsDecision(allowed=True, reason="Allowed by deterministic guardrail.")
