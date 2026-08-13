from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.openapi.utils import get_openapi

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
from app.swagger_examples import build_transform_openapi_examples
from app.transform_rules import build_fail_payload, find_validated_match, template_keywords

store = GlossaryStore()
ollama = OllamaClient()
TRANSFORM_OPENAPI_EXAMPLES = build_transform_openapi_examples()


async def _reindex_from_disk() -> dict:
    templates = load_templates(DEFAULT_EXCEL_PATH)
    return await store.reindex(templates, source_path=str(DEFAULT_EXCEL_PATH))


def _ordered_transform_examples() -> dict[str, dict]:
    examples = build_transform_openapi_examples()
    return {
        **{k: v for k, v in examples.items() if k.startswith("latarm_")},
        **{k: v for k, v in examples.items() if k.startswith("eng_")},
        **{k: v for k, v in examples.items() if not k.startswith(("latarm_", "eng_"))},
    }


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
    description=(
        "Educational local AI service for Latarm/ARM/ENG/RUS transformation with glossary RAG.\n\n"
        "Open `/transform` → **Try it out** → dropdown **Examples**: values are grouped as "
        "`[Latarm] ...` and `[Eng] ...` from `SMS_Templates.xlsx`."
    ),
    version="0.3.2",
    lifespan=lifespan,
)


def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    transform_post = openapi_schema.get("paths", {}).get("/transform", {}).get("post", {})
    request_body = transform_post.get("requestBody", {})
    content = request_body.get("content", {}).get("application/json")
    if content is not None:
        content.pop("example", None)
        content["examples"] = _ordered_transform_examples()

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "glossary": store.status()}


@app.get("/admin/glossary/status", response_model=GlossaryStatusResponse)
async def glossary_status() -> GlossaryStatusResponse:
    return GlossaryStatusResponse(**store.status())


@app.post("/admin/reindex", response_model=ReindexResponse)
async def reindex() -> ReindexResponse:
    """Reload SMS_Templates.xlsx and refresh embeddings/knowledge index."""
    global TRANSFORM_OPENAPI_EXAMPLES

    try:
        result = await _reindex_from_disk()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Reindex failed: {exc}") from exc

    TRANSFORM_OPENAPI_EXAMPLES = _ordered_transform_examples()
    app.openapi_schema = None
    return ReindexResponse(ok=True, **result)


@app.post(
    "/transform",
    response_model=TransformResponse,
    summary="Transform SMS text",
    description=(
        "Accepts only `text`. Source (Latarm/Eng) is detected automatically.\n\n"
        "In Swagger use the **Examples** dropdown: first all `[Latarm]` rows from Excel, then all `[Eng]`."
    ),
)
async def transform(
    request: Annotated[
        TransformRequest,
        Body(openapi_examples=TRANSFORM_OPENAPI_EXAMPLES),
    ],
) -> TransformResponse:
    if not store.ready:
        raise HTTPException(
            status_code=503,
            detail="Glossary is empty. Put SMS_Templates.xlsx into data/ and call POST /admin/reindex",
        )

    retrieved = await store.retrieve(request.text, top_k=RETRIEVE_TOP_K)
    source = detect_source(request.text, retrieved=retrieved)
    validated, keywords = find_validated_match(request.text, source, retrieved)
    if validated is None and retrieved:
        keywords = template_keywords(retrieved[0].template, source)

    candidates = [
        RetrievedCandidate(
            subject=item.template.subject,
            trans_type=item.template.trans_type,
            score=round(item.score, 4),
            method=item.method,
        )
        for item in retrieved
    ]

    if validated is None:
        fail = build_fail_payload(request.text)
        return TransformResponse(
            arm=fail["arm"],
            eng=fail["eng"],
            rus=fail["rus"],
            latarm=fail["latarm"],
            matched_subject=fail["matched_subject"],
            source_detected=source.value,
            transform_ok=False,
            required_keywords=keywords,
            model=str(fail["_model"]),
            retrieval_method=retrieved[0].method if retrieved else None,
            candidates=candidates,
            raw_model_output=None,
        )

    try:
        result = await ollama.transform(
            request.text,
            source,
            validated=validated,
            keywords=keywords,
        )
    except Exception as exc:  # noqa: BLE001 - educational endpoint, surface model/network errors
        raise HTTPException(status_code=502, detail=f"Ollama call failed: {exc}") from exc

    return TransformResponse(
        arm=str(result.get("arm", "")).strip(),
        eng=str(result.get("eng", "")).strip(),
        rus=str(result.get("rus", "")).strip(),
        latarm=(str(result.get("latarm", "")).strip() or None),
        matched_subject=(str(result.get("matched_subject", "")).strip() or validated.template.subject),
        source_detected=source.value,
        transform_ok=True,
        required_keywords=keywords,
        model=str(result.get("_model", ollama.model)),
        retrieval_method=validated.method,
        candidates=candidates,
        raw_model_output=str(result.get("_raw", "")),
    )
