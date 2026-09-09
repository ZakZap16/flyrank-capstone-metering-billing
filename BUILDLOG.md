# BUILDLOG.md — AI Tool Usage and Architectural Decisions

This file documents the AI-assisted development process, architectural decisions, and bug resolutions for the FlyRank Capstone Project.

---

## Development Phases

### Phase 1: Project Initialization (Day 1)

- **Tool**: `uv init` + manual FastAPI setup
- **Decisions**: Python 3.11, FastAPI + SQLAlchemy[asyncio] + PostgreSQL + Alembic
- **Commands**: `uv start`, `uv sync`, `uv run alembic init`
- **Output**: Project skeleton with `pyproject.toml`, `.gitignore`, `.python-version`

### Phase 2: Core Metering & Billing (Weeks 1-2)

- **Tools**: `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy` (strict)
- **Key Decisions**:
  - Per-1,000-unit micro-unit pricing (vs. per-million) for cleaner integer arithmetic
  - TRIALING/INCOMPLETE subscription status allows metering (business decision)
  - `canceled_at` column on Subscription model for future cancel tracking
  - `get_active_by_tenant()` expanded to include TRIALING/INCOMPLETE statuses
- **Bugs Fixed**:
  - `e.vaule → e.value` typo in `src/schemas/meter.py` validator error message
  - `get_active_by_tenant()` previously only returned ACTIVE status; expanded to ACTIVE|TRIALING|INCOMPLETE
  - `microunits_to_cents()` divides by 10,000 (not 1,000,000) for correct cent conversion
- **Output**: 84 unit tests passing, core API endpoints implemented

### Phase 3: Stripe Webhooks & Checkout (Week 3)

- **Tools**: `stripe` Python SDK, `httpx` for integration tests
- **Key Decisions**:
  - 8 Stripe webhook event types supported
  - Webhook idempotency via `UNIQUE` constraint on `(tenant_id, idempotency_key, usage_type)`
  - `StripeService` wraps all SDK calls; `verify_webhook_signature()` validates signatures
  - `checkout.session.completed` creates tenant + subscription; `stripe_customer_id` stored on Tenant
- **Bugs Fixed**:
  - Fixed `SubscriptionStatus` enum instead of string literals
  - Removed non-existent `subscription.payment_failed` attribute
  - Removed non-existent `subscription_repo.create()/update()` calls (added these methods)
  - Fixed subscription `plan_id` mapping from Stripe price IDs
- **Output**: 14 webhook integration tests passing (all 8 event types)

### Phase 4: Cost Calculation Engine (Week 4)

- **Tools**: `decimal` for integer arithmetic, `pytest` for deterministic tests
- **Key Decisions**:
  - Pricing configuration as immutable `@dataclass(frozen=True)` in `src/config/pricing.py`
  - Prices per 1,000 units (not per million) for cleaner math: API call = 1,000,000 µ-units/1K, input = 150/1K, cached = 75/1K (50% discount), output = 600/1K
  - `calculate_cost_microunits()` divides by 1,000 (not 1,000,000) since prices are now per-thousand
  - Billing rules engine: categories calculated independently, then summed; output+reasoning combined at output rate
  - Zero/negative `qty` rejected at Pydantic level (422); schema validator typo fixed
- **Bugs Fixed**:
  - `pricing.py` loaded from `settings` at module load (now uses `get_settings()` lazy)
  - `money.py` `calculate_cost_microunits()` formerly divided by 1,000,000; updated to 1,000
  - `cost_service.py` references updated to use new per-thousand pricing
  - `test_cost.py` and `test_money.py` updated with new per-1,000 unit expected values
- **Output**: 137 tests passing (84 unit + 33+ integration), 82% coverage

### Phase 5: Dockerization & Finalization (Week 5)

- **Tools**: `Dockerfile`, `docker-compose.yml`, `seed.py`, `capstone.yaml`, `demo.sh`
- **Key Decisions**:
  - `Dockerfile`: Python 3.11-slim + `uv` for fast dependency resolution; `apt-get install libpq-dev gcc` for psycopg2/bcrypt
  - `docker-compose.yml`: Services `postgres`, `redis`, `api`; health checks; `api` waits for postgres/redis
  - `seed.py`: Upserts Free/Pro plans, creates demo tenant, pre-fills usage to **exactly 1 slot away from FREE plan boundary** (4,999 / 5,000 API calls; ~499,999 / 500,000 tokens)
  - `capstone.yaml`: Manifest with `run`, `seed`, `test`, `docker`, `demo` commands
  - `demo.sh`: 6-minute demo script: idempotency → quota boundary → Stripe webhook → cost rollup
  - `README.md`: "Note" section added clarifying this is a demo, not a live application
