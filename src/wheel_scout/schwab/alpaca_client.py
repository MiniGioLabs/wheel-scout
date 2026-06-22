"""Alpaca Markets client for options chains and quotes.

Uses alpaca-py's OptionHistoricalDataClient and StockHistoricalDataClient.
Returns the same OptionChain/OptionContract/TickerQuote models as Schwab.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone

from alpaca.data import OptionChainRequest, StockLatestQuoteRequest
from alpaca.data.historical import (
    OptionHistoricalDataClient,
    StockHistoricalDataClient,
)

from .models import OptionChain, OptionContract, TickerQuote
from ..config import settings

logger = logging.getLogger(__name__)

# Option symbol format: AAPL260717P00292500
# = ticker + YYMMDD + P/C + strike*1000 (8 digits, zero-padded)
_SYM_RE = re.compile(r"^([A-Z]+)(\d{6})([PC])(\d{8})$")


class AlpacaClient:
    """Wraps alpaca-py for options chain and quote data."""

    def __init__(self) -> None:
        self._option_client: OptionHistoricalDataClient | None = None
        self._stock_client: StockHistoricalDataClient | None = None

    @property
    def configured(self) -> bool:
        return settings.alpaca_configured

    def _ensure_clients(self) -> None:
        if self._option_client is not None:
            return
        self._option_client = OptionHistoricalDataClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
        )
        self._stock_client = StockHistoricalDataClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
        )
        logger.info("Alpaca client initialized (paper=%s)", settings.ALPACA_PAPER)

    def get_option_chain(
        self,
        symbol: str,
        dte_min: int | None = None,
        dte_max: int | None = None,
    ) -> OptionChain:
        """Fetch put options chain for a symbol within DTE range."""
        self._ensure_clients()
        dte_min = dte_min or settings.DTE_MIN
        dte_max = dte_max or settings.DTE_MAX

        today = date.today()
        from_date = today + timedelta(days=dte_min)
        to_date = today + timedelta(days=dte_max)

        # Get stock quote for underlying price
        try:
            quote_req = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
            quotes = self._stock_client.get_stock_latest_quote(quote_req)
            quote_obj = quotes.get(symbol)
            underlying_price = float(quote_obj.ask_price or 0) if quote_obj else 0.0
        except Exception:
            underlying_price = 0.0

        # Fetch options chain
        try:
            chain_req = OptionChainRequest(
                underlying_symbol=symbol,
                expiration_date_gte=from_date,
                expiration_date_lte=to_date,
                type="put",
                limit=200,
            )
            raw = self._option_client.get_option_chain(chain_req)
        except Exception as exc:
            logger.warning("Alpaca options chain error for %s: %s", symbol, exc)
            return OptionChain(
                symbol=symbol, underlying_price=underlying_price,
                avg_volume=0, puts=[], calls=[],
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )

        # Parse the dict response (keyed by option symbol → OptionsSnapshot objects)
        puts: list[OptionContract] = []
        if isinstance(raw, dict):
            for opt_symbol, snap in raw.items():
                if not hasattr(snap, "symbol"):
                    continue

                m = _SYM_RE.match(opt_symbol or "")
                if not m:
                    continue

                tkr, yymmdd, pc, strike_str = m.groups()
                if pc != "P":
                    continue

                strike = float(strike_str) / 1000.0
                try:
                    exp_date = datetime.strptime(yymmdd, "%y%m%d").date()
                except ValueError:
                    continue
                dte_val = (exp_date - today).days

                # Greeks (may be None for illiquid strikes)
                gr = snap.greeks
                delta_val = float(gr.delta or 0) if gr else 0.0
                gamma_val = float(gr.gamma or 0) if gr else 0.0
                theta_val = float(gr.theta or 0) if gr else 0.0
                vega_val = float(gr.vega or 0) if gr else 0.0

                # Quote
                q = snap.latest_quote
                bid_val = float(q.bid_price or 0) if q else 0.0
                ask_val = float(q.ask_price or 0) if q else 0.0
                mid_val = (bid_val + ask_val) / 2 if bid_val + ask_val > 0 else 0.0
                spread_val = (ask_val - bid_val) / mid_val if mid_val > 0 else 1.0

                # IV
                iv_val = float(snap.implied_volatility or 0)

                # OI (via snapshot, approximate)
                oi_val = 0  # v2: use get_option_snapshot for OI

                puts.append(OptionContract(
                    symbol=opt_symbol,
                    put_call="PUT",
                    strike=strike,
                    expiration_date=exp_date.isoformat(),
                    days_to_expiration=dte_val,
                    bid=round(bid_val, 2),
                    ask=round(ask_val, 2),
                    mid=round(mid_val, 2),
                    last=0.0,
                    delta=delta_val,
                    gamma=gamma_val,
                    theta=theta_val,
                    vega=vega_val,
                    implied_volatility=iv_val,
                    open_interest=oi_val,
                    volume=0,
                    bid_ask_spread_pct=round(spread_val, 4),
                ))

        return OptionChain(
            symbol=symbol,
            underlying_price=underlying_price,
            avg_volume=0,
            puts=puts,
            calls=[],
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def get_quotes(self, symbols: list[str]) -> list[TickerQuote]:
        """Batch-fetch stock quotes for screening."""
        self._ensure_clients()
        try:
            req = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes = self._stock_client.get_stock_latest_quote(req)
        except Exception as exc:
            logger.warning("Quote batch failed: %s", exc)
            return []

        results: list[TickerQuote] = []
        for sym in symbols:
            q = quotes.get(sym)
            if q:
                results.append(TickerQuote(
                    symbol=sym,
                    last_price=float(q.ask_price or 0),
                    avg_volume=0,
                    sma_50=None,
                    sector="",
                ))
        return results
