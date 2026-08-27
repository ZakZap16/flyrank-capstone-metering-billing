from sqlalchemy import String, BigInteger, Integer, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base
import enum

class PlanTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"

class Plan(Base):
    __tablename__ = "plans"
    
    id: Mapped[PlanTier] = mapped_column(
        SQLEnum(PlanTier, native_enum=False), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    api_call_quota: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ai_token_quota: Mapped[int] = mapped_column(BigInteger, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)