- **Output**: Full containerized setup; `docker compose up --build` brings up all services; demo script works end-to-end

### Phase 6: Security & Quality Hardening (Post-audit)

- **Tools**: `hypothesis` for property-based testing, `re` for regex secret redaction
- **Key Changes**:
  - **Secret redaction**: Added `_redact()` function in `src/api/middleware/error_handling.py` that masks `sk_test_*`, `sk_live_*`, `whsec_*`, `password=*`, and `postgresql://user:pass@` patterns before logging or returning in error responses
  - **Property-based tests**: Added 2 new Hypothesis tests to `tests/unit/test_cost.py`:
    - `test_cost_never_exceeds_raw_product`: Cost is always non-negative for any valid quantity (100 examples)
    - `test_cost_monotonic_non_decreasing`: Cost increases monotonically with quantity (100 examples)
  - **Redaction tests**: Created `tests/unit/test_error_redaction.py` with 7 tests covering Stripe keys, DB URLs, passwords, and multiple secrets in one string
  - **Hypothesis test cleanup**: Removed `try/except ImportError` guard (Hypothesis is a declared dependency); changed decorator style from `@st.strategies.integers(...)` to `@given(quantity=st.integers(...))`
  - Fixed `test_cached_input_50_percent_discount` assertion: removed `(regular - cached) <= 1` which failed due to independent rounding of cached vs regular prices
- **Output**: 97 unit tests passing (up from 84), 7 new redaction tests + 2 new property-based tests

### Phase 7: Infrastructure, Performance & Test Coverage Expansion

- **Tools**: `redis`, `structlog`, `pytest-cov`, `alembic`
- **Key Changes**:
  - **Redis caching layer**: Created `src/config/cache.py` with tenant lookup caching (60s TTL), usage response caching (30s TTL), and idempotency key caching (24h TTL)
  - **Transient database retries**: Added `with_db_retry()` decorator for PostgreSQL connection errors and deadlocks with exponential backoff and jitter
  - **Rate limiting**: Implemented sliding-window rate limiting with fail-open Redis degradation
  - **Health routing**: Mounted `/health` and `/ready` endpoints in `create_app()`
  - **Comment cleanup**: Stripped AI-generated docstrings and redundant comments across all 32 `src/` files
  - **Concurrent test stabilization**: Rewrote `test_concurrent_metering.py` using direct `MeterService.record()` calls and DB-state assertions
  - **8 new test files**: Added tests for cache operations, health endpoints, DB retries, webhook dispatch, deps, logging, billing portal, and error redaction
- **Output**: 215 tests passing, coverage raised to 86%

### Phase 8: Gemini API Pricing Alignment Because i Frogot about it

- **Tools**: `pytest`, `hypothesis`
- **Key Changes**:
  - **Reasoning token calculation**: Refactored `CostService.calculate_token_breakdown()` to combine reasoning tokens with output tokens before multiplying by the output token rate: `(Input * Input Rate) + (Cached Input * Cached Rate) + ((Output + Reasoning) * Output Rate)`
  - **Dead code removal**: Deleted unused `calculate_output_and_reasoning_combined()` method
  - **Schema update**: Removed `reasoning_cost_cents` from `TokenBreakdown` schema (cost rolled into `output_cost_cents`), kept `reasoning_tokens` count
  - **Pinned unit test**: Added `test_gemini_formula_combined_output_and_reasoning` asserting exact Gemini formula math
- **Output**: 216 tests passing, 86% coverage

---

## Architectural Decisions

### Pricing Model

- **Per-1,000-unit micro-units** chosen over per-million for these reasons:
  - Avoids fractional micro-units (e.g., 62.5 µ-units/1K cached input → rounded to 75 µ-units after scaling)
  - Matches capstone spec: "prices per 1,000 tokens for different AI models"
  - Keeps `calculate_cost_microunits()` simple: `(quantity * price_per_thousand) / 1_000`
  - Maintains integer-only arithmetic throughout
