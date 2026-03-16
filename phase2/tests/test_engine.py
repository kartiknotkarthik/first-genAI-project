from pathlib import Path

from sqlalchemy import Column, Float, Integer, MetaData, String, Table, create_engine

from recommender.engine import RecommendationRequest, get_recommendations


def _setup_temp_db(tmp_path: Path, table_name: str = "restaurants") -> str:
    """
    Create a temporary SQLite database with a small restaurants table
    to exercise the phase 2 recommendation engine.
    """
    db_path = tmp_path / "phase2_test.sqlite"
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
                {
                    "name": "Spicy House",
                    "city": "Delhi",
                    "location": "Connaught Place",
                    "cuisine": "North Indian",
                    "price_range": 2,
                    "aggregate_rating": 4.3,
                    "votes": 120,
                },
                {
                    "name": "Curry Palace",
                    "city": "Delhi",
                    "location": "Karol Bagh",
                    "cuisine": "North Indian",
                    "price_range": 3,
                    "aggregate_rating": 4.7,
                    "votes": 340,
                },
                {
                    "name": "Pizza Town",
                    "city": "Mumbai",
                    "location": "Bandra",
                    "cuisine": "Italian",
                    "price_range": 2,
                    "aggregate_rating": 4.1,
                    "votes": 90,
                },
            ],
        )

    return db_url


def test_recommendations_filter_by_city_and_cuisine(tmp_path: Path):
    db_url = _setup_temp_db(tmp_path)

    req = RecommendationRequest(city="Delhi", cuisine="North Indian", min_rating=4.0, max_price_range=3, limit=5)
    results = get_recommendations(req, db_url=db_url)

    # Should only return the two Delhi North Indian restaurants
    assert len(results) == 2
    names = {r["name"] for r in results}
    assert names == {"Spicy House", "Curry Palace"}


def test_recommendations_are_ordered_by_rating_and_votes(tmp_path: Path):
    db_url = _setup_temp_db(tmp_path)

    req = RecommendationRequest(city="Delhi", cuisine="North Indian", min_rating=4.0, max_price_range=5, limit=5)
    results = get_recommendations(req, db_url=db_url)

    # Both Delhi North Indian restaurants match; higher rating and votes should come first
    assert [r["name"] for r in results] == ["Curry Palace", "Spicy House"]


def test_recommendations_respect_limit(tmp_path: Path):
    db_url = _setup_temp_db(tmp_path)

    req = RecommendationRequest(min_rating=0.0, max_price_range=10, limit=1)
    results = get_recommendations(req, db_url=db_url)

    # Only one result should be returned due to the limit
    assert len(results) == 1

