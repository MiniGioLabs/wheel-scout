"""Wheel Scout — main FastAPI application.

Provides health endpoint and triggers daily options scans via APScheduler.
Supports Schwab and Alpaca providers — auto-detects based on configured keys.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from .config import settings
from .notifier.discord import DiscordNotifier
from .scanner.engine import ScreenEngine
from .scanner.models import ScanResult
from .scanner.universe import load_tickers
from .schwab.client import SchwabClient
from .schwab.alpaca_client import AlpacaClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Singletons ─────────────────────────────────────────────────────

_client = None  # SchwabClient or AlpacaClient
engine: ScreenEngine | None = None
notifier = DiscordNotifier()

# Resolve timezone safely
try:
    import zoneinfo
    _tz = zoneinfo.ZoneInfo(settings.SCAN_TIMEZONE)
except Exception:
    _tz = "UTC"

scheduler = AsyncIOScheduler(timezone=_tz)


def _init_components() -> None:
    """Lazy-init the best available provider (Alpaca > Schwab)."""
    global _client, engine
    if _client is not None:
        return
    if settings.alpaca_configured:
        _client = AlpacaClient()
        logger.info("Using Alpaca Markets")
    elif settings.schwab_configured:
        _client = SchwabClient()
        logger.info("Using Schwab")
    else:
        logger.warning("No provider configured — set ALPACA_API_KEY or SCHWAB_APP_KEY")
        _client = None
        return
    engine = ScreenEngine(_client)
    logger.info("Components initialized")


# ── Scan job ───────────────────────────────────────────────────────


async def _run_daily_scan() -> ScanResult:
    """Fetch tickers, scan chains, notify Discord."""
    _init_components()

    symbols = load_tickers()
    if not symbols:
        logger.warning("No tickers loaded — scan aborted")
        return ScanResult(
            timestamp="", total_scanned=0,
            passed_tier1=0, passed_tier2=0, passed_tier3=0,
            candidates=[],
        )

    try:
        result = await engine.run(symbols)
    except Exception as exc:
        logger.exception("Scan failed: %s", exc)
        result = ScanResult(
            timestamp="", total_scanned=len(symbols),
            passed_tier1=0, passed_tier2=0, passed_tier3=0,
            candidates=[],
            errors=[str(exc)],
        )

    message = notifier.format_candidates(result)
    await notifier.send(message)

    return result


# ── FastAPI app ────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start scheduler on app startup, shut down gracefully."""
    _init_components()

    hour, minute = _parse_cron(settings.SCAN_SCHEDULE_CRON)
    scheduler.add_job(
        _run_daily_scan,
        "cron",
        day_of_week="mon-fri",
        hour=hour,
        minute=minute,
        id="daily_scan",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started — daily scan at %02d:%02d ET (Mon–Fri)",
        hour, minute,
    )

    yield

    scheduler.shutdown(wait=False)
    logger.info("Scheduler shut down")


def _parse_cron(cron_expr: str) -> tuple[int, int]:
    parts = cron_expr.strip().split()
    if len(parts) >= 2:
        return int(parts[1]), int(parts[0])
    return 8, 0


app = FastAPI(
    title="Wheel Scout",
    description="Daily options wheel strategy scanner — Schwab + Alpaca support.",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "alpaca_configured": settings.alpaca_configured,
        "schwab_configured": settings.schwab_configured,
        "discord_configured": settings.discord_configured,
        "dte_window": f"{settings.DTE_MIN}–{settings.DTE_MAX}",
    }


@app.get("/scan", response_model=ScanResult)
async def manual_scan() -> ScanResult:
    """Trigger a scan manually (on-demand)."""
    return await _run_daily_scan()
