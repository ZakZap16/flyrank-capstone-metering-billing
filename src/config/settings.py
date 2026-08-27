from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PostgresDsn
from functools import lru_cache
import secrets



class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Usage Metering & Billing Engine"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    
    DATABASE_URL: PostgresDsn = Field(
        default="postgresql+asyncpg://app_user:dev_password@localhost:5432/metering_billing"
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 5
    
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1"]
    
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    
    STRIPE_API_KEY: str = Field(default="sk_test_...")
    STRIPE_WEBHOOK_SECRET: str = Field(default="whsec_...")
    STRIPE_PRICE_ID_PRO: str = Field(default="price_...")
    STRIPE_SUCCESS_URL: str = "http://localhost:3000/success"
    STRIPE_CANCEL_URL: str = "http://localhost:3000/cancel"
    
    PRICE_API_CALL_PER_MILLION: int = 100_000
    PRICE_INPUT_TOKEN_PER_MILLION: int = 250_000
    PRICE_CACHED_INPUT_TOKEN_PER_MILLION: int = 62_500
    PRICE_OUTPUT_TOKEN_PER_MILLION: int = 1_000_000
    PRICE_REASONING_TOKEN_PER_MILLION: int = 1_000_000
    
    FREE_PLAN_API_QUOTA: int = 5_000
    FREE_PLAN_TOKEN_QUOTA: int = 500_000
    PRO_PLAN_API_QUOTA: int = 100_000
    PRO_PLAN_TOKEN_QUOTA: int = 10_000_000
    PRO_PLAN_PRICE_CENTS: int = 4_900
    
    @property
    def is_test_stripe(self) -> bool:
        return self.STRIPE_API_KEY.startswith("sk_test_")
    
    def validate_stripe_test_mode(self) -> None:
        if not self.is_test_stripe:
            raise ValueError("STRIPE_API_KEY must be test mode (sk_test_)")

@lru_cache
def get_settings() -> Settings:
    return Settings()