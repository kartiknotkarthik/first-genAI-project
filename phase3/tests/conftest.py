"""Pytest configuration: add phase2 to path for recommender imports."""

import sys
from pathlib import Path

_phase2 = Path(__file__).resolve().parent.parent.parent / "phase2"
if _phase2.exists() and str(_phase2) not in sys.path:
    sys.path.insert(0, str(_phase2))
