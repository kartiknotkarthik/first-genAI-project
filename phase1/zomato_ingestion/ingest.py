from __future__ import annotations

from typing import Any, Dict, Optional

from datasets import Dataset, load_dataset
from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.engine import Engine

from .config import DATASET_NAME, DATASET_SPLIT, default_db_url


def _infer_sqlalchemy_type(hf_feature: Any):
    """
    Infer a reasonable SQLAlchemy column type from a Hugging Face feature.

    This is intentionally conservative and uses Text for anything complex.
    """
    from datasets import ClassLabel, Sequence, Value

    # Primitive scalar
    if isinstance(hf_feature, Value):
        dtype = getattr(hf_feature, "dtype", "string")
        if dtype in ("int32", "int64", "uint32", "uint64"):
            return Integer
        if dtype in ("float32", "float64"):
            return Float
        if dtype in ("bool",):
            return Boolean
        # Everything else as text
        return Text

    # Categorical labels -> store as text label
    if isinstance(hf_feature, ClassLabel):
        return String(255)

    # Sequences / nested structures -> store as text (e.g. JSON-encoded)
    if isinstance(hf_feature, Sequence):
        return Text

    # Fallback to text
    return Text


def _should_index_column(column_name: str) -> bool:
    """
    Decide whether to create an index on a column based on its name.

    We focus on fields relevant to later phases: price, location/place, rating, cuisine.
    """
    lowered = column_name.lower()
    keywords = ("price", "cost", "location", "city", "place", "rating", "cuisine")
    return any(k in lowered for k in keywords)


def _clean_value(value: Any) -> Any:
    """
    Perform very light cleaning/normalization for ingestion.

    - Strip whitespace from strings.
    - Treat empty strings as NULL.
    """
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def build_metadata_from_dataset(dataset: Dataset, table_name: str = "restaurants") -> MetaData:
    """
    Build SQLAlchemy MetaData and a single table definition from a Hugging Face dataset.

    The table always contains:
      - id (Integer primary key, auto-increment)
      - One column per dataset feature, with inferred SQL types.
    """
    metadata = MetaData()

    columns = [
        Column("id", Integer, primary_key=True, autoincrement=True),
    ]

    for name, feature in dataset.features.items():
        # Skip if the name would conflict with the primary key
        if name == "id":
            continue

        col_type = _infer_sqlalchemy_type(feature)
        kwargs: Dict[str, Any] = {}
        if _should_index_column(name):
            kwargs["index"] = True

        # Use Text for long strings, String for shorter ones where possible
        if col_type is String:
            columns.append(Column(name, col_type(255), nullable=True, **kwargs))
        else:
            columns.append(Column(name, col_type, nullable=True, **kwargs))

    Table(table_name, metadata, *columns)
    return metadata


def ingest_dataset(
    db_url: Optional[str] = None,
    *,
    dataset: Optional[Dataset] = None,
    table_name: str = "restaurants",
    batch_size: int = 1000,
) -> Engine:
    """
    Ingest the Hugging Face Zomato dataset into a SQLite database.

    - If `dataset` is None, loads from Hugging Face using `DATASET_NAME` and `DATASET_SPLIT`.
    - Creates a single table with columns inferred from dataset features.
    - Performs light cleaning and inserts data in batches.

    Returns the SQLAlchemy Engine for further inspection or querying.
    """
    db_url = db_url or default_db_url()
    engine = create_engine(db_url, future=True)

    if dataset is None:
        dataset = load_dataset(DATASET_NAME, split=DATASET_SPLIT)

    metadata = build_metadata_from_dataset(dataset, table_name=table_name)
    metadata.drop_all(engine)  # ensure a clean slate for Phase 1 runs
    metadata.create_all(engine)

    restaurants_table = metadata.tables[table_name]

    with engine.begin() as conn:
        buffer = []
        for row in dataset:
            cleaned_row = {k: _clean_value(v) for k, v in row.items()}
            buffer.append(cleaned_row)

            if len(buffer) >= batch_size:
                conn.execute(restaurants_table.insert(), buffer)
                buffer.clear()

        if buffer:
            conn.execute(restaurants_table.insert(), buffer)

    return engine


if __name__ == "__main__":
    # Simple CLI entrypoint for manual Phase 1 execution.
    engine = ingest_dataset()
    print(f"Ingestion complete. Database URL: {engine.url}")

