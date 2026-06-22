"""Alpaca Markets client for options chains and quotes.

Mirrors the Schwab client interface so the scanner engine is provider-agnostic.
Uses alpaca-py for clean async access. Paper trading by default.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from alpaca.data import OptionChainRequest, StockLatestQuoteRequest
from alpaca.data.live import StockDataStream
from alpaca.trading.client import TradingClient

from .models import OptionChain, OptionContract, TickerQuote
from ..config import settings

logger = logging.getLogger(__name__)


class AlpacaClient:
    """Wraps alpaca-py for options chain and quote data.

    Requires ALPACA_API_KEY and ALPACA_SECRET_KEY in environment.
    Uses paper trading endpoint by default (ALPACA_PAPER=true).
    """

    def __init__(self) -> None:
        self._trade_client: TradingClient | None = None
        self._option_client = None  # OptionDataClient

    @property
    def configured(self) -> bool:
        return settings.alpaca_configured

    def _ensure_clients(self) -> None:
        """Lazy-init Alpaca clients."""
        if self._trade_client is not None:
            return

        from alpaca.data.option import OptionDataClient

        base_url = (
            "https://paper-api.alpaca.markets"
            if settings.ALPACA_PAPER
            else "https://api.alpaca.markets"
        )

        self._trade_client = TradingClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
            paper=settings.ALPACA_PAPER,
        )
        self._option_client = OptionDataClient(
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

        today = datetime.now(timezone.utc).date()
        from_date = today + timedelta(days=dte_min)
        to_date = today + timedelta(days=dte_max)

        # Get latest quote for underlying price
        try:
            quote_req = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
            quotes = self._option_client.get_stock_latest_quote(quote_req)
            underlying_price = float(quotes.get(symbol, type("q", (), {"ask_price": 0})()).ask_price or 0)
        except Exception:
            underlying_price = 0.0

        # Fetch options contracts
        try:
            chain_req = OptionChainRequest(
                underlying_symbol=symbol,
                expiration_date_gte=from_date,
                expiration_date_lte=to_date,
                type="put",
                limit=120,  # reasonable cap per chain
            )
            contracts = self._option_client.get_option_chain(chain_req)
        except Exception as exc:
            logger.warning("Alpaca options chain error for %s: %s", symbol, exc)
            return OptionChain(
                symbol=symbol,
                underlying_price=underlying_price,
                avg_volume=0,
                puts=[],
                calls=[],
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )

        # Get snapshots for Greeks
        snapshot_symbols = [c.symbol for c in contracts if hasattr(c, "symbol")]
        snapshots = {}
        if snapshot_symbols:
            try:
                from alpaca.data import OptionSnapshotRequest
                snap_req = OptionSnapshotRequest(symbol_or_symbols=snapshot_symbols[:50])
                snaps = self._option_client.get_option_snapshots(snap_req)
                snapshots = {s.symbol: s for s in snaps if hasattr(s, "symbol")}
            except Exception:
                pass

        puts: list[OptionContract] = []
        for c in contracts:
            sym = getattr(c, "symbol", f"{symbol}_PUT")
            snap = snapshots.get(sym)

            strike = float(getattr(c, "strike_price", 0))
            exp_str = str(getattr(c, "expiration_date", ""))
            dte = (datetime.fromisoformat(exp_str).date() - today).days if exp_str else 0

            bid = float(snap.bid_price) if snap and snap.bid_price else 0.0
            ask = float(snap.ask_price) if snap and snap.ask_price else 0.0
            mid = (bid + ask) / 2 if bid + ask > 0 else 0.0
            spread = (ask - bid) / mid if mid > 0 else 1.0

            puts.append(OptionContract(
                symbol=sym,
                put_call="PUT",
                strike=strike,
                expiration_date=exp_str,
                days_to_expiration=dte,
                bid=round(bid, 2),
                ask=round(ask, 2),
                mid=round(mid, 2),
                last=float(snap.last_price) if snap and snap.last_price else 0.0,
                delta=float(snap.greeks.delta) if snap and snap.greeks and snap.greeks.delta else 0.0,
                gamma=float(snap.greeks.gamma) if snap and snap.greeks and snap.greeks.gamma else 0.0,
                theta=float(snap.greeks.theta) if snap and snap.greeks and snap.greeks.theta else 0.0,
                vega=float(snap.greeks.vega) if snap and snap.greeks and snap.greeks.vega else 0.0,
                implied_volatility=float(snap.implied_volatility) if snap and snap.implied_volatility else 0.0,
                open_interest=int(snap.open_interest) if snap and snap.open_interest else 0,
                volume=int(snap.volume) if snap and snap.volume else 0,
                bid_ask_spread_pct=round(spread, 4),
            ))

        return OptionChain(
            symbol=symbol,
            underlying_price=underlying_price,
            avg_volume=0,  # Alpaca doesn't provide this directly
            puts=puts,
            calls=[],  # We only care about puts for wheel strategy
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def get_quotes(self, symbols: list[str]) -> list[TickerQuote]:
        """Batch-fetch quotes for screening (price, SMA)."""
        self._ensure_clients()

        try:
            req = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes = self._option_client.get_stock_latest_quote(req)
        except Exception as exc:
            logger.warning("Quote batch failed: %s", exc)
            return []

        results: list[TickerQuote] = []
        for symbol in symbols:
            q = quotes.get(symbol)
            if q:
                results.append(TickerQuote(
                    symbol=symbol,
                    last_price=float(q.ask_price or 0),
                    avg_volume=0,  # Not in snapshot; use separate call if needed
                    sma_50=None,   # Not provided by Alpaca snapshot
                    sector="",
                ))

        return results
