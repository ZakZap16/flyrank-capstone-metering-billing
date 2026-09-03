# Flyrank Capstone Metering & Billing Engine

Backend capstone project for FlyRank Internship — Usage Metering & Billing Engine.

## Current Status: Phase 2 Complete

- Python 3.11 + FastAPI project initialized with `uv`
- Dependencies: FastAPI, SQLAlchemy[asyncio], asyncpg, Alembic, Pydantic v2, Stripe, httpx
- Dev tools: pytest, pytest-asyncio, pytest-cov, ruff, mypy (strict), pre-commit
- PostgreSQL 16 via Docker Compose with init script (uuid-ossp, pgcrypto)
- Alembic configured with sync driver (psycopg2) for migrations
- Environment template (.env.example) with all required variables

## Phase 2: API Endpoints, Services & Test Suite

### API Endpoints (`/api/v1`)

| Endpoint    | Method | Description                                 |
| ----------- | ------ | ------------------------------------------- |
| `/meter`    | POST   | Record API usage events (idempotency-keyed) |
| `/usage`    | GET    | Get current usage and quota breakdown       |
| `/auth/key` | POST   | Generate a new API key for a tenant         |

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

- **6 integration tests** — real Postgres, full request flow (idempotency, quota enforcement, payment required)
- **65 unit tests** — mocked deps, isolated logic (auth, quota, cost, money, rate limit, idempotency, meter service)
- **89% code coverage** (>= 80% target)

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

# If want to run tests
# 5. Run tests
uv run pytest tests/ --cov=src --cov-report=term-missing
# Expected: 71 passed, 89% coverage

# 6. Start the server
uv run uvicorn src.main:app --reload
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

## Project Structure

```
.
├── .env.example          # Environment template
├── .gitignore
├── .python-version       # 3.11
├── alembic.ini           # Alembic config (psycopg2 driver)
├── alembic/              # Migration directory
│   └── versions/         # Versioned migrations
├── docker-compose.yml    # PostgreSQL 16
├── pyproject.toml        # Project config + deps
├── README.md
├── scripts/
│   └── init.sql          # DB init (extensions, roles)
├── src/
│   ├── api/
│   │   ├── deps.py           # FastAPI dependency injection
│   │   ├── main.py           # App factory (middleware stack)
│   │   ├── middleware/
│   │   │   ├── auth.py           # X-Tenant-ID auth
│   │   │   ├── error_handling.py # Global error handler
│   │   │   ├── idempotency.py    # Idempotency-Key validation
│   │   │   └── rate_limit.py     # Sliding window rate limiter
│   │   └── v1/
│   │       ├── auth.py       # POST /api/v1/auth/key
│   │       ├── meter.py      # POST /api/v1/meter
│   │       └── usage.py      # GET /api/v1/usage
│   ├── config/
│   │   ├── database.py   # Async engine + session factory
│   │   ├── pricing.py    # Micro-unit pricing constants
│   │   └── settings.py   # Pydantic Settings (Stripe validated)
│   ├── models/
│   │   ├── base.py          # SQLAlchemy declarative base
│   │   ├── plan.py          # Plan model + PlanTier enum
│   │   ├── stripe_event.py  # ProcessedStripeEvent model
│   │   ├── subscription.py  # Subscription model
│   │   ├── tenant.py        # Tenant model
│   │   └── usage_event.py   # UsageEvent model
│   ├── repositories/
│   │   ├── plan_repo.py         # Plan queries
│   │   ├── subscription_repo.py # Subscription CRUD
│   │   ├── tenant_repo.py       # Tenant CRUD
│   │   └── usage_repo.py        # Usage recording + monthly breakdown
│   ├── schemas/
│   │   ├── auth.py   # AuthRequest, AuthResponse
│   │   ├── meter.py  # MeterRequest, MeterResponse, QuotaExceededError, PaymentRequiredError
│   │   └── usage.py  # UsageResponse, QuotaBreakdown
│   └── services/
│       ├── auth_service.py   # API key generation (bcrypt)
│       ├── cost_service.py   # Micro-unit cost calculation
│       ├── meter_service.py  # Usage recording + quota enforcement
│       └── quota_service.py  # Quota checks + subscription state
├── tests/
│   ├── conftest.py              # Fixtures (async_session, client, test_tenant, auth_headers)
│   ├── integration/
│   │   └── test_metering.py     # 6 integration tests
│   └── unit/
│       ├── test_auth.py             # 7 tests
│       ├── test_auth_service.py     # 10 tests
│       ├── test_cost.py             # 7 tests
│       ├── test_idempotency.py      # 7 tests
│       ├── test_meter_service.py    # 7 tests
│       ├── test_money.py            # 7 tests
│       ├── test_quota_service.py    # 13 tests
│       └── test_rate_limit.py       # 8 tests
└── uv.lock               # Locked dependencies

Next: Phase 3
Stripe webhook integration, payment intent handling, subscription management.
```
