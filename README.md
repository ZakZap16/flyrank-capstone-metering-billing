# flyrank-capstone-metering-billing

**A production-grade, multi-tenant usage metering and billing engine — built for AI-native SaaS.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-215%20passing-brightgreen)](#testing)
[![Coverage](https://img.shields.io/badge/coverage-86%25-brightgreen)](#testing)

---

## What This System Does

Flyrank Capstone Metering Billing is a backend service that handles **real-time usage tracking, quota enforcement, and Stripe-integrated billing** for multi-tenant SaaS applications — specifically designed for AI-powered products that consume API calls and LLM tokens.

### Core Capabilities

- **Idempotent metering** — Every usage event carries an `Idempotency-Key` header. Duplicate requests within a 24-hour window return the cached response without double-counting. Atomic database inserts with `ON CONFLICT DO NOTHING` provide a second safety net.

- **Hard quota enforcement** — Monthly quotas are checked before recording. When a tenant exhausts their plan quota, subsequent requests receive **`429 Too Many Requests`** with `Retry-After: 86400` headers. No soft limits, no grace periods — the boundary is absolute.

- **Subscription-aware gating** — Only `ACTIVE`, `TRIALING`, or `INCOMPLETE` subscriptions can meter usage. `PAST_DUE` and `CANCELED` subscriptions receive **`402 Payment Required`** immediately.

- **Integer-cent cost calculation** — All monetary values use **integer microunits** (1/1,000,000 of a currency unit). No floating-point arithmetic, no rounding errors. Five token categories have distinct per-1,000-unit prices:

  | Usage Type          | Price (microunits / 1k units) |
  | ------------------- | ----------------------------- |
  | API Calls           | 1,000,000                     |
  | Input Tokens        | 150                           |
  | Cached Input Tokens | 75                            |
  | Output Tokens       | 600                           |
  | Reasoning Tokens    | 600                           |

- **Stripe webhook synchronization** — Webhook events (`checkout.session.completed`, `invoice.paid`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`) are verified via signature validation, deduplicated against a `processed_stripe_events` table, and dispatched to internal handlers that update subscription state.

- **Redis-backed caching and rate limiting** — Tenant lookups cached 60s, usage rollups cached 30s, idempotency keys cached 24h. Sliding-window rate limiter at 100k requests/60s with fail-open degradation.

- **Zero-cost free stack** — PostgreSQL 16, Redis 7, and FastAPI. No paid infrastructure required. Stripe operates exclusively in test mode.

---

## Architecture

```
                          ┌─────────────────────────────────────────┐
                          │              Client (cURL)              │
                          └──────────────────┬──────────────────────┘
                                             │
                              POST /api/v1/meter
                              Header: X-Tenant-ID
                              Header: Idempotency-Key
                                             │
                                             ▼
                          ┌──────────────────────────────────────────┐
                          │             FastAPI Application          │
                          │   ┌──────────────────────────────────┐   │
                          │   │         Middleware Stack         │   │
                          │   │  RequestID → RateLimit → Auth    │   │
                          │   └──────────────┬───────────────────┘   │
                          │                  │                       │
                          │                  ▼                       │
                          │   ┌──────────────────────────────────┐   │
                          │   │      MeterService.record()       │   │
                          │   │                                  │   │
                          │   │  1. Check idempotency (Redis)    │   │
                          │   │  2. Verify subscription status   │   │
                          │   │  3. Check quota (monthly usage)  │   │
                          │   │  4. Calculate cost (integer)     │   │
                          │   │  5. Insert event (atomic)        │   │
                          │   │  6. Store idempotency response   │   │
                          │   └──────────────┬───────────────────┘   │
                          │                  │                       │
                          │         ┌────────┴────────┐              │
                          │         ▼                  ▼             │
                          │   ┌───────────┐    ┌───────────┐         │
                          │   │ PostgreSQL│    │   Redis   │         │
                          │   │  (async)  │    │ (cache/   │         │
                          │   │           │    │  idempot.)│         │
                          │   └───────────┘    └───────────┘         │
                          └───────────────────┬──────────────────────┘
                                              │
                                             │  POST /api/v1/webhooks/stripe
                                             │  (Stripe CLI → localhost)
                                             ▼
                          ┌──────────────────────────────────────────┐
                          │           Stripe Webhook Handler         │
                          │                                          │
                          │  1. Verify signature (whsec_*)           │
                          │  2. Check processed_stripe_events        │
                          │  3. Dispatch to handler:                 │
                          │     ├─ checkout.session.completed        │
                          │     ├─ invoice.paid                      │
                          │     ├─ customer.subscription.updated     │
                          │     ├─ customer.subscription.deleted     │
                          │     └─ invoice.payment_failed            │
                          │  4. Mark event as processed              │
                          └──────────────────────────────────────────┘
```

**Data flow summary:**

1. **Metering path** (synchronous): Client → Middleware → `MeterService` → quota check → cost calculation → atomic insert → 200 OK (or 429/402)
2. **Webhook path** (asynchronous): Stripe CLI → signature verification → deduplication → handler → subscription state update → cache invalidation
3. **Read path** (cached): Client → `/usage` endpoint → Redis cache check → usage rollup query → 30s cached response

---

## Tech Stack

| Layer                  | Technology                                     |
| ---------------------- | ---------------------------------------------- |
| **Runtime**            | Python 3.11+                                   |
| **Framework**          | FastAPI 0.110+                                 |
| **ORM**                | SQLAlchemy 2.0 (async)                         |
| **Database**           | PostgreSQL 16 (Alpine)                         |
| **Cache / Rate Limit** | Redis 7 (Alpine)                               |
| **Migrations**         | Alembic                                        |
| **Validation**         | Pydantic v2 + Pydantic Settings                |
| **Payments**           | Stripe SDK 7.0+ (test mode)                    |
| **Logging**            | structlog (JSON structured)                    |
| **Container**          | Docker + Docker Compose                        |
| **Package Mgmt**       | uv (Astral)                                    |
| **Testing**            | pytest, pytest-asyncio, pytest-cov, Hypothesis |
| **Linting**            | Ruff, mypy (strict)                            |

---

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2
- [Stripe CLI](https://docs.stripe.com/stripe-cli) (`stripe` binary)
- [Python 3.11+](https://www.python.org/downloads/) (for seeding and testing only)

### 1. Clone and configure

```bash
git clone https://github.com/your-org/flyrank-capstone-metering-billing.git
cd flyrank-capstone-metering-billing

cp .env.example .env
# Edit .env with your Stripe test keys (or leave placeholders for offline testing)
```

### 2. Boot the system

```bash
docker compose up --build
```

This starts three containers:

| Service    | Port | Purpose                                          |
| ---------- | ---- | ------------------------------------------------ |
| `postgres` | 5432 | PostgreSQL 16 with `metering_billing` database   |
| `redis`    | 6379 | Cache, idempotency keys, rate limiting           |
| `api`      | 8000 | FastAPI application (http://localhost:8000/docs) |

### 3. Run migrations

```bash
docker compose exec api alembic upgrade head
```

### 4. Seed demo data

```bash
docker compose exec api python seed.py
```

Output:

```
Seeding plans...
Seeding demo tenant...
Seeding usage events (FREE plan boundary: 5000 API calls, 500000 tokens)...
  Inserted 4999 usage events for tenant <UUID>
  API calls used: 4999 / 5000 (1 remaining)
  Token quota: ~499999 / 500000 (1 remaining)

Demo credentials:
  Tenant ID: <UUID>
  X-Tenant-ID: <UUID>
  Idempotency-Key: <any UUID v4>
```

The seed pre-fills **4,999 API calls** and **~499,999 tokens** — exactly one unit below the FREE plan boundary. This lets you immediately test quota enforcement.

### 5. (Optional) Forward Stripe webhooks

```bash
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
```

Copy the `whsec_...` signing secret from the CLI output into your `.env` as `STRIPE_WEBHOOK_SECRET`.

---

## Usage

All requests require the `X-Tenant-ID` header. The seed script outputs a `Tenant ID` to use.

### Record usage (billable endpoint)

```bash
curl -X POST http://localhost:8000/api/v1/meter \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: <TENANT_ID>" \
  -H "Idempotency-Key: $(python -c 'import uuid; print(uuid.uuid4())')" \
  -d '{"usage_type": "api_call", "qty": 1}'
```

**Success (200 OK):**

```json
{
	"recorded": true,
	"usage_event_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
	"usage_type": "api_call",
	"quantity": 1,
	"cost_microunits": 1000,
	"remaining_quota": {
		"api_calls": 4998,
		"ai_tokens": 0
	}
}
```

### Quota exceeded (429)

When the tenant exhausts their monthly quota:

```json
{
	"detail": {
		"error": "quota_exceeded",
		"message": "Quota exceeded for api_call:used=5000, limit=5000, reqested=1",
		"usage_type": "api_call",
		"used": 5000,
		"limit": 5000,
		"requested": 1,
		"retry_after_seconds": 86400
	}
}
```

### Payment required (402)

For `PAST_DUE` or `CANCELED` subscriptions:

```json
{
	"detail": {
		"error": "payment_required",
		"message": "Subscription past due - payment required"
	}
}
```

### Query usage rollup

```bash
curl http://localhost:8000/api/v1/usage \
  -H "X-Tenant-ID: <TENANT_ID>"
```

```json
{
	"period": {
		"start": "2026-09-01T00:00:00+00:00",
		"end": "2026-10-01T00:00:00+00:00"
	},
	"plan": "Free",
	"api_calls": {
		"used": 5000,
		"limit": 5000,
		"remaining": 0,
		"cost_cents": 5000
	},
	"ai_tokens": {
		"used": 499999,
		"limit": 500000,
		"remaining": 1,
		"cost_cents": 75,
		"breakdown": {
			"input_tokens": 124999,
			"cached_input_tokens": 125000,
			"output_tokens": 125000,
			"reasoning_tokens": 125000,
			"input_cost_cents": 19,
			"cached_input_cost_cents": 9,
			"output_cost_cents": 75,
			"reasoning_cost_cents": 75
		}
	},
	"total_cost_cents": 5075
}
```

### Idempotent replay

Replaying the same request with the same `Idempotency-Key` returns the cached response without double-counting:

```bash
# Replay with the exact same Idempotency-Key — same response, no new event created
curl -X POST http://localhost:8000/api/v1/meter \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: <TENANT_ID>" \
  -H "Idempotency-Key: <SAME_UUID>" \
  -d '{"usage_type": "api_call", "qty": 1}'
```

---

## Testing

```bash
# Run full test suite (215 tests)
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

**Coverage summary:**

| Module                 | Coverage |
| ---------------------- | -------- |
| `cache.py`             | 100%     |
| `logging.py`           | 100%     |
| `idempotency.py`       | 100%     |
| `request_id.py`        | 100%     |
| `meter.py`             | 100%     |
| `pricing.py`           | 100%     |
| `meter_service.py`     | 100%     |
| `stripe_service.py`    | 100%     |
| `auth.py` (middleware) | 92%      |
| `rate_limit.py`        | 94%      |
| **Overall**            | **86%**  |

Test categories: unit tests (mocked dependencies), integration tests (async SQLAlchemy + Redis), Hypothesis property-based tests, and concurrent metering safety tests.

---

## Honest Limitations

This system is a **capstone project**, not a production billing platform. The following are known constraints:

- **Stripe test mode only** — No live payment processing. `sk_test_` keys are required; the app validates test mode on startup and rejects `sk_live_` keys.

- **No overage billing** — When monthly quota is exhausted, requests are rejected (429). There is no mechanism to charge for overages, bill incrementally, or offer quota top-ups.

- **No proration** — Plan upgrades/downgrades do not calculate partial-period charges. The system relies on Stripe's native proration when handling subscription changes via Checkout or Customer Portal.

- **Simulated AI token metering** — Token counts (`input_tokens`, `output_tokens`, etc.) are client-reported values. The system validates that quantities are positive integers within bounds (1–10M) but does not independently verify token counts against an LLM provider.

- **Single billing period** — Quotas reset monthly based on the first day of the UTC month. There is no custom billing cycle support.

- **No invoice generation** — Cost calculations are in-memory rollups. The system does not generate or store invoices — that responsibility is delegated to Stripe.

- **Flat quota model** — All tenants on the same plan share identical quota limits. There is no per-tenant quota override or enterprise tier system.

- **No webhook retry queue** — Failed webhook processing is logged but not retried. In production, this would require a dead-letter queue and retry scheduler.

---

## Project Structure

```
src/
├── api/
│   ├── deps.py                    # FastAPI dependency injection
│   ├── health.py                  # /health and /ready endpoints
│   ├── middleware/
│   │   ├── auth.py                # Tenant authentication + Redis caching
│   │   ├── error_handling.py      # Global exception handlers + secret redaction
│   │   ├── idempotency.py         # UUID v4 validation
│   │   ├── rate_limit.py          # Redis sliding-window rate limiter
│   │   └── request_id.py          # X-Request-ID injection
│   └── v1/
│       ├── meter.py               # POST /api/v1/meter — core billable endpoint
│       ├── usage.py               # GET /api/v1/usage — monthly rollup
│       ├── auth.py                # POST /api/v1/auth — tenant creation
│       ├── billing.py             # POST /api/v1/billing/portal — Stripe portal
│       ├── checkout.py            # POST /api/v1/checkout — Stripe Checkout Session
│       ├── subscription.py        # GET /api/v1/subscription — status query
│       └── webhook.py             # POST /api/v1/webhooks/stripe — Stripe event handler
├── config/
│   ├── cache.py                   # Redis pool, cache ops, idempotency helpers
│   ├── database.py                # Async engine, session, retry logic
│   ├── logging.py                 # structlog JSON configuration
│   ├── pricing.py                 # Frozen PricingConfig dataclass
│   └── settings.py                # Pydantic Settings (env-driven)
├── models/
│   ├── base.py                    # Declarative base + timestamp mixin
│   ├── plan.py                    # Plan tiers (FREE / PRO)
│   ├── tenant.py                  # Multi-tenant identity
│   ├── subscription.py            # Stripe-linked subscription state
│   ├── usage_event.py             # Metered usage records
│   └── stripe_event.py            # Webhook deduplication log
├── repositories/
│   ├── usage_repo.py              # Atomic inserts, monthly aggregation
│   ├── subscription_repo.py       # Active subscription lookup
│   ├── plan_repo.py               # Plan retrieval
│   ├── stripe_event_repo.py       # Event deduplication
│   └── tenant_repo.py             # Tenant CRUD
├── schemas/
│   ├── meter.py                   # Request/response models + error types
│   ├── usage.py                   # Usage rollup response
│   ├── auth.py                    # Tenant creation schema
│   └── checkout.py                # Checkout session schema
├── services/
│   ├── meter_service.py           # Core recording logic (quota → cost → insert)
│   ├── quota_service.py           # Monthly quota enforcement
│   ├── cost_service.py            # Integer-cent cost calculation
│   ├── auth_service.py            # API key hashing (bcrypt + LRU cache)
│   └── stripe_service.py          # Stripe API wrapper
├── utils/
│   └── money.py                   # Microunit ↔ cent conversions
└── main.py                        # App factory + lifespan
```

---

## License

[MIT](LICENSE)
