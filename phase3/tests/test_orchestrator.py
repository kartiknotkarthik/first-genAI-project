"""Unit tests for Phase 3 orchestrator (Groq mocked)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure phase2 is on path (conftest does this)
from recommender.engine import RecommendationRequest, get_recommendations
from sqlalchemy import Column, Float, Integer, MetaData, String, Table, create_engine


def _setup_temp_db(tmp_path: Path, table_name: str = "restaurants") -> str:
    """Create a temporary SQLite DB with sample restaurants for Phase 3 tests."""
    db_path = tmp_path / "phase3_test.sqlite"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(db_url, future=True)
    metadata = MetaData()
    Table(
        table_name,
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("name", String(255), nullable=False),
        Column("city", String(255)),
        Column("location", String(255)),
        Column("cuisine", String(255)),
        Column("price_range", Integer),
        Column("aggregate_rating", Float),
        Column("votes", Integer),
    )
    metadata.create_all(engine)

    restaurants = metadata.tables[table_name]
    with engine.begin() as conn:
        conn.execute(
            restaurants.insert(),
            [
                {"name": "Spicy House", "city": "Delhi", "location": "CP", "cuisine": "North Indian", "price_range": 2, "aggregate_rating": 4.3, "votes": 120},
                {"name": "Curry Palace", "city": "Delhi", "location": "Karol Bagh", "cuisine": "North Indian", "price_range": 3, "aggregate_rating": 4.7, "votes": 340},
            ],
        )

    return db_url


@pytest.fixture
def mock_groq_client():
    """Mock GroqClient to avoid real API calls."""
    with patch("orchestrator.orchestrator.GroqClient") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield instance


def test_parse_intent_returns_request(mock_groq_client):
    """Intent parsing should return a valid RecommendationRequest."""
    mock_groq_client.chat.return_value = '{"city":"Delhi","location":null,"cuisine":"North Indian","min_rating":4.0,"max_price_range":2}'

    from orchestrator.orchestrator import parse_intent

    req = parse_intent("cheap North Indian in Delhi, at least 4 stars", groq_client=mock_groq_client)

    assert isinstance(req, RecommendationRequest)
    assert req.city == "Delhi"
    assert req.cuisine == "North Indian"
    assert req.min_rating == 4.0
    assert req.max_price_range == 2


def test_recommend_returns_restaurants_and_explanation(mock_groq_client, tmp_path):
    """Full recommend flow should return restaurants and Groq-generated explanation."""
    db_url = _setup_temp_db(tmp_path)

    mock_groq_client.chat.side_effect = [
        '{"city":"Delhi","location":null,"cuisine":"North Indian","min_rating":null,"max_price_range":5}',
        "Here are great North Indian options in Delhi: 1. Curry Palace - top rated. 2. Spicy House - popular choice. Want cheaper options?",
    ]

    from orchestrator.orchestrator import recommend

    result = recommend("North Indian in Delhi", db_url=db_url, groq_client=mock_groq_client, limit=5)

    assert "restaurants" in result
    assert "explanation" in result
    assert "session_id" in result
    assert len(result["restaurants"]) == 2
    assert "Curry Palace" in [r["name"] for r in result["restaurants"]]
    assert "North Indian" in result["explanation"] or "Curry" in result["explanation"]


def test_refine_updates_preferences(mock_groq_client, tmp_path):
    """Refinement should use session context and produce updated results."""
    db_url = _setup_temp_db(tmp_path)

    # First call: initial recommend
    mock_groq_client.chat.side_effect = [
        '{"city":"Delhi","location":null,"cuisine":"North Indian","min_rating":null,"max_price_range":5}',
        "Here are options.",
        # Refinement: user says "cheaper"
        '{"city":"Delhi","location":null,"cuisine":"North Indian","min_rating":null,"max_price_range":2}',
        "Here are cheaper options.",
    ]

    from orchestrator.orchestrator import recommend, refine

    r1 = recommend("North Indian in Delhi", session_id="s1", db_url=db_url, groq_client=mock_groq_client, limit=5)
    assert len(r1["restaurants"]) == 2

    r2 = refine("make it cheaper", session_id="s1", db_url=db_url, groq_client=mock_groq_client, limit=5)
    assert "restaurants" in r2
    assert r2["session_id"] == "s1"
