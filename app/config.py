from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_EXCEL_PATH = DATA_DIR / "SMS_Templates.xlsx"
DEFAULT_SHEET_NAME = "New"

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_CHAT_MODEL = "llama3.2"
OLLAMA_EMBED_MODEL = "nomic-embed-text"

RETRIEVE_TOP_K = 3
