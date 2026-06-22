"""Free earnings calendar client using Nasdaq API.

No API key required. Fetches earnings dates for the DTE window and
provides fast lookups to filter out stocks with upcoming earnings.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

NASDAQ_EARNINGS_URL = "https://api.nasdaq.com/api/calendar/earnings"


class EarningsCache:
    """Caches earnings dates for a rolling DTE window.

    Nasdaq API returns one day at a time, so we fetch each day in
    the window. Results are stored as {symbol: {date_str, ...}}.
    """

    def __init__(self) -> None:
        self._earnings: dict[str, set[str]] = {}  # symbol → {dates}
        self._loaded_range: tuple[int, int] = (0, 0)

    async def refresh(self, dte_min: int, dte_max: int) -> None:
        """Fetch earnings data for the DTE window.

        Skips fetch if the same window is already loaded.
        """
        if self._loaded_range == (dte_min, dte_max) and self._earnings:
            logger.debug("Earnings cache hit for DTE %d–%d", dte_min, dte_max)
            return

        today = datetime.now(timezone.utc).date()
        dates = [
            (today + timedelta(days=d)).strftime("%Y-%m-%d")
            for d in range(dte_min, dte_max + 1)
        ]

        self._earnings.clear()
        async with httpx.AsyncClient(timeout=30) as client:
            tasks = [self._fetch_date(client, d) for d in dates]
            await asyncio.gather(*tasks)

        self._loaded_range = (dte_min, dte_max)
        total = sum(len(v) for v in self._earnings.values())
        logger.info("Earnings cache loaded: %d symbols across %d days", total, len(dates))

    async def _fetch_date(self, client: httpx.AsyncClient, date_str: str) -> None:
        """Fetch earnings for a single date from Nasdaq."""
        try:
            resp = await client.get(
                NASDAQ_EARNINGS_URL,
                params={"date": date_str},
                headers={"User-Agent": "WheelScout/1.0", "Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.debug("Nasdaq earnings fetch failed for %s: %s", date_str, exc)
            return

        rows = data.get("data", {}).get("rows") or []
        for row in rows:
            symbol = (row.get("symbol") or "").strip().upper()
            if symbol:
                self._earnings.setdefault(symbol, set()).add(date_str)

    def has_earnings_in_window(self, symbol: str, dte: int) -> bool:
        """Check if a symbol has earnings within the given DTE days.

        Returns True if earnings are scheduled — meaning the contract
        should be REJECTED.
        """
        if not self._earnings:
            return False  # No data — pass through (don't reject)

        today = datetime.now(timezone.utc).date()
        window_dates = {
            (today + timedelta(days=d)).strftime("%Y-%m-%d")
            for d in range(dte + 1)
        }
        symbol_dates = self._earnings.get(symbol.upper(), set())
        return bool(symbol_dates & window_dates)
