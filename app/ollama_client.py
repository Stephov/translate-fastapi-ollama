import json
import re

import httpx

from app.config import OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL
from app.glossary.store import RetrievedTemplate
from app.schemas import SourceFormat


SYSTEM_PROMPT = """You are a banking SMS template transformation engine.
You MUST transform the input using the provided glossary templates.

Return ONLY valid JSON with this schema:
{
  "latarm": "latinized Armenian template/text",
  "arm": "Armenian script",
  "eng": "English",
  "rus": "Russian",
  "matched_subject": "subject from the best matching template"
}

Hard rules:
- Choose the glossary candidate whose LATARM/ENG opening phrase best matches the input meaning.
- Do not invent a new business meaning.
- Preserve placeholders exactly as in templates: <amount>, <currency>, <card_mask>, <sw_date>, <sw_time>, <utrnno>, <acct_bal>, <acct_curr>, <addr_name>, etc.
- If input contains concrete values instead of placeholders, keep those values in the same positions.
- If input is Latarm, fill arm/eng/rus (and latarm normalized from glossary when possible).
- If input is Eng, fill arm/rus (and eng normalized), plus latarm from glossary.
- matched_subject must come from the chosen candidate.
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
        retrieved: list[RetrievedTemplate],
    ) -> str:
        if retrieved:
            blocks = []
            for idx, item in enumerate(retrieved, start=1):
                blocks.append(
                    f"[candidate {idx} | score={item.score:.4f} | method={item.method}]\n"
                    f"{item.template.to_prompt_block()}"
                )
            glossary_block = "\n\n".join(blocks)
        else:
            glossary_block = "No glossary candidates available."

        return (
            f"source_format: {source.value}\n"
            f"input_text: {text}\n\n"
            f"Glossary candidates:\n{glossary_block}\n\n"
            "Transform the input into latarm/arm/eng/rus using the best candidate."
        )

    async def transform(
        self,
        text: str,
        source: SourceFormat,
        retrieved: list[RetrievedTemplate] | None = None,
    ) -> dict:
        retrieved = retrieved or []
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._build_user_prompt(text, source, retrieved)},
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
