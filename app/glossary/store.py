from __future__ import annotations

import math
import re
from dataclasses import dataclass

import httpx

from app.config import OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL
from app.glossary.models import SmsTemplate


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[A-Za-zА-Яа-яЁёԱ-Ֆա-ֆ0-9<>_]+", text.lower()) if token}


def lexical_score(query: str, candidate: str) -> float:
    q = _tokenize(query)
    c = _tokenize(candidate)
    if not q or not c:
        return 0.0
    overlap = len(q & c)
    return overlap / math.sqrt(len(q) * len(c))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_EMBED_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def embed(self, text: str) -> list[float]:
        payload = {"model": self.model, "prompt": text}
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}/api/embeddings", json=payload)
            response.raise_for_status()
            data = response.json()
        embedding = data.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            raise ValueError("Ollama returned empty embedding")
        return embedding


@dataclass
class RetrievedTemplate:
    template: SmsTemplate
    score: float
    method: str


class GlossaryStore:
    """In-memory glossary with embedding retrieval and lexical fallback."""

    def __init__(self, embedder: EmbeddingClient | None = None):
        self._embedder = embedder or EmbeddingClient()
        self._templates: list[SmsTemplate] = []
        self._embeddings: list[list[float] | None] = []
        self._source_path: str | None = None
        self._embed_model: str | None = None
        self._embeddings_ready = False

    @property
    def size(self) -> int:
        return len(self._templates)

    @property
    def ready(self) -> bool:
        return self.size > 0

    def status(self) -> dict:
        return {
            "ready": self.ready,
            "template_count": self.size,
            "source_path": self._source_path,
            "embeddings_ready": self._embeddings_ready,
            "embed_model": self._embed_model,
        }

    async def reindex(self, templates: list[SmsTemplate], source_path: str | None = None) -> dict:
        self._templates = templates
        self._source_path = source_path
        self._embeddings = [None] * len(templates)
        self._embeddings_ready = False
        self._embed_model = self._embedder.model

        errors: list[str] = []
        embedded = 0
        for idx, template in enumerate(templates):
            try:
                self._embeddings[idx] = await self._embedder.embed(template.search_text())
                embedded += 1
            except Exception as exc:  # noqa: BLE001 - keep reindex resilient for education use
                errors.append(f"template[{idx}]: {exc}")

        self._embeddings_ready = embedded > 0
        return {
            "template_count": len(templates),
            "embedded_count": embedded,
            "embeddings_ready": self._embeddings_ready,
            "source_path": source_path,
            "errors": errors[:5],
        }

    async def retrieve(self, query: str, top_k: int = 3) -> list[RetrievedTemplate]:
        if not self._templates:
            return []

        scored: list[RetrievedTemplate] = []
        query_for_match = SmsTemplate._strip_placeholders(query)

        query_embedding: list[float] | None = None
        if self._embeddings_ready:
            try:
                query_embedding = await self._embedder.embed(query_for_match)
            except Exception:  # noqa: BLE001
                query_embedding = None

        for idx, template in enumerate(self._templates):
            method = "lexical"
            score = lexical_score(query_for_match, template.search_text())

            embedding = self._embeddings[idx]
            if query_embedding is not None and embedding is not None:
                emb_score = cosine_similarity(query_embedding, embedding)
                # Lexical gets more weight so distinctive words (Anbavarar, Gnum, etc.) win
                # over shared SMS skeleton similarity from embeddings.
                score = (0.45 * emb_score) + (0.55 * score)
                method = "embedding+lexical"

            scored.append(RetrievedTemplate(template=template, score=score, method=method))

        scored.sort(key=lambda item: item.score, reverse=True)
        return [item for item in scored[:top_k] if item.score > 0] or scored[:top_k]
