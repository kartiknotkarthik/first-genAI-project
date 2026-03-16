# Zomato-AI Restaurant Service — Architecture

## Overview

- **Goal**: An AI-powered restaurant recommendation service that takes user preferences (**price, place/location, rating, cuisine**) and returns **clear, ranked restaurant recommendations** with brief reasoning and easy refinement.
- **Primary data source**: Hugging Face dataset `ManikaSaini/zomato-restaurant-recommendation` (ingested offline, queried online).
- **Core approach**: Retrieval + ranking (filters + scoring; optional embeddings) to select candidates, with an LLM to parse intent and generate user-friendly explanations.

## High-level System Architecture

- **UI (Web)**
  - Preference input (structured filters + optional free-text).
  - Results view (ranked list + explanations).
  - Refinement loop (chat-like follow-ups).

- **Backend API**
  - Accepts recommendation requests and refinement requests.
  - Validates input and manages session/conversation context.
  - Orchestrates calls to:
    - LLM orchestrator (intent parsing + explanation)
    - Recommendation engine (filtering/ranking)
    - Data store / retrieval layer (structured + optional vector search)

- **LLM Orchestrator**
  - **Intent parsing**: Converts free-text into structured preferences (JSON).
  - **Response generation**: Produces a concise recommendation narrative and per-restaurant justification.
  - **Refinement**: Updates preferences based on follow-up messages.

- **Recommendation Engine**
  - Pre-filters candidates using structured fields (location, cuisine, rating, price).
  - Scores/ranks restaurants (rule-based or hybrid with embeddings).
  - Optionally diversifies results (avoid near-duplicates in top N).

- **Data Layer**
  - Offline ingestion pipeline from Hugging Face dataset.
  - Online query store (relational DB) with indices for filters.
  - Optional vector index for semantic matching if embeddings are added.

## Data Flow (End-to-End)

1. **User input** (filters + optional text) submitted from UI.
2. **Backend** sends free-text (and any explicit filters) to **LLM intent parsing** to produce structured preferences.
3. **Recommendation engine** queries the **data store**:
   - Apply hard filters (location, cuisine, min rating, price bounds).
   - Score and rank remaining candidates.
4. **Backend** sends top-K candidates to **LLM response generation** to produce:
   - Ranked recommendations with brief rationale
   - Suggested follow-up questions (refinement hooks)
5. **UI** renders the results and supports iterative refinement.

## Components (Responsibilities)

### UI (Web)

- Collect preferences:
  - **Price**: range/budget level
  - **Place**: city/area or “near X” (as supported by dataset)
  - **Rating**: minimum rating threshold
  - **Cuisine**: one or more cuisines
  - Optional: dietary constraints, ambience, “occasion”, etc.
- Display results:
  - Restaurant card list with key fields from dataset (name, location, cuisine, rating, price, etc.)
  - LLM-generated short reasoning
  - Controls to refine query

### Backend API

- Endpoint examples (illustrative):
  - `POST /api/recommendations` — new request
  - `POST /api/refine` — follow-up with conversation context
  - `GET /api/restaurants/:id` — details (optional)
  - `GET /api/health` — health checks
- Validates and normalizes inputs; logs request metadata and timing.

### LLM Orchestrator

- Prompt templates:
  - Intent extraction → structured JSON preferences
  - Explanation generation → short ranking rationale and trade-offs
  - Refinement handling → convert follow-up to preference updates
- Reliability concerns:
  - Output schema validation for extracted JSON
  - Timeouts/retries/rate limiting

### Recommendation Engine

- Filtering:
  - Location/area match (as supported by dataset columns)
  - Cuisine normalization and matching
  - Rating threshold
  - Price range/budget mapping
- Ranking:
  - Weighted scoring (e.g., rating + match quality + popularity indicators if present)
  - Optional semantic match using embeddings (hybrid scoring)
- Output:
  - Top-K items with feature breakdown (scores/reasons) for LLM to explain

### Data Layer

- Offline ingestion:
  - Pull dataset from Hugging Face.
  - Validate schema and handle missing values.
  - Normalize categorical fields (cuisine naming, location naming, price mapping).
  - Load into DB tables and create indices.
- Optional embeddings:
  - Create embeddings for text fields (if available) and store in a vector index.

## Non-Functional Requirements

- **Latency**: Keep DB retrieval fast (sub-200ms typical); overall request time dominated by LLM calls.
- **Observability**: Track p95 latency, error rate, and LLM usage; log preference extraction output (sanitized).
- **Security**: Keep API keys in environment variables; avoid storing unnecessary PII; apply rate limiting if public.

## Project Phases

### Phase 0 — Foundations & Planning

- Decide tech stack (backend framework, DB, UI framework).
- Define schema assumptions for the Hugging Face dataset and required fields.
- Establish repo structure, environment variable conventions, and local dev workflow.

### Phase 1 — Data Ingestion & Modeling

- Download dataset from Hugging Face (`ManikaSaini/zomato-restaurant-recommendation`).
- Data cleaning/normalization and schema design.
- Load into DB and add indices to support filtering and sorting.
- (Optional) Prepare embedding generation pipeline and vector index.

### Phase 2 — Core Recommendation Engine (No LLM)

- Implement filtering + ranking on structured inputs (price/place/rating/cuisine).
- Implement API contract for structured requests.
- Validate recommendation quality with test queries and edge cases (empty results, missing fields).

### Phase 3 — LLM Orchestration & Natural Language (Groq LLM)

- Use **Groq** as the LLM provider (Groq Cloud API).
- Implement a Groq LLM client wrapper:
  - API key and model configured via environment variables.
  - Timeouts, retries, and basic rate limiting.
- Add Groq-driven intent parsing:
  - Convert free-text input into structured JSON preferences (price/place/rating/cuisine + optional constraints).
  - Validate against a strict schema before calling the recommendation engine.
- Add Groq-driven explanation generation:
  - Produce a concise ranked list explanation and short per-item rationale.
  - Suggest follow-up refinements (e.g., “veg only”, “within 2km”, “cheaper”).
- Add conversation/refinement flow:
  - Persist a lightweight conversation context (session ID + last structured preferences + last results summary).

### Phase 4 — Hardening, Quality, and Ops

- Improve retrieval quality (better normalization, hybrid scoring, diversification).
- Add caching for repeated queries and common filters.
- Add observability (structured logs, metrics for latency and LLM usage).
- Add security hardening (secrets handling, rate limiting, abuse protection).

### Phase 5 — UI Page (Polished User Experience)

- Build a dedicated **UI page** for the project that includes:
  - Preference form (price/place/rating/cuisine) + free-text input.
  - Results page with ranked restaurant cards and Groq-generated reasoning.
  - Refinement controls (chat-style follow-ups) and “no results” guidance.
  - Responsive layout and accessible UX (keyboard navigation, clear states).
