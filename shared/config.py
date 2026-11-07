import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

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
SESSION_SECRET = os.getenv("SESSION_SECRET", "onboardai-secure-session-secret-key-2026")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "")
DEFAULT_EMPLOYEE_PASSWORD = os.getenv("DEFAULT_EMPLOYEE_PASSWORD", "")
TRUSTED_PROXIES = [
    ip.strip()
    for ip in os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1,testclient").split(",")
    if ip.strip()
]
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000",
    ).split(",")
    if o.strip()
]
