"""Pydantic models for Schwab options data."""

from pydantic import BaseModel


class OptionContract(BaseModel):
    """A single option contract from Schwab's chain."""
    symbol: str               # e.g. "AAPL_062626P210"
    put_call: str             # "PUT" or "CALL"
    strike: float
    expiration_date: str      # "2026-06-26"
    days_to_expiration: int
    bid: float
    ask: float
    mid: float                # (bid + ask) / 2
    last: float
    delta: float
    gamma: float
    theta: float
    vega: float
    implied_volatility: float
    open_interest: int
    volume: int
    bid_ask_spread_pct: float  # (ask - bid) / mid


class OptionChain(BaseModel):
    """Complete options chain for an underlying."""
    symbol: str                # "AAPL"
    underlying_price: float
    avg_volume: int
    puts: list[OptionContract]
    calls: list[OptionContract]
    fetched_at: str            # ISO timestamp


class TickerQuote(BaseModel):
    """Simplified quote data for screening."""
    symbol: str
    last_price: float
    avg_volume: int = 0
    sma_50: float | None = None  # 50-day simple moving average
    sector: str = ""
