from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.config import DEFAULT_EXCEL_PATH, DEFAULT_SHEET_NAME
from app.glossary.models import SmsTemplate


def _clean(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).replace("_x000D_", " ").replace("\r", " ")
    return " ".join(text.split()).strip()


def load_templates(
    excel_path: Path | None = None,
    sheet_name: str = DEFAULT_SHEET_NAME,
) -> list[SmsTemplate]:
    path = excel_path or DEFAULT_EXCEL_PATH
    if not path.exists():
        raise FileNotFoundError(f"Excel glossary not found: {path}")

    df = pd.read_excel(path, sheet_name=sheet_name)
    required = ["Subject", "LATARM", "ARM", "ENG", "RUS"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Sheet '{sheet_name}' missing columns: {missing}")

    templates: list[SmsTemplate] = []
    for _, row in df.iterrows():
        latarm = _clean(row.get("LATARM"))
        arm = _clean(row.get("ARM"))
        eng = _clean(row.get("ENG"))
        rus = _clean(row.get("RUS"))
        if not any((latarm, arm, eng, rus)):
            continue

        n_raw = row.get("N")
        n_val: int | None
        try:
            n_val = int(n_raw) if pd.notna(n_raw) else None
        except (TypeError, ValueError):
            n_val = None

        templates.append(
            SmsTemplate(
                n=n_val,
                subject=_clean(row.get("Subject")),
                trans_type=_clean(row.get("TRANS_TYPE")),
                latarm=latarm,
                arm=arm,
                eng=eng,
                rus=rus,
                reverse_indicator=_clean(row.get("reverse indicator")) or None,
                resp_code=_clean(row.get("resp code")) or None,
            )
        )

    if not templates:
        raise ValueError(f"No templates loaded from {path} sheet '{sheet_name}'")

    return templates
