# Latarm Transform AI

Educational project: transform transaction text between Latarm / Armenian / English / Russian using a local AI model (Ollama), not hardcoded if/else dictionaries.

## Stack

- Python 3.12
- FastAPI (API)
- Ollama + `llama3.2` (local model)
- Docker (later, for vector DB / compose)

## Project layout

```text
latarm-transform/
  app/
    main.py            # FastAPI entrypoint
    schemas.py         # request/response models
    ollama_client.py   # calls local Ollama
  data/                # Excel glossary will go here later
  requirements.txt
```

## Setup

1. Create venv and install deps:

```powershell
cd D:\Step\Programs\AI\latarm-transform
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Make sure Ollama is running and model exists:

```powershell
ollama list
```

3. Start API:

```powershell
uvicorn app.main:app --reload --port 8001
```

4. Open docs: http://localhost:8001/docs

## Example request

```http
POST /transform
{
  "text": "kanxikacum",
  "source": "latarm"
}
```

## Next steps

1. Load Excel glossary into `data/`
2. Add exact/fuzzy match before LLM
3. Add embeddings / RAG
4. Push to GitHub under `maratuktours-com`
