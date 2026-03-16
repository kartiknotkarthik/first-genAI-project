from pathlib import Path

# Hugging Face dataset identifier used in Phase 1.
DATASET_NAME: str = "ManikaSaini/zomato-restaurant-recommendation"

# Default split to ingest. The dataset currently exposes a single split with all rows.
DATASET_SPLIT: str = "train"


def default_db_path() -> Path:
    """
    Default path for the Phase 1 SQLite database file.

    The database lives inside the phase1 folder so it is self-contained.
    """
    return Path(__file__).resolve().parent.parent / "zomato_phase1.sqlite"


def default_db_url() -> str:
    """SQLAlchemy database URL for the default SQLite DB."""
    return f"sqlite:///{default_db_path()}"

