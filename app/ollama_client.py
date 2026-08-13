import json
import re

import httpx

from app.config import OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL
from app.glossary.store import RetrievedTemplate
from app.schemas import SourceFormat


SYSTEM_PROMPT = """You are a banking SMS template transformation engine.
You MUST transform the input using the provided glossary template.

Return ONLY valid JSON with this schema:
{
  "latarm": "latinized Armenian template/text",
  "arm": "Armenian script",
  "eng": "English",
  "rus": "Russian",
  "matched_subject": "subject from the chosen template"
}

Hard rules:
- Transform ONLY meaningful template words (example: Qarti, hamalrum, Mnacord).
- Do NOT translate/change placeholders: <amount>, <currency>, <card_mask>, <sw_date>, <sw_time>, <utrnno>, <acct_bal>, <acct_curr>, <addr_name>, etc.
- Do NOT translate/change noise tokens such as TRN NU, punctuation, numbers, dates, times, currency codes, masks, and similar technical values.
- Keep frozen tokens exactly as in the input, in the same positions.
- Use the provided validated template as the meaning source.
- If input is Latarm, fill arm/eng/rus (and normalized latarm from glossary wording when possible).
- If input is Eng, fill arm/rus/latarm (and normalized eng from glossary wording when possible).
- matched_subject must come from the chosen template.
- Return JSON only, no markdown.
"""


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_CHAT_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _build_user_prompt(
        self,
        text: str,
        source: SourceFormat,
        validated: RetrievedTemplate,
        keywords: list[str],
    ) -> str:
        return (
            f"source_format: {source.value}\n"
            f"input_text: {text}\n"
            f"transformable_keywords: {', '.join(keywords)}\n\n"
            f"Validated glossary template:\n{validated.template.to_prompt_block()}\n\n"
            "Transform only transformable_keywords / their language equivalents. "
            "Keep all placeholders, TRN NU, punctuation, numbers, dates and technical values unchanged."
        )

    async def transform(
        self,
        text: str,
        source: SourceFormat,
        validated: RetrievedTemplate,
        keywords: list[str],
    ) -> dict:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": self._build_user_prompt(text, source, validated, keywords),
                },
            ],
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

        content = data.get("message", {}).get("content", "")
        parsed = self._parse_json(content)
        parsed["_raw"] = content
        parsed["_model"] = self.model
        return parsed

    @staticmethod
    def _parse_json(content: str) -> dict:
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if not match:
                raise ValueError(f"Model did not return JSON: {content[:300]}")
            return json.loads(match.group(0))
