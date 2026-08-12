from __future__ import annotations

import re

from app.glossary.models import SmsTemplate
from app.glossary.store import RetrievedTemplate, lexical_score
from app.schemas import SourceFormat

_ARMENIAN_RE = re.compile(r"[\u0530-\u058F]")
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_LATIN_RE = re.compile(r"[A-Za-z]")

# Frequent English SMS tokens from banking templates.
_ENGLISH_HINTS = {
    "insufficient",
    "funds",
    "purchase",
    "refund",
    "balance",
    "card",
    "credit",
    "debit",
    "cash",
    "withdrawal",
    "return",
    "hold",
    "amount",
    "status",
    "network",
    "terminal",
    "transfer",
}

# Frequent Latarm tokens / stems from the glossary.
_LATARM_HINTS = {
    "anbavarar",
    "mijocner",
    "mnacord",
    "qarti",
    "qartic",
    "hamalrum",
    "elqagrum",
    "gnum",
    "gnman",
    "veradardz",
    "kankhiki",
    "stacum",
    "mutqagrum",
    "poxancum",
    "gumari",
}


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[A-Za-zА-Яа-яЁёԱ-Ֆա-ֆ0-9]+", text.lower()) if token}


def detect_source(
    text: str,
    retrieved: list[RetrievedTemplate] | None = None,
) -> SourceFormat:
    """Detect whether input is Latarm or Eng.

    Priority:
    1. Script heuristics
    2. Similarity vs LATARM/ENG sides of retrieved glossary templates
    3. Keyword hints
    """
    cleaned = SmsTemplate._strip_placeholders(text)
    if not cleaned.strip():
        return SourceFormat.latarm

    if _ARMENIAN_RE.search(cleaned):
        # Armenian script is closer to ARM templates; treat as latarm-side workflow
        # is wrong — but API contract is latarm/eng. Prefer latarm pathway via ARM match.
        return SourceFormat.latarm

    if _CYRILLIC_RE.search(cleaned) and not _LATIN_RE.search(cleaned):
        # Pure Russian input is outside primary contract; map to eng-side as nearest Latin business text.
        return SourceFormat.eng

    latarm_score = 0.0
    eng_score = 0.0

    if retrieved:
        for item in retrieved:
            latarm_score = max(
                latarm_score,
                lexical_score(cleaned, SmsTemplate._strip_placeholders(item.template.latarm)),
            )
            eng_score = max(
                eng_score,
                lexical_score(cleaned, SmsTemplate._strip_placeholders(item.template.eng)),
            )

    tokens = _tokens(cleaned)
    eng_hits = len(tokens & _ENGLISH_HINTS)
    latarm_hits = len(tokens & _LATARM_HINTS)

    # Blend glossary similarity with lightweight keyword hints.
    eng_total = eng_score + 0.15 * eng_hits
    latarm_total = latarm_score + 0.15 * latarm_hits

    if eng_total > latarm_total:
        return SourceFormat.eng
    if latarm_total > eng_total:
        return SourceFormat.latarm

    # Tie-breaker: Latin text with no strong glossary signal → prefer eng if English hints exist.
    if eng_hits > latarm_hits:
        return SourceFormat.eng
    return SourceFormat.latarm
