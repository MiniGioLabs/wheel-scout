"""3-tier screening engine for wheel strategy candidates.

Funnel architecture:
    Symbols → Tier 1 (hard) → Tier 2 (profit) → Tier 3 (quality) → Ranked Results
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from . import filters
from .models import Candidate, ScanResult
from ..config import settings
from ..schwab.client import SchwabClient
from ..schwab.models import OptionContract, TickerQuote
from ..earnings.client import EarningsCache

logger = logging.getLogger(__name__)


class ScreenEngine:
    """Runs the 3-tier deterministic screening pipeline."""

    def __init__(self, schwab: SchwabClient) -> None:
        self._schwab = schwab
        self._earnings = EarningsCache()

    async def run(self, symbols: list[str]) -> ScanResult:
        """Scan a universe of symbols and return ranked wheel candidates.

        Args:
            symbols: List of ticker symbols to scan (e.g., S&P 500).

        Returns:
            ScanResult with ranked candidates passing all three tiers.
        """
        start = datetime.now(timezone.utc)
        logger.info("Starting scan of %d symbols", len(symbols))

        # Preload earnings data for the DTE window
        await self._earnings.refresh(
            dte_min=settings.DTE_MIN,
            dte_max=settings.DTE_MAX,
        )

        errors: list[str] = []
        passed_t1 = 0
        passed_t2 = 0
        passed_t3 = 0
        candidates: list[Candidate] = []

        for symbol in symbols:
            try:
                chain = self._schwab.get_option_chain(symbol)
                quote = self._fetch_quote(symbol)
            except Exception as exc:
                logger.debug("Skipping %s: %s", symbol, exc)
                continue

            for contract in chain.puts:
                # Tier 1 — hard filters
                if not self._apply_tier(filters.TIER1_FILTERS, symbol, contract, quote):
                    continue
                passed_t1 += 1

                # Tier 2 — profitability gates
                if not self._apply_tier(filters.TIER2_FILTERS, symbol, contract, quote):
                    continue
                passed_t2 += 1

                # Earnings check (runs between T2 and T3)
                if self._earnings.has_earnings_in_window(
                    symbol, contract.days_to_expiration
                ):
                    continue

                # Tier 3 — quality & safety
                if not self._apply_tier(filters.TIER3_FILTERS, symbol, contract, quote):
                    continue
                passed_t3 += 1

                # All filters passed — build candidate
                ann_ret = ((contract.mid / contract.strike)
                           * (365 / contract.days_to_expiration) * 100)

                candidates.append(Candidate(
                    symbol=symbol,
                    put_call="PUT",
                    strike=contract.strike,
                    expiration_date=contract.expiration_date,
                    dte=contract.days_to_expiration,
                    premium=round(contract.mid, 2),
                    delta=abs(contract.delta),
                    implied_volatility=round(contract.implied_volatility, 4),
                    open_interest=contract.open_interest,
                    bid=contract.bid,
                    ask=contract.ask,
                    spread_pct=contract.bid_ask_spread_pct,
                    underlying_price=quote.last_price,
                    annualized_return_pct=round(ann_ret, 2),
                    above_sma_50=(
                        quote.sma_50 is not None
                        and quote.last_price >= quote.sma_50
                    ),
                    avg_volume=quote.avg_volume,
                ))

        # Rank by annualized return (highest first)
        candidates.sort(key=lambda c: c.annualized_return_pct, reverse=True)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info(
            "Scan complete: %d scanned → T1:%d T2:%d T3:%d → %d candidates (%.1fs)",
            len(symbols), passed_t1, passed_t2, passed_t3, len(candidates), elapsed,
        )

        return ScanResult(
            timestamp=start.isoformat(),
            total_scanned=len(symbols),
            passed_tier1=passed_t1,
            passed_tier2=passed_t2,
            passed_tier3=passed_t3,
            candidates=candidates[:settings.CANDIDATE_LIMIT],
            errors=errors,
        )

    def _apply_tier(
        self,
        tier: list[tuple[str, callable]],
        symbol: str,
        contract: OptionContract,
        quote: TickerQuote,
    ) -> bool:
        """Run all filters in a tier. All must pass."""
        for name, check in tier:
            if not check(contract, quote):
                logger.debug("%s: %s FAILED %s", symbol, contract.strike, name)
                return False
        return True

    def _fetch_quote(self, symbol: str) -> TickerQuote:
        """Fetch quote with fallback to empty/default values."""
        quotes = self._schwab.get_quotes([symbol])
        if quotes:
            return quotes[0]
        return TickerQuote(symbol=symbol, last_price=0.0)
