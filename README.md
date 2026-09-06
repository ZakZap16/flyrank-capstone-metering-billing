# Flyrank Capstone Metering & Billing Engine

Backend capstone project for FlyRank Internship — Usage Metering & Billing Engine.

## Current Status: Phase 3 Complete

- Python 3.11 + FastAPI project initialized with `uv`
- Dependencies: FastAPI, SQLAlchemy[asyncio], asyncpg, Alembic, Pydantic v2, Stripe, httpx
- Dev tools: pytest, pytest-asyncio, pytest-cov, ruff, mypy (strict), pre-commit
- PostgreSQL 16 via Docker Compose with init script (uuid-ossp, pgcrypto)
- Alembic configured with sync driver (psycopg2) for migrations
- Environment template (.env.example) with all required variables

## Phase 3: Stripe Webhooks, Checkout, Billing Portal, Subscription Cancel

### API Endpoints (`/api/v1`)

| Endpoint                    | Method | Description                                               |
| --------------------------- | ------ | --------------------------------------------------------- |
| `/meter`                    | POST   | Record API usage events (idempotency-keyed)               |
| `/usage`                    | GET    | Get current usage and quota breakdown                       |
| `/auth/key`                 | POST   | Generate a new API key for a tenant                       |
| `/checkout/session`         | POST   | Create a Stripe checkout session for plan subscription       |
| `/billing/portal`           | POST   | Create a Stripe billing portal session                     |
| `/subscriptions/cancel`    | POST   | Cancel a tenant's subscription                             |
| `/webhook/stripe`           | POST   | Stripe webhook receiver (8 event types)                   |

### Stripe Webhook Event Types Supported
- `checkout.session.completed`
- `invoice.payment_succeeded`
- `invoice.payment_failed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `customer.subscription.trial_will_end`
- `invoice.upcoming`

### Middleware
- **Rate limiting** — 100k requests/minute per tenant (in-memory, SlidingWindow)
- **Idempotency** — UUID v4 `Idempotency-Key` header required on `/meter` POST
- **Auth** — `X-Tenant-ID` header on all endpoints; optional `X-API-Key` verification
- **Error handling** — Global handler for `QuotaExceededError`, `PaymentRequiredError`, `HTTPException`

### Pricing (Micro-Units, Integer-Only)
| Usage Type          | Price per Unit            |
| ------------------- | ------------------------- |
| API call            | $0.001 (1,000 calls = $1) |
| Input tokens        | $0.15 / 1M tokens         |
| Cached input tokens | 50% discount              |
| Output tokens       | $0.60 / 1M tokens         |
| Reasoning tokens    | Priced as output          |

### Plan Quotas
| Plan | API Calls | Input Tokens | Output Tokens |
| ---- | --------- | ------------ | ------------- |
| FREE | 10,000    | 1,000,000    | 500,000       |
| PRO  | 100,000   | 10,000,000   | 5,000,000     |

### Test Coverage
- **115 integration tests** — real Postgres, full request flow (8 event types + idempotency + signature validation + error paths)
- **70 unit tests** — mocked deps, isolated logic (auth, quota, cost, money, rate limit, idempotency, Stripe service, meter service, webhook helpers)
- **82% code coverage** (>= 80% target)

## Quick Start

```bash
# 1. Copy environment template
cp .env.example .env
# Edit .env with your Stripe test keys (when ready)

# 2. Start PostgreSQL
docker compose up -d

# 3. Install dependencies
uv sync

# 4. Run migrations
uv run alembic upgrade head

# 5. Run tests
uv run pytest tests/ --cov=src --cov-report=term-missing
# Expected: 115 passed, 82% coverage

# 6. Start the server
uv run uvicorn src.main:app --reload
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

## Project Structure
.
├── .env.example
├── .gitignore
├── .python-version
├── alembic.ini
├── alembic/
│   └── versions/
├── docker-compose.yml
├── pyproject.toml
├── README.md
├── scripts/
│   └── init.sql
├── src/
│   ├── api/
│   │   ├── deps.py
│   │   ├── main.py
│   │   ├── middleware/
│   │   │   ├── auth.py
│   │   │   ├── error_handling.py
│   │   │   ├── idempotency.py
│   │   │   └── rate_limit.py
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── billing.py
│   │       ├── checkout.py
│   │       ├── meter.py
│   │       ├── subscription.py
│   │       ├── usage.py
│   │       └── webhook.py
│   ├── config/
│   │   ├── database.py
│   │   ├── pricing.py
│   │   └── settings.py
│   ├── models/
│   │   ├── base.py
│   │   ├── plan.py
│   │   ├── stripe_event.py
│   │   ├── subscription.py
│   │   ├── tenant.py
│   │   └── usage_event.py
│   ├── repositories/
│   │   ├── plan_repo.py
│   │   ├── stripe_event_repo.py
│   │   ├── subscription_repo.py
│   │   ├── tenant_repo.py
│   │   └── usage_repo.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── billing.py
│   │   ├── checkout.py
│   │   ├── meter.py
│   │   └── usage.py
│   └── services/
│       ├── auth_service.py
│       ├── billing_service.py
│       ├── cost_service.py
│       ├── meter_service.py
│       ├── quota_service.py
│       └── stripe_service.py
├── tests/
│   ├── conftest.py
│   ├── integration/
│   │   ├── test_checkout.py
│   │   ├── test_metering.py
│   │   ├── test_phase3_endpoints.py
│   │   └── test_webhooks.py
│   └── unit/
│       ├── test_auth.py
│       ├── test_auth_service.py
│       ├── test_billing_service.py
│       ├── test_cost.py
│       ├── test_checkout.py
│       ├── test_idempotency.py
│       ├── test_meter_service.py
│       ├── test_money.py
│       ├── test_quota_service.py
│       ├── test_rate_limit.py
│       ├── test_stripe_service.py
│       └── test_webhook_helpers.py
└── uv.lock

Next: Phase 4
Expand Stripe integrations with refunds, discounts, subscription items,
customers with multiple subscriptions, and tax calculations.