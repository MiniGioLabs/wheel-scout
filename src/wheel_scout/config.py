"""Wheel Scout configuration — loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Schwab API ---
    SCHWAB_APP_KEY: str = ""
    SCHWAB_SECRET: str = ""
    SCHWAB_CALLBACK_URL: str = "https://127.0.0.1:8182"

    # --- Alpaca API ---
    ALPACA_API_KEY: str = ""
    ALPACA_SECRET_KEY: str = ""
    ALPACA_PAPER: bool = True  # Use paper trading endpoint

    # --- Discord ---
    DISCORD_WEBHOOK_URL: str = ""

    # --- Scanner ---
    DTE_MIN: int = 21
    DTE_MAX: int = 35
    MIN_ANNUALIZED_RETURN: float = 15.0
    MIN_PREMIUM: float = 0.30
    MIN_DELTA: float = 0.20
    MAX_DELTA: float = 0.30
    MAX_BID_ASK_SPREAD_PCT: float = 0.05
    MIN_OPEN_INTEREST: int = 100
    MIN_AVG_VOLUME: int = 500_000
    MIN_STOCK_PRICE: float = 10.0
    MAX_STOCK_PRICE: float = 200.0

    # --- Scheduler ---
    SCAN_SCHEDULE_CRON: str = "0 8 * * 1-5"  # Mon-Fri 8 AM ET
    SCAN_TIMEZONE: str = "US/Eastern"
    CANDIDATE_LIMIT: int = 10

    @property
    def schwab_configured(self) -> bool:
        return bool(self.SCHWAB_APP_KEY and self.SCHWAB_SECRET)

    @property
    def alpaca_configured(self) -> bool:
        return bool(self.ALPACA_API_KEY and self.ALPACA_SECRET_KEY)

    @property
    def discord_configured(self) -> bool:
        return bool(self.DISCORD_WEBHOOK_URL)


settings = Settings()
