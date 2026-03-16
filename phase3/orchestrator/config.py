"""Phase 3 configuration: Groq API and database paths."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env: try DOTENV_PATH first, then project root, then phase3
_env_path = os.environ.get("DOTENV_PATH")
if _env_path:
    load_dotenv(_env_path)
else:
    _project_root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(_project_root / ".env")  # project root (outside phase3)
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")  # phase3/.env fallback


def get_groq_api_key() -> str:
    """Groq API key from environment. Raises if not set."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "GROQ_API_KEY environment variable is required for Phase 3. "
            "Get a key at https://console.groq.com/"
        )
    return key


def get_groq_model() -> str:
    """Groq model ID from environment or default."""
    return os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def default_db_url() -> str:
    """SQLite URL for Phase 1 database (used by Phase 2 recommender)."""
    phase1_db = Path(__file__).resolve().parent.parent.parent / "phase1" / "zomato_phase1.sqlite"
    return f"sqlite:///{phase1_db}"
