from __future__ import annotations

import re
from typing import Any

from app.services.metadata import MetadataCatalog


def normalize_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9_ .-]", " ", value.lower())).strip()


def phrase_matches(phrase: str, text: str) -> bool:
    normalized_phrase = normalize_phrase(phrase)
    normalized_text = normalize_phrase(text)
    if not normalized_phrase:
        return False
    return normalized_phrase in normalized_text


class SynonymResolver:
    def resolve(self, message: str, catalog: MetadataCatalog) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []

        for table in catalog.tables:
            for alias in [table.name, table.display_name, *table.synonyms]:
                if phrase_matches(alias, message):
                    matches.append(
                        {
                            "type": "table",
                            "matched": alias,
                            "target": table.qualified_name,
                            "description": table.description,
                        }
                    )
                    break

        for column in catalog.columns:
            for alias in [column.name, column.display_name, *column.synonyms]:
                if phrase_matches(alias, message):
                    matches.append(
                        {
                            "type": "column",
                            "matched": alias,
                            "target": f"{column.table}.{column.name}",
                            "description": column.description,
                            "semantic_type": column.semantic_type,
                        }
                    )
                    break

        for term in catalog.terms:
            for alias in [term.term, *term.synonyms]:
                if phrase_matches(alias, message):
                    matches.append(
                        {
                            "type": term.canonical_type or "term",
                            "matched": alias,
                            "target": term.canonical_value or term.term,
                            "description": term.description,
                        }
                    )
                    break

        for metric in catalog.metrics:
            for alias in [metric.name, *metric.synonyms]:
                if phrase_matches(alias, message):
                    matches.append(
                        {
                            "type": "metric",
                            "matched": alias,
                            "target": metric.name,
                            "expression": metric.expression,
                            "table": metric.table,
                            "description": metric.description,
                        }
                    )
                    break

        return matches

