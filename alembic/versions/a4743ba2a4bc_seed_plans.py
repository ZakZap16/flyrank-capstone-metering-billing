"""seed plans

Revision ID: a4743ba2a4bc
Revises: 3b17d2cce51c
Create Date: 2026-08-27 20:13:50.222113

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4743ba2a4bc'
down_revision: Union[str, Sequence[str], None] = '3b17d2cce51c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed Free and Pro plans."""
    plan_tier_enum = sa.Enum('FREE', 'PRO', name='plantier', native_enum=False)
    
    op.bulk_insert(
        sa.table(
            "plans",
            sa.column("id", plan_tier_enum),
            sa.column("name", sa.String),
            sa.column("api_call_quota", sa.BigInteger),
            sa.column("ai_token_quota", sa.BigInteger),
            sa.column("price_cents", sa.Integer),
            sa.column("stripe_price_id", sa.String),
            sa.column("is_active", sa.Boolean),
        ),
        [
            {
                "id": "FREE",
                "name": "Free",
                "api_call_quota": 5_000,
                "ai_token_quota": 500_000,
                "price_cents": 0,
                "stripe_price_id": None,
                "is_active": True,
            },
            {
                "id": "PRO",
                "name": "Pro",
                "api_call_quota": 100_000,
                "ai_token_quota": 10_000_000,
                "price_cents": 4_900,
                "stripe_price_id": "price_PRO_ID_FROM_STRIPE_DASHBOARD",
                "is_active": True,
            },
        ]
    )


def downgrade() -> None:
    """Remove seeded plans."""
    op.execute("DELETE FROM plans WHERE id IN ('FREE', 'PRO')")
