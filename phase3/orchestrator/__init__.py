"""
Phase 3: LLM Orchestration & Natural Language (Groq LLM).

This package is responsible for:
- Groq-driven intent parsing (free-text → structured preferences).
- Groq-driven explanation generation (ranked list + rationale).
- Conversation/refinement flow with session context.
"""

import sys
from pathlib import Path

# Allow importing recommender from phase2 when running from phase3
_phase2 = Path(__file__).resolve().parent.parent.parent / "phase2"
if _phase2.exists() and str(_phase2) not in sys.path:
    sys.path.insert(0, str(_phase2))
