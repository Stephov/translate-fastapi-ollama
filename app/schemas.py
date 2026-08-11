from enum import Enum

from pydantic import BaseModel, Field


class SourceFormat(str, Enum):
    latarm = "latarm"
    eng = "eng"
    auto = "auto"


class TransformRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Input text to transform")
    source: SourceFormat = Field(
        default=SourceFormat.auto,
        description="Input format: latarm, eng, or auto-detect",
    )


class TransformResponse(BaseModel):
    arm: str
    eng: str
    rus: str
    latarm: str | None = None
    source_detected: str
    model: str
    raw_model_output: str | None = None
