# Latarm Transform AI

Educational project: transform SMS text between Latarm / Armenian / English / Russian using local AI (Ollama) grounded on Excel glossary templates (RAG).

## Idea

You do **not** hardcode translation rules.
Flow is always AI:

1. Load templates from `data/SMS_Templates.xlsx` (sheet `New`)
2. On `/transform`, retrieve top similar templates (embeddings + lexical)
3. Auto-detect input source (`latarm` or `eng`)
4. Send input + candidates to Llama
5. Return `arm` / `eng` / `rus` (+ `latarm`)

Updating templates = put new Excel + call `/admin/reindex` (no model fine-tune yet).

## Stack

- Python 3.12 + FastAPI
- Ollama chat model: `llama3.2`
- Ollama embedding model: `nomic-embed-text`
- Excel glossary: `data/SMS_Templates.xlsx`

## Setup

```powershell
cd D:\Step\Programs\AI\latarm-transform
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

ollama pull llama3.2
ollama pull nomic-embed-text
```

Put glossary file here:

`data/SMS_Templates.xlsx`

## Run

```powershell
uvicorn app.main:app --reload --port 8001
```

Docs: http://localhost:8001/docs

## API

- `GET /health`
- `GET /admin/glossary/status`
- `POST /admin/reindex` — reload Excel and rebuild embeddings
- `POST /transform`

Example:

```json
{
  "text": "Qarti hamalrum <amount> <currency> <card_mask> <sw_date> <sw_time>, TRN NU <utrnno>, Mnacord: <acct_bal> <acct_curr>"
}
```

Rules:
- Placeholders / noise (`<amount>`, `TRN NU`, numbers, dates, currencies) are not transformed.
- If not all template keywords are present in input → `transform_ok=false`, subject=`Amio card`, all language fields = original text.
- `source` is detected automatically and returned as `source_detected`.

## Update templates

1. Replace `data/SMS_Templates.xlsx`
2. `POST /admin/reindex`
3. New `/transform` calls use updated knowledge

## Project layout

```text
app/
  main.py              # API + startup reindex
  source_detector.py   # auto-detect latarm vs eng
  ollama_client.py     # Llama chat with glossary-aware prompt
  schemas.py
  config.py
  glossary/
    loader.py          # Excel -> templates
    store.py           # embeddings retrieval + lexical fallback
    models.py
data/
  SMS_Templates.xlsx
```
