from __future__ import annotations

from pathlib import Path


def default_db_path() -> Path:
    """
    Default path to the SQLite database populated in Phase 1.

    By convention, Phase 1 writes `zomato_phase1.sqlite` in the `phase1` folder.
    Phase 2 reads from the same file to power the recommendation engine.
    """
    phase2_dir = Path(__file__).resolve().parent.parent
    return phase2_dir.parent / "phase1" / "zomato_phase1.sqlite"


def default_db_url() -> str:
    """SQLAlchemy database URL for the shared SQLite DB."""
    return f"sqlite:///{default_db_path()}"

