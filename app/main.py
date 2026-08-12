from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.config import DEFAULT_EXCEL_PATH, RETRIEVE_TOP_K
from app.glossary.loader import load_templates
from app.glossary.store import GlossaryStore
from app.ollama_client import OllamaClient
from app.schemas import (
    GlossaryStatusResponse,
    ReindexResponse,
    RetrievedCandidate,
    TransformRequest,
    TransformResponse,
)
from app.source_detector import detect_source

store = GlossaryStore()
ollama = OllamaClient()


async def _reindex_from_disk() -> dict:
    templates = load_templates(DEFAULT_EXCEL_PATH)
    return await store.reindex(templates, source_path=str(DEFAULT_EXCEL_PATH))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Load glossary at startup so /transform is AI+RAG ready immediately.
    try:
        await _reindex_from_disk()
    except Exception as exc:  # noqa: BLE001 - service can still boot; reindex endpoint available
        print(f"[startup] glossary reindex failed: {exc}")
    yield


app = FastAPI(
    title="Latarm Transform AI",
    description="Educational local AI service for Latarm/ARM/ENG/RUS transformation with glossary RAG",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "glossary": store.status()}


@app.get("/admin/glossary/status", response_model=GlossaryStatusResponse)
async def glossary_status() -> GlossaryStatusResponse:
    return GlossaryStatusResponse(**store.status())


@app.post("/admin/reindex", response_model=ReindexResponse)
async def reindex() -> ReindexResponse:
    """Reload SMS_Templates.xlsx and refresh embeddings/knowledge index."""
    try:
        result = await _reindex_from_disk()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Reindex failed: {exc}") from exc

    return ReindexResponse(ok=True, **result)


@app.post("/transform", response_model=TransformResponse)
async def transform(request: TransformRequest) -> TransformResponse:
    if not store.ready:
        raise HTTPException(
            status_code=503,
            detail="Glossary is empty. Put SMS_Templates.xlsx into data/ and call POST /admin/reindex",
        )

    retrieved = await store.retrieve(request.text, top_k=RETRIEVE_TOP_K)
    source = detect_source(request.text, retrieved=retrieved)

    try:
        result = await ollama.transform(request.text, source, retrieved=retrieved)
    except Exception as exc:  # noqa: BLE001 - educational endpoint, surface model/network errors
        raise HTTPException(status_code=502, detail=f"Ollama call failed: {exc}") from exc

    candidates = [
        RetrievedCandidate(
            subject=item.template.subject,
            trans_type=item.template.trans_type,
            score=round(item.score, 4),
            method=item.method,
        )
        for item in retrieved
    ]

    return TransformResponse(
        arm=str(result.get("arm", "")).strip(),
        eng=str(result.get("eng", "")).strip(),
        rus=str(result.get("rus", "")).strip(),
        latarm=(str(result.get("latarm", "")).strip() or None),
        matched_subject=(str(result.get("matched_subject", "")).strip() or None),
        source_detected=source.value,
        model=str(result.get("_model", ollama.model)),
        retrieval_method=retrieved[0].method if retrieved else None,
        candidates=candidates,
        raw_model_output=str(result.get("_raw", "")),
    )
