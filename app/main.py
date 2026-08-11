from fastapi import FastAPI, HTTPException

from app.ollama_client import OllamaClient
from app.schemas import TransformRequest, TransformResponse

app = FastAPI(
    title="Latarm Transform AI",
    description="Educational local AI service for Latarm/ARM/ENG/RUS transformation",
    version="0.1.0",
)

ollama = OllamaClient()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/transform", response_model=TransformResponse)
async def transform(request: TransformRequest) -> TransformResponse:
    try:
        result = await ollama.transform(request.text, request.source)
    except Exception as exc:  # noqa: BLE001 - educational endpoint, surface model/network errors
        raise HTTPException(status_code=502, detail=f"Ollama call failed: {exc}") from exc

    return TransformResponse(
        arm=str(result.get("arm", "")).strip(),
        eng=str(result.get("eng", "")).strip(),
        rus=str(result.get("rus", "")).strip(),
        latarm=(str(result.get("latarm", "")).strip() or None),
        source_detected=request.source.value,
        model=str(result.get("_model", ollama.model)),
        raw_model_output=str(result.get("_raw", "")),
    )
