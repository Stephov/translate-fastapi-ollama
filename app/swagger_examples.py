from __future__ import annotations

import re

from app.config import DEFAULT_EXCEL_PATH
from app.glossary.loader import load_templates


def _slug(text: str, limit: int = 40) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return (cleaned or "template")[:limit]


def _short_subject(subject: str) -> str:
    # Prefer English part from "ARM/ENG/RUS" style subjects when present.
    parts = [part.strip() for part in subject.split("/") if part.strip()]
    if len(parts) >= 2:
        return parts[1]
    return subject[:60]


def build_transform_openapi_examples() -> dict[str, dict]:
    """Build Swagger examples for /transform from Excel (Latarm + Eng)."""
    try:
        templates = load_templates(DEFAULT_EXCEL_PATH)
    except Exception:  # noqa: BLE001 - docs should still open if excel temporarily missing
        return {
            "latarm_example": {
                "summary": "[Latarm] example",
                "description": "Excel glossary is not available yet.",
                "value": {"text": "Qarti hamalrum <amount> <currency>"},
            },
            "eng_example": {
                "summary": "[Eng] example",
                "description": "Excel glossary is not available yet.",
                "value": {"text": "Card credit <amount> <currency>"},
            },
        }

    examples: dict[str, dict] = {}

    for index, template in enumerate(templates, start=1):
        label = _short_subject(template.subject)
        n = template.n if template.n is not None else index
        slug = _slug(label)

        if template.latarm:
            key = f"latarm_{index:02d}_{slug}"
            examples[key] = {
                "summary": f"[Latarm] {n}. {label}",
                "description": f"Source template N={n}; field LATARM from SMS_Templates.xlsx",
                "value": {"text": template.latarm},
            }

        if template.eng:
            key = f"eng_{index:02d}_{slug}"
            examples[key] = {
                "summary": f"[Eng] {n}. {label}",
                "description": f"Source template N={n}; field ENG from SMS_Templates.xlsx",
                "value": {"text": template.eng},
            }

    return examples
