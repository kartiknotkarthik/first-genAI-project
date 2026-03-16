from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import MetaData, Table, and_, create_engine, inspect, select
from sqlalchemy.engine import Engine

from .config import default_db_url


@dataclass
class RecommendationRequest:
    """
    Structured preferences for the core recommendation engine.

    These correspond to Phase 2 architecture:
    - price (max price_range/budget)
    - place (city/location)
    - rating (minimum rating)
    - cuisine (primary cuisine name)
    """

    city: Optional[str] = None
    location: Optional[str] = None
    cuisine: Optional[str] = None
    min_rating: Optional[float] = None
    max_price_range: Optional[int] = None
    limit: int = 10


def create_db_engine(db_url: Optional[str] = None) -> Engine:
    """Create a SQLAlchemy Engine for the restaurants database."""
    return create_engine(db_url or default_db_url(), future=True)


def load_restaurants_table(engine: Engine, table_name: str = "restaurants") -> Table:
    """
    Reflect the restaurants table from the existing database.

    This assumes Phase 1 has already created and populated the table.
    """
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        raise RuntimeError(f"Table '{table_name}' not found in database {engine.url}")

    metadata = MetaData()
    return Table(table_name, metadata, autoload_with=engine)


def _build_filters(table: Table, req: RecommendationRequest):
    """Build SQLAlchemy filter expressions based on available columns and request fields."""
    conditions = []
    cols = table.c

    # City filter (if column exists)
    if req.city and "city" in cols:
        conditions.append(cols.city.ilike(f"%{req.city}%"))

    # Location/area filter (if column exists)
    if req.location:
        # Prefer a 'location' column if present, otherwise fall back to 'address' or 'locality'
        for cand in ("location", "address", "locality"):
            if cand in cols:
                conditions.append(cols[cand].ilike(f"%{req.location}%"))
                break

    # Cuisine filter (if column exists)
    if req.cuisine:
        for cand in ("cuisine", "cuisines"):
            if cand in cols:
                conditions.append(cols[cand].ilike(f"%{req.cuisine}%"))
                break

    # Rating threshold (if rating-like column exists)
    if req.min_rating is not None:
        from sqlalchemy import cast, Float, func
        for cand in ("aggregate_rating", "rating", "user_rating", "rate"):
            if cand in cols:
                if cand == "rate":
                    # Parse "4.1/5" or "4.1 /5"
                    # We split by / and take the first part
                    clean_rate = func.substr(cols[cand], 1, func.instr(cols[cand], '/') - 1)
                    conditions.append(cast(func.trim(clean_rate), Float) >= req.min_rating)
                else:
                    conditions.append(cols[cand] >= req.min_rating)
                break

    # Max price / budget (if price-like column exists)
    if req.max_price_range is not None:
        from sqlalchemy import cast, Integer, func
        for cand in ("price_range", "average_cost_for_two", "cost", "approx_cost(for two people)"):
            if cand in cols:
                clean_col = func.replace(cols[cand], ',', '')
                conditions.append(cast(clean_col, Integer) <= req.max_price_range)
                break

    if not conditions:
        return None
    return and_(*conditions)


def _build_order_by(table: Table):
    """
    Build an ORDER BY clause that prefers highly rated and popular restaurants.

    This implementation is heuristic and robust to missing columns:
    - Primary: aggregate_rating / rating / user_rating (descending)
    - Secondary: votes / rating_count (descending) if available
    - Fallback: name ascending
    """
    cols = table.c
    order_by = []

    rating_col = None
    from sqlalchemy import cast, Float, func
    for cand in ("aggregate_rating", "rating", "user_rating", "rate"):
        if cand in cols:
            if cand == "rate":
                clean_rate = func.substr(cols[cand], 1, func.instr(cols[cand], '/') - 1)
                rating_col = cast(func.trim(clean_rate), Float)
            else:
                rating_col = cols[cand]
            break

    if rating_col is not None:
        order_by.append(rating_col.desc())

    votes_col = None
    for cand in ("votes", "rating_count"):
        if cand in cols:
            votes_col = cols[cand]
            break

    if votes_col is not None:
        order_by.append(votes_col.desc())

    if "name" in cols:
        order_by.append(cols.name.asc())

    return order_by


def get_recommendations(
    req: RecommendationRequest,
    db_url: Optional[str] = None,
    table_name: str = "restaurants",
) -> List[Dict[str, Any]]:
    """
    Retrieve a ranked list of restaurants based on structured preferences.

    - Connects to the SQLite DB (Phase 1 output) via `db_url` or default.
    - Applies best-effort filters for city, location, cuisine, rating, and price.
    - Orders results by rating (and votes if present), then name.
    - Returns a list of plain dictionaries (one per restaurant).
    """
    engine = create_db_engine(db_url)
    table = load_restaurants_table(engine, table_name=table_name)

    filters = _build_filters(table, req)
    stmt = select(table)
    if filters is not None:
        stmt = stmt.where(filters)

    order_by = _build_order_by(table)
    if order_by:
        stmt = stmt.order_by(*order_by)

    if req.limit > 0:
        stmt = stmt.limit(req.limit * 5)

    with engine.connect() as conn:
        rows = conn.execute(stmt).fetchall()

    results = []
    seen = set()
    for row in rows:
        mapping = dict(row._mapping)
        name = mapping.get("name")
        if name:
            name_key = name.lower().strip()
            if name_key in seen:
                continue
            seen.add(name_key)
        results.append(mapping)
        if len(results) >= req.limit:
            break

    return results


def get_metadata(
    db_url: Optional[str] = None,
    table_name: str = "restaurants",
) -> Dict[str, List[str]]:
    """
    Retrieve unique cities, localities, and cuisines for the UI dropdowns.
    """
    engine = create_db_engine(db_url)
    table = load_restaurants_table(engine, table_name=table_name)
    
    with engine.connect() as conn:
        cities = []
        if "listed_in(city)" in table.c:
            cities_raw = conn.execute(select(table.c["listed_in(city)"]).distinct()).fetchall()
            cities = [r[0] for r in cities_raw if r[0]]
        elif "city" in table.c:
            cities_raw = conn.execute(select(table.c["city"]).distinct()).fetchall()
            cities = [r[0] for r in cities_raw if r[0]]
            
        localities = []
        if "location" in table.c:
            localities_raw = conn.execute(select(table.c["location"]).distinct()).fetchall()
            localities = [r[0] for r in localities_raw if r[0]]
        elif "locality" in table.c:
            localities_raw = conn.execute(select(table.c["locality"]).distinct()).fetchall()
            localities = [r[0] for r in localities_raw if r[0]]
            
        cuisines_raw = []
        if "cuisines" in table.c:
            cuisines_data = conn.execute(select(table.c["cuisines"]).distinct()).fetchall()
            cuisines_raw = [r[0] for r in cuisines_data if r[0]]
        elif "cuisine" in table.c:
            cuisines_data = conn.execute(select(table.c["cuisine"]).distinct()).fetchall()
            cuisines_raw = [r[0] for r in cuisines_data if r[0]]
            
        cuisines = set()
        for c_list in cuisines_raw:
            if c_list:
                for c in str(c_list).split(","):
                    c_clean = c.strip()
                    if c_clean:
                        cuisines.add(c_clean)
                
        return {
            "cities": sorted(cities),
            "localities": sorted(localities),
            "cuisines": sorted(list(cuisines))
        }

