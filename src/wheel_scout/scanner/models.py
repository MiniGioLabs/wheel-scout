"""Pydantic models for scanner results."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Candidate(BaseModel):
    """A wheel strategy candidate that passed all screening filters."""
    symbol: str
    put_call: str = "PUT"
    strike: float
    expiration_date: str
    days_to_expiration: int = Field(alias="dte")
    premium: float               # mid price
    delta: float
    implied_volatility: float
    open_interest: int
    bid: float
    ask: float
    spread_pct: float
    underlying_price: float
    annualized_return_pct: float

    # Quality signals
    above_sma_50: bool = True
    avg_volume: int = 0

    class Config:
        populate_by_name = True


class ScanResult(BaseModel):
    """The output of a complete scan run."""
    timestamp: str
    total_scanned: int
    passed_tier1: int
    passed_tier2: int
    passed_tier3: int
    candidates: list[Candidate]   # ranked by annualized return
    errors: list[str] = Field(default_factory=list)
