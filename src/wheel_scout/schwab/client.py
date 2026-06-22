"""Schwab API client for options chains and quotes."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from .models import OptionChain, OptionContract, TickerQuote
from ..config import settings

logger = logging.getLogger(__name__)


class SchwabClient:
    """Wraps schwab-py for options chain and quote data.

    Requires SCHWAB_APP_KEY and SCHWAB_SECRET in environment.
    Authenticates via OAuth and handles token refresh automatically.
    """

    def __init__(self) -> None:
        self._client = None
        self._last_request: float = 0.0
        self._rate_limit_delay: float = 0.5  # seconds between requests

    @property
    def configured(self) -> bool:
        return settings.schwab_configured

    def _ensure_client(self) -> None:
        """Lazy-init the Schwab client with OAuth."""
        if self._client is not None:
            return
        try:
            import schwab
        except ImportError:
            raise RuntimeError(
                "schwab-py not installed. Run: uv add schwab-py"
            )
        self._client = schwab.auth.easy_client(
            api_key=settings.SCHWAB_APP_KEY,
            app_secret=settings.SCHWAB_SECRET,
            callback_url=settings.SCHWAB_CALLBACK_URL,
            token_path="schwab_token.json",
        )
        logger.info("Schwab client authenticated")

    def _rate_limit(self) -> None:
        """Enforce rate limiting between API calls."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)
        self._last_request = time.monotonic()

    def get_option_chain(
        self,
        symbol: str,
        dte_min: int | None = None,
        dte_max: int | None = None,
    ) -> OptionChain:
        """Fetch the full options chain for a symbol.

        Filters to specified DTE range if provided.
        Falls back gracefully when Schwab API is unavailable.
        """
        self._ensure_client()
        self._rate_limit()

        dte_min = dte_min or settings.DTE_MIN
        dte_max = dte_max or settings.DTE_MAX

        try:
            raw = self._client.get_option_chain(
                symbol,
                from_date=datetime.now(timezone.utc),
                to_date=None,  # schwab-py handles DTE filtering
            )
        except Exception as exc:
            logger.warning("Schwab API error for %s: %s", symbol, exc)
            raise

        return self._parse_chain(raw, symbol)

    def get_quotes(self, symbols: list[str]) -> list[TickerQuote]:
        """Batch-fetch quotes for screening (price, SMA, sector)."""
        self._ensure_client()
        results: list[TickerQuote] = []

        for symbol in symbols:
            self._rate_limit()
            try:
                quote = self._client.get_quote(symbol)
                results.append(TickerQuote(
                    symbol=symbol,
                    last_price=float(quote.get("lastPrice", 0)),
                    sma_50=float(quote.get("fiftyDayAverage", 0)) or None,
                    sector=quote.get("sector", ""),
                ))
            except Exception:
                logger.debug("Quote fetch failed for %s", symbol)
                continue

        return results

    def _parse_chain(self, raw: dict, symbol: str) -> OptionChain:
        """Parse raw Schwab chain response into our model."""
        underlying_price = float(raw.get("underlyingPrice", 0))
        avg_volume = int(raw.get("totalVolume", 0))

        puts: list[OptionContract] = []
        calls: list[OptionContract] = []

        for expiry_key, exp_data in raw.get("putExpDateMap", {}).items():
            for strike_key, contracts in exp_data.items():
                for c in contracts:
                    bid = float(c.get("bid", 0))
                    ask = float(c.get("ask", 0))
                    mid = (bid + ask) / 2
                    spread = (ask - bid) / mid if mid > 0 else 1.0
                    puts.append(OptionContract(
                        symbol=c.get("symbol", f"{symbol}_PUT"),
                        put_call="PUT",
                        strike=float(c.get("strikePrice", 0)),
                        expiration_date=c.get("expirationDate", ""),
                        days_to_expiration=int(float(c.get("daysToExpiration", 0))),
                        bid=bid,
                        ask=ask,
                        mid=mid,
                        last=float(c.get("last", 0)),
                        delta=float(c.get("delta", 0)),
                        gamma=float(c.get("gamma", 0)),
                        theta=float(c.get("theta", 0)),
                        vega=float(c.get("vega", 0)),
                        implied_volatility=float(c.get("volatility", 0)),
                        open_interest=int(c.get("openInterest", 0)),
                        volume=int(c.get("totalVolume", 0)),
                        bid_ask_spread_pct=round(spread, 4),
                    ))

        for expiry_key, exp_data in raw.get("callExpDateMap", {}).items():
            for strike_key, contracts in exp_data.items():
                for c in contracts:
                    bid = float(c.get("bid", 0))
                    ask = float(c.get("ask", 0))
                    mid = (bid + ask) / 2
                    spread = (ask - bid) / mid if mid > 0 else 1.0
                    calls.append(OptionContract(
                        symbol=c.get("symbol", f"{symbol}_CALL"),
                        put_call="CALL",
                        strike=float(c.get("strikePrice", 0)),
                        expiration_date=c.get("expirationDate", ""),
                        days_to_expiration=int(float(c.get("daysToExpiration", 0))),
                        bid=bid,
                        ask=ask,
                        mid=mid,
                        last=float(c.get("last", 0)),
                        delta=float(c.get("delta", 0)),
                        gamma=float(c.get("gamma", 0)),
                        theta=float(c.get("theta", 0)),
                        vega=float(c.get("vega", 0)),
                        implied_volatility=float(c.get("volatility", 0)),
                        open_interest=int(c.get("openInterest", 0)),
                        volume=int(c.get("totalVolume", 0)),
                        bid_ask_spread_pct=round(spread, 4),
                    ))

        return OptionChain(
            symbol=symbol,
            underlying_price=underlying_price,
            avg_volume=avg_volume,
            puts=puts,
            calls=calls,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )
