#!/usr/bin/env python3
"""Seed script: populates plans, creates demo tenant, and pre-fills usage to boundary.

Run AFTER migrations: python seed.py
"""
import asyncio
import uuid
import sys
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text


DATABASE_URL = "postgresql+asyncpg://app_user:dev_password@localhost:5432/metering_billing"

FREE_API_QUOTA = 5_000
FREE_TOKEN_QUOTA = 500_000

async def seed():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("Seeding plans...")

        await db.execute(text("""
            INSERT INTO plans (id, name, api_call_quota, ai_token_quota, price_cents, is_active)
            VALUES
                ('FREE', 'Free Plan', :free_api, :free_token, 0, true),
                ('PRO',  'Pro Plan',  :pro_api,  :pro_token, 4900, true)
            ON CONFLICT (id) DO UPDATE SET
                name          = EXCLUDED.name,
                api_call_quota = EXCLUDED.api_call_quota,
                ai_token_quota  = EXCLUDED.ai_token_quota,
                price_cents     = EXCLUDED.price_cents,
                is_active       = EXCLUDED.is_active
        """), {
            "free_api": FREE_API_QUOTA,
            "free_token": FREE_TOKEN_QUOTA,
            "pro_api": 100_000,
            "pro_token": 10_000_000,
        })

        print("Seeding demo tenant...")

        tenant_id = uuid.uuid4()

        await db.execute(text("""
            INSERT INTO tenants (id, name, email, api_key_hash, created_at, updated_at)
            VALUES (:id, :name, :email, :hash, NOW(), NOW())
            ON CONFLICT DO NOTHING
        """), {
            "id": str(tenant_id),
            "name": "Demo User",
            "email": "demo@flyrank.test",
            "hash": "demo_key_hash_not_for_production",
        })

        await db.execute(text("""
            INSERT INTO subscriptions (
                id, tenant_id, plan_id, status,
                current_period_start, current_period_end,
                cancel_at_period_end, created_at, updated_at
            )
            VALUES (:id, :tid, 'FREE', 'active', NOW(), NOW() + INTERVAL '1 month', false, NOW(), NOW())
            ON CONFLICT (tenant_id) DO UPDATE SET
                plan_id              = EXCLUDED.plan_id,
                status              = EXCLUDED.status,
                current_period_end  = EXCLUDED.current_period_end,
                updated_at          = NOW()
        """), {"id": str(uuid.uuid4()), "tid": str(tenant_id)})

        await db.commit()

        print(f"Seeding usage events (FREE plan boundary: {FREE_API_QUOTA} API calls, {FREE_TOKEN_QUOTA} tokens)...")

        api_calls_to_insert = FREE_API_QUOTA - 1
        token_batches = 10
        tokens_per_batch = (FREE_TOKEN_QUOTA - 1) // token_batches

        now = datetime.now(timezone.utc)

        for i in range(api_calls_to_insert):
            await db.execute(text("""
                INSERT INTO usage_events
                    (id, tenant_id, idempotency_key, usage_type, quantity,
                     cost_microunits, created_at, updated_at)
                VALUES
                    (:id, :tid, :key, 'api_call', 1, 1000, :now, :now)
                ON CONFLICT DO NOTHING
            """), {
                "id": str(uuid.uuid4()),
                "tid": str(tenant_id),
                "key": f"seed-api-{i}",
                "now": now,
            })

        await db.commit()

        for batch in range(token_batches):
            for j in range(tokens_per_batch):
                await db.execute(text("""
                    INSERT INTO usage_events
                        (id, tenant_id, idempotency_key, usage_type, quantity,
                         cost_microunits, created_at, updated_at)
                    VALUES
                        (:id, :tid, :key, :utype, :qty, :cost, :now, :now)
                    ON CONFLICT DO NOTHING
                """), {
                    "id": str(uuid.uuid4()),
                    "tid": str(tenant_id),
                    "key": f"seed-token-{batch}-{j}",
                    "utype": ["input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens"][batch % 4],
                    "qty": 100,
                    "cost": 15 if batch % 4 == 0 else 7,
                    "now": now,
                })

        await db.commit()

        result = await db.execute(text("SELECT COUNT(*) FROM usage_events WHERE tenant_id = :tid"), {"tid": str(tenant_id)})
        count = result.scalar_one()
        print(f"  Inserted {count} usage events for tenant {tenant_id}")
        print(f"  API calls used: {api_calls_to_insert} / {FREE_API_QUOTA} (1 remaining)")
        print(f"  Token quota: ~{FREE_TOKEN_QUOTA - 1} / {FREE_TOKEN_QUOTA} (1 remaining)")

        print("\nDemo credentials:")
        print(f"  Tenant ID: {tenant_id}")
        print(f"  X-Tenant-ID: {tenant_id}")
        print(f"  Idempotency-Key: <any UUID v4>")
        print(f"\nOne API call remaining in FREE plan quota.")
        print(f"Run the demo script to exercise the system.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
