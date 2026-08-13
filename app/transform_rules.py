from __future__ import annotations

import re

from app.config import FAIL_SUBJECT, NOISE_TOKENS
from app.glossary.models import SmsTemplate
from app.schemas import SourceFormat

_PLACEHOLDER_RE = re.compile(r"<[^>]+>")
_TOKEN_RE = re.compile(r"[A-Za-zԱ-Ֆա-ֆА-Яа-яЁё0-9]+", re.UNICODE)
_NUMBER_RE = re.compile(r"^\d+([.,]\d+)?$")
_DATE_LIKE_RE = re.compile(r"^\d{1,4}([./-])\d{1,2}([./-])\d{1,4}$")
_TIME_LIKE_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")
_CURRENCY_RE = re.compile(r"^(AMD|USD|EUR|RUB|GBP|CHF)$", re.IGNORECASE)


def strip_placeholders(text: str) -> str:
    return " ".join(_PLACEHOLDER_RE.sub(" ", text).split()).strip()


def is_noise_token(token: str) -> bool:
    lowered = token.lower()
    if lowered in NOISE_TOKENS:
        return True
    if _NUMBER_RE.match(token):
        return True
    if _DATE_LIKE_RE.match(token):
        return True
    if _TIME_LIKE_RE.match(token):
        return True
    if _CURRENCY_RE.match(token):
        return True
    return False


def extract_keywords(text: str) -> list[str]:
    """Meaningful words only: no placeholders, noise, numbers, dates, currencies."""
    cleaned = strip_placeholders(text)
    keywords: list[str] = []
    seen: set[str] = set()
    for token in _TOKEN_RE.findall(cleaned):
        if is_noise_token(token):
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        keywords.append(token)
    return keywords


def template_keywords(template: SmsTemplate, source: SourceFormat) -> list[str]:
    side = template.latarm if source == SourceFormat.latarm else template.eng
    return extract_keywords(side)


def input_contains_all_keywords(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return False
    input_tokens = {token.lower() for token in _TOKEN_RE.findall(strip_placeholders(text))}
    return all(keyword.lower() in input_tokens for keyword in keywords)


def find_validated_match(
    text: str,
    source: SourceFormat,
    retrieved: list,
) -> tuple[object | None, list[str]]:
    """Return first retrieved candidate whose template keywords are all present in input."""
    for item in retrieved:
        keys = template_keywords(item.template, source)
        if input_contains_all_keywords(text, keys):
            return item, keys
    return None, []


def build_fail_payload(original_text: str) -> dict:
    return {
        "arm": original_text,
        "eng": original_text,
        "rus": original_text,
        "latarm": original_text,
        "matched_subject": FAIL_SUBJECT,
        "transform_ok": False,
        "_raw": None,
        "_model": "rules-engine",
    }
