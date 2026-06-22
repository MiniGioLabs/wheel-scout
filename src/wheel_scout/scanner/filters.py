"""Deterministic screening filters for the wheel strategy.

Each filter is a pure function: (OptionContract, context) -> bool.
All thresholds come from Settings so they can be overridden via env vars.
"""

from __future__ import annotations

from collections.abc import Callable

from ..config import settings
from ..schwab.models import OptionContract, TickerQuote

# SIC codes for biotech / pharma (2833-2836)
_BIOTECH_SIC_PREFIXES = ("2833", "2834", "2835", "2836")


# ── Tier 1: Hard Filters ──────────────────────────────────────────


def price_in_range(contract: OptionContract, quote: TickerQuote) -> bool:
    """Reject if underlying is below $10 or above $200."""
    return settings.MIN_STOCK_PRICE <= quote.last_price <= settings.MAX_STOCK_PRICE


def open_interest_min(contract: OptionContract, _quote: TickerQuote) -> bool:
    """Reject if open interest is below threshold.

    Passes if OI data is unavailable (0) — some providers don't include it
    in the chain response.
    """
    if contract.open_interest == 0:
        return True  # data unavailable, skip check
    return contract.open_interest >= settings.MIN_OPEN_INTEREST


def volume_min(_contract: OptionContract, quote: TickerQuote) -> bool:
    """Reject if average daily volume is below threshold.

    Passes if volume data is unavailable (0) — some providers don't include it.
    """
    if quote.avg_volume == 0:
        return True  # data unavailable, skip check
    return quote.avg_volume >= settings.MIN_AVG_VOLUME


def bid_ask_spread_tight(contract: OptionContract, _quote: TickerQuote) -> bool:
    """Reject if bid-ask spread exceeds threshold (illiquid contract)."""
    return contract.bid_ask_spread_pct <= settings.MAX_BID_ASK_SPREAD_PCT


def dte_in_range(contract: OptionContract, _quote: TickerQuote) -> bool:
    """Reject if DTE is outside our target window."""
    return settings.DTE_MIN <= contract.days_to_expiration <= settings.DTE_MAX


# ── Tier 2: Profitability Gates ───────────────────────────────────


def annualized_return_min(contract: OptionContract, _quote: TickerQuote) -> bool:
    """Reject if annualized return on capital is below threshold.

    Formula: (premium / strike) * (365 / DTE) * 100
    """
    if contract.strike <= 0 or contract.days_to_expiration <= 0:
        return False
    ann_ret = (contract.mid / contract.strike) * (365 / contract.days_to_expiration) * 100
    return ann_ret >= settings.MIN_ANNUALIZED_RETURN


def delta_in_range(contract: OptionContract, _quote: TickerQuote) -> bool:
    """Reject if delta is outside the 0.20–0.30 sweet spot."""
    if contract.delta == 0:
        return False
    return settings.MIN_DELTA <= abs(contract.delta) <= settings.MAX_DELTA


def premium_min(contract: OptionContract, _quote: TickerQuote) -> bool:
    """Reject if premium per contract is below the minimum."""
    return contract.mid >= settings.MIN_PREMIUM


# ── Tier 3: Quality & Safety ──────────────────────────────────────


def above_sma_50(_contract: OptionContract, quote: TickerQuote) -> bool:
    """Reject if stock is below its 50-day moving average (falling knife).

    If SMA data is unavailable, pass through (don't reject).
    """
    if quote.sma_50 is None:
        return True  # data unavailable — don't filter
    return quote.last_price >= quote.sma_50


def no_earnings_in_window(contract: OptionContract, _quote: TickerQuote) -> bool:
    """Reject if earnings are scheduled within the DTE window.

    This requires the earnings cache to be populated before screening.
    The filter is applied by the engine, not as a standalone function.
    In v1, this is handled via the Nasdaq earnings calendar.
    """
    # This is checked by the engine against the earnings cache
    return True


def no_biotech(_contract: OptionContract, quote: TickerQuote) -> bool:
    """Reject biotech/pharma stocks (SIC codes 2833-2836)."""
    sector = quote.sector.lower() if quote.sector else ""
    biotech_keywords = ("biotech", "biotechnology", "pharma", "pharmaceutical")
    return not any(kw in sector for kw in biotech_keywords)


# ── Filter registry ────────────────────────────────────────────────

# Ordered tiers — each is a list of (name, function) pairs
TIER1_FILTERS: list[tuple[str, Callable]] = [
    ("price_in_range", price_in_range),
    ("open_interest_min", open_interest_min),
    ("volume_min", volume_min),
    ("bid_ask_spread_tight", bid_ask_spread_tight),
    ("dte_in_range", dte_in_range),
]

TIER2_FILTERS: list[tuple[str, Callable]] = [
    ("annualized_return_min", annualized_return_min),
    ("delta_in_range", delta_in_range),
    ("premium_min", premium_min),
]

TIER3_FILTERS: list[tuple[str, Callable]] = [
    ("above_sma_50", above_sma_50),
    ("no_biotech", no_biotech),
]
