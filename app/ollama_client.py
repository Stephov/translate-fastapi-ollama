import json
import re

import httpx

from app.schemas import SourceFormat


SYSTEM_PROMPT = """You are a banking terminology transformation engine.
Convert the input term into three languages and return ONLY valid JSON.

Output schema:
{
  "latarm": "latinized armenian if known, else empty string",
  "arm": "Armenian script",
  "eng": "English",
  "rus": "Russian"
}

Rules:
- Do not invent unrelated meanings.
- Keep banking/finance sense if the term looks domain-specific.
- If input is already one of the languages, still fill all fields.
- Return JSON only, no markdown, no comments.
"""


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _build_user_prompt(self, text: str, source: SourceFormat) -> str:
        return (
            f"source_format: {source.value}\n"
            f"input_text: {text}\n"
            "Transform this term and return JSON with keys latarm, arm, eng, rus."
        )

    async def transform(self, text: str, source: SourceFormat) -> dict:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._build_user_prompt(text, source)},
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