- **Gemini pricing rules**:
  - Input: 150 µ-units / 1k
  - Cached input: 75 µ-units / 1k (50% discount)
  - Output & Reasoning: 600 µ-units / 1k (reasoning aggregated into output prior to rate application)

### Subscription Status Handling

- **ACTIVE**: Full metering allowed
- **TRIALING/INCOMPLETE**: Metering allowed (per business decision for demo)
- **PAST_DUE/CANCELED**: Metering blocked → HTTP 402 Payment Required
- **Why**: Supports the 6-minute demo flow while maintaining logical consistency

### Idempotency Design

- **Unique constraint**: `(tenant_id, idempotency_key, usage_type)` in `UsageEvent`
- **Middleware**: `IdempotencyMiddleware` validates UUID v4 format; rejects missing/invalid keys with HTTP 400
- **Service layer**: `MeterService.record()` checks quota first, then cost, then atomic record; on race condition, raises `QuotaExceededError` without writing

### Database Design

- **UUID primary keys** on all tables via `Base` declarative base
- **`created_at`/`updated_at`**: Server-default `func.now()`, timezone-aware
- **`UsageEvent`**: `cost_microunits` stored as `BigInteger`; never floats
- **`Subscription`**: `stripe_subscription_id` unique, `canceled_at` column for future use

---

## Bug Resolutions Summary

| Bug                                                   | File                                                  | Fix                                                                |
| ----------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------ |
| `e.vaule → e.value` typo                              | `src/schemas/meter.py`                                | Fixed validator error message                                      |
| `get_active_by_tenant()` status filter                | `src/repositories/subscription_repo.py`               | Expanded to ACTIVE\|TRIALING\|INCOMPLETE                           |
| `microunits_to_cents()` divisor                       | `src/utils/money.py`                                  | Changed from 1,000,000 to 10,000                                   |
| `calculate_cost_microunits()` divisor                 | `src/utils/money.py`                                  | Changed from 1,000,000 to 1,000 (prices now per-thousand)          |
| `pricing.py` module-level settings load               | `src/config/pricing.py`                               | Uses `get_settings()` lazy loading                                 |
| Test expected values                                  | `tests/unit/test_cost.py`, `tests/unit/test_money.py` | Updated for per-1,000 unit pricing                                 |
| `test_cost_cached_input_is_25_percent` → `50_percent` | `tests/unit/test_cost.py`                             | Fixed to reflect 50% discount correctly                            |
| Health router unmounted                               | `src/main.py`                                         | Added `app.include_router(health_router)`                          |
| Concurrent test flakiness                             | `tests/integration/test_concurrent_metering.py`       | Rewrote with direct `MeterService` calls and DB assertions         |
| Webhook mark_processed ordering                       | `src/api/v1/webhook.py`                               | Moved `mark_processed()` after successful event handling           |
| Gemini reasoning token cost separation                | `src/services/cost_service.py`, `src/api/v1/usage.py` | Aggregated reasoning into output tokens before rate multiplication |

---

## Tool Usage Summary

| Tool      | Purpose                                    | Count                       |
| --------- | ------------------------------------------ | --------------------------- |
| `uv`      | Dependency management, `uv sync`, `uv run` | 150+ invocations            |
| `pytest`  | Test execution                             | 216 tests active            |
| `ruff`    | Linting and code quality                   | Ongoing                     |
| `mypy`    | Static type checking                       | Strict mode, 0 errors       |
| `Docker`  | Containerization                           | `docker compose up --build` |
| `seed.py` | Database seeding                           | 1 run (idempotent)          |
| `demo.sh` | 6-minute demo script                       | 1 run                       |

---

## For Complete Honesty

Most of the tests from phase 4 and so on ai helped heavily in them.
Also i used AI but not mainly for:

1. Some guide on the structure of files because past big projects i made didn't have may money and heavy api requests it was mostly complex logic instead
2. The Final ReadME and some parts of the past ones
3. Recommendations on how to fix things especially for the seeding and some json requests
4. Stripe webhooks setup
5. Docker file because i still don't understand it
6. General debugging some new stuff i haven't used before like async sessions

**End of BUILDLOG.md**
