# Flyrank capstone Betering & Billing Engine

Backend capstone project for FlyRank Internship — Usage Metering & Billing Engine.

## Current Status: Phase 0 Complete

- Python 3.11 + FastAPI project initialized with `uv`
- Dependencies: FastAPI, SQLAlchemy[asyncio], asyncpg, Alembic, Pydantic v2, Stripe, httpx
- Dev tools: pytest, pytest-asyncio, ruff, mypy (strict), pre-commit
- PostgreSQL 16 via Docker Compose with init script (uuid-ossp, pgcrypto)
- Alembic configured with sync driver (psycopg2) for migrations
- Environment template (.env.example) with all required variables

## Quick Start (Current)

```bash
# 1. Copy environment template
cp .env.example .env
# Edit .env with your Stripe test keys (when ready)

# 2. Start PostgreSQL
docker compose up -d

# 3. Install dependencies
uv sync

# 4. Verify Alembic works
uv run alembic current
# Output: Current revision for postgresql+psycopg2://...: <none>
Project Structure (Current)
.
├── .env.example          # Environment template
├── .gitignore
├── .python-version       # 3.11
├── alembic.ini           # Alembic config (psycopg2 driver)
├── alembic/              # Migration directory (empty)
├── docker-compose.yml    # PostgreSQL 16
├── pyproject.toml        # Project config + deps
├── README.md
├── scripts/
│   └── init.sql          # DB init (extensions, roles)
└── uv.lock               # Locked dependencies
Next: Phase 1
Database schema, SQLAlchemy models, and initial migration.
```
