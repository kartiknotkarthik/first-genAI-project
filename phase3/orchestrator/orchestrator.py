"""LLM orchestrator: intent parsing, explanation generation, refinement flow."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import default_db_url
from .groq_client import GroqClient

# Import Phase 2 recommender (phase2 added to path in __init__.py)
from recommender.engine import RecommendationRequest, get_recommendations


INTENT_SYSTEM = """You are a restaurant preference extractor. Given a user's message, extract structured preferences for restaurant search.

Output ONLY a valid JSON object with these keys (use null for missing values):
- city: string or null (e.g. "Delhi", "Mumbai")
- location: string or null (area/neighborhood like "Connaught Place", "Bandra")
- cuisine: string or null (e.g. "North Indian", "Italian")
- min_rating: number 0-5 or null (minimum rating threshold)
- max_price_range: integer or null (budget max INR, e.g. 500, 1000, 2000)

Examples:
User: "cheap North Indian in Delhi" -> {"city":"Delhi","location":null,"cuisine":"North Indian","min_rating":null,"max_price_range":500}
User: "fancy Italian near Bandra, at least 4 stars" -> {"city":"Mumbai","location":"Bandra","cuisine":"Italian","min_rating":4.0,"max_price_range":null}
User: "any good restaurants" -> {"city":null,"location":null,"cuisine":null,"min_rating":null,"max_price_range":null}

Output only the JSON, no other text."""

EXPLANATION_SYSTEM = """You are a friendly restaurant recommendation assistant. Given a ranked list of restaurants and the user's preferences, write a brief, helpful response.

Include:
1. A short intro (1 sentence) summarizing what you found.
2. For each restaurant (up to top 5): name, 1-line reason why it matches.
3. End with 1-2 suggested refinements (e.g. "Want cheaper options?", "Only veg?").

