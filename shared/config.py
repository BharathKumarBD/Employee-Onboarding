import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SEED_DATA_DIR = ROOT_DIR / "seed-data"
DATA_DIR = ROOT_DIR / "data"
CHROMA_PATH = DATA_DIR / "chroma"

DATA_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")  # Optional OpenAI-compatible base URL (e.g. Ollama, Groq, vLLM)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
DEFAULT_EMPLOYEE_ID = "alex-chen"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://onboardai:onboardai@localhost:5432/onboardai",
)

# Security
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "*",
    ).split(",")
    if o.strip()
]
