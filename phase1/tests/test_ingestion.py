from pathlib import Path

import pytest
from datasets import Dataset
from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine

from zomato_ingestion.ingest import build_metadata_from_dataset, ingest_dataset


def _create_sample_dataset() -> Dataset:
    """
    Create a tiny in-memory dataset that mimics key fields of the real Zomato dataset.
    This avoids network calls in unit tests while exercising the ingestion pipeline.
    """
    data = {
        "name": ["Spicy House", "Curry Palace"],
        "city": ["Delhi", "Mumbai"],
        "location": ["Connaught Place", "Bandra"],
        "cuisine": ["North Indian", "Indian"],
        "price_range": [2, 3],
        "aggregate_rating": [4.3, 4.7],
        "votes": [120, 340],
    }
    return Dataset.from_dict(data)


def test_build_metadata_from_dataset_creates_expected_columns():
    ds = _create_sample_dataset()
    metadata = build_metadata_from_dataset(ds, table_name="restaurants_test")

    assert "restaurants_test" in metadata.tables
    table = metadata.tables["restaurants_test"]

    # Always has an auto-increment primary key
    assert "id" in table.c

    # Columns from the dataset
    for col in ["name", "city", "location", "cuisine", "price_range", "aggregate_rating", "votes"]:
        assert col in table.c


def test_ingest_dataset_inserts_rows_and_creates_indices(tmp_path: Path):
    # Use a temporary SQLite DB for the test
    db_path = tmp_path / "test.sqlite"
    db_url = f"sqlite:///{db_path}"

    ds = _create_sample_dataset()
    engine: Engine = ingest_dataset(db_url=db_url, dataset=ds, table_name="restaurants_test")

    inspector = inspect(engine)

    # Table exists
    assert "restaurants_test" in inspector.get_table_names()

    # Columns exist
    columns = {col["name"] for col in inspector.get_columns("restaurants_test")}
    for col in ["id", "name", "city", "location", "cuisine", "price_range", "aggregate_rating", "votes"]:
        assert col in columns

    # Indices on important fields (price, location, rating, cuisine) should be present
    index_columns = {tuple(idx["column_names"]) for idx in inspector.get_indexes("restaurants_test")}
    # Flatten the set of tuples for easier membership checks
    indexed = {c for cols in index_columns for c in cols}
    for expected_index_col in ["price_range", "location", "aggregate_rating", "cuisine"]:
        assert expected_index_col in indexed

    # Check that rows were inserted and lightly cleaned
    metadata = build_metadata_from_dataset(ds, table_name="restaurants_test")
    table = metadata.tables["restaurants_test"]

    with engine.connect() as conn:
        result = conn.execute(select(table)).fetchall()

    assert len(result) == 2
    # Spot-check one row's values
    names = {row._mapping["name"] for row in result}
    assert names == {"Spicy House", "Curry Palace"}

