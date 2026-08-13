from enum import Enum

from pydantic import BaseModel, Field


class SourceFormat(str, Enum):
    latarm = "latarm"
    eng = "eng"


class TransformRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Input text to transform")


class RetrievedCandidate(BaseModel):
    subject: str
    trans_type: str
    score: float
    method: str


class TransformResponse(BaseModel):
    arm: str
    eng: str
    rus: str
    latarm: str | None = None
    matched_subject: str | None = None
    source_detected: str
    transform_ok: bool = True
    required_keywords: list[str] = Field(default_factory=list)
    model: str
    retrieval_method: str | None = None
    candidates: list[RetrievedCandidate] = Field(default_factory=list)
    raw_model_output: str | None = None


class ReindexResponse(BaseModel):
    ok: bool
    template_count: int
    embedded_count: int
    embeddings_ready: bool
    source_path: str | None = None
    errors: list[str] = Field(default_factory=list)


class GlossaryStatusResponse(BaseModel):
    ready: bool
    template_count: int
    source_path: str | None = None
    embeddings_ready: bool
    embed_model: str | None = None