Keep it concise and natural. No bullet points unless listing restaurants."""


@dataclass
class SessionContext:
    """Lightweight conversation context for refinement."""

    session_id: str
    last_preferences: Optional[Dict[str, Any]] = None
    last_results_summary: Optional[str] = None
    last_restaurants: List[Dict[str, Any]] = field(default_factory=list)


# In-memory session store (keyed by session_id)
_sessions: Dict[str, SessionContext] = {}


def _parse_intent_json(text: str) -> Dict[str, Any]:
    """Extract JSON from LLM response, with fallback parsing."""
    text = text.strip()
    # Try to find JSON block
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _json_to_request(data: Dict[str, Any], limit: int = 10) -> RecommendationRequest:
    """Convert parsed JSON to RecommendationRequest."""
    return RecommendationRequest(
        city=data.get("city"),
        location=data.get("location"),
        cuisine=data.get("cuisine"),
        min_rating=data.get("min_rating"),
        max_price_range=data.get("max_price_range"),
        limit=limit,
    )


def _merge_refinement(base: Dict[str, Any], refinement: Dict[str, Any]) -> Dict[str, Any]:
    """Merge refinement preferences into base; refinement overrides."""
    out = dict(base) if base else {}
    for k, v in refinement.items():
        if v is not None:
            out[k] = v
    return out


def parse_intent(
    user_message: str,
    groq_client: Optional[GroqClient] = None,
) -> RecommendationRequest:
    """
    Use Groq to parse free-text user message into structured preferences.

    Returns a RecommendationRequest ready for the Phase 2 engine.
    """
    client = groq_client or GroqClient()
    messages = [
        {"role": "system", "content": INTENT_SYSTEM},
        {"role": "user", "content": user_message},
    ]
    response = client.chat(messages, temperature=0.2)
    parsed = _parse_intent_json(response)
    return _json_to_request(parsed)


def generate_explanation(
    user_message: str,
    restaurants: List[Dict[str, Any]],
    groq_client: Optional[GroqClient] = None,
) -> str:
    """
    Use Groq to generate a human-friendly explanation of the recommendations.

    Includes brief rationale per restaurant and suggested refinements.
    """
    client = groq_client or GroqClient()
    if not restaurants:
        return "I couldn't find any restaurants matching your preferences. Try relaxing filters (e.g. lower rating, different area) or describe what you're looking for."

    # Build a compact summary for the LLM
    summary_lines = []
    for i, r in enumerate(restaurants[:5], 1):
        name = r.get("name", "Unknown")
        loc = r.get("location") or r.get("city") or ""
        cuisine = r.get("cuisine", "")
        rating = r.get("aggregate_rating") or r.get("rating", "")
        price = r.get("price_range", "")
        summary_lines.append(f"{i}. {name} | {loc} | {cuisine} | rating {rating} | price {price}")

    restaurants_text = "\n".join(summary_lines)
    messages = [
        {"role": "system", "content": EXPLANATION_SYSTEM},
        {"role": "user", "content": f"User asked: {user_message}\n\nRestaurants (ranked):\n{restaurants_text}"},
    ]
    return client.chat(messages, temperature=0.4)


def recommend(
    user_message: str,
    session_id: Optional[str] = None,
    db_url: Optional[str] = None,
    groq_client: Optional[GroqClient] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Full recommendation flow: parse intent → get recommendations → generate explanation.

    Returns:
        {
            "restaurants": [...],
            "explanation": "...",
            "session_id": "...",
        }
    """
    client = groq_client or GroqClient()
    db_url = db_url or default_db_url()

    req = parse_intent(user_message, groq_client=client)
    req.limit = limit

    restaurants = get_recommendations(req, db_url=db_url, table_name="restaurants")
    explanation = generate_explanation(user_message, restaurants, groq_client=client)

    sid = session_id or "default"
    _sessions[sid] = SessionContext(
        session_id=sid,
        last_preferences={
            "city": req.city,
            "location": req.location,
            "cuisine": req.cuisine,
            "min_rating": req.min_rating,
            "max_price_range": req.max_price_range,
        },
        last_results_summary=explanation[:500],
        last_restaurants=restaurants,
    )

    return {
        "restaurants": restaurants,
        "explanation": explanation,
        "session_id": sid,
    }


def refine(
    user_message: str,
    session_id: str,
    db_url: Optional[str] = None,
    groq_client: Optional[GroqClient] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Refinement flow: use previous context + new message to update preferences and re-recommend.

    If no session exists, falls back to a fresh recommend().
    """
    ctx = _sessions.get(session_id)
    if not ctx or not ctx.last_preferences:
        return recommend(user_message, session_id=session_id, db_url=db_url, groq_client=groq_client, limit=limit)

    client = groq_client or GroqClient()
    db_url = db_url or default_db_url()

    # Ask Groq to interpret the refinement in context
    refinement_prompt = f"""Previous preferences: {json.dumps(ctx.last_preferences)}
Previous results: {ctx.last_results_summary[:200]}...

User's follow-up: {user_message}

Extract updated preferences (merge/override). Output ONLY a JSON object with: city, location, cuisine, min_rating, max_price_range. Use null for unchanged."""
    messages = [
        {"role": "system", "content": INTENT_SYSTEM},
        {"role": "user", "content": refinement_prompt},
    ]
    response = client.chat(messages, temperature=0.2)
    parsed = _parse_intent_json(response)
    merged = _merge_refinement(ctx.last_preferences, parsed)
    req = _json_to_request(merged, limit=limit)

    restaurants = get_recommendations(req, db_url=db_url, table_name="restaurants")
    explanation = generate_explanation(user_message, restaurants, groq_client=client)

    _sessions[session_id] = SessionContext(
        session_id=session_id,
        last_preferences=merged,
        last_results_summary=explanation[:500],
        last_restaurants=restaurants,
    )

    return {
        "restaurants": restaurants,
        "explanation": explanation,
        "session_id": session_id,
    }
