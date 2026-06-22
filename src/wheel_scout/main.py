"""Wheel Scout — main FastAPI application.

Provides health endpoint and triggers daily options scans via APScheduler.
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Singletons ─────────────────────────────────────────────────────

schwab: SchwabClient | None = None
engine: ScreenEngine | None = None
notifier = DiscordNotifier()

# Resolve timezone safely — fall back to UTC if tzdata not installed
try:
    import zoneinfo
    _tz = zoneinfo.ZoneInfo(settings.SCAN_TIMEZONE)
except Exception:
    logging.warning(
        "Timezone '%s' not available — falling back to UTC. "
        "Install tzdata: uv add tzdata",
        settings.SCAN_TIMEZONE,
    )
    _tz = "UTC"

scheduler = AsyncIOScheduler(timezone=_tz)


def _init_components() -> None:
    """Lazy-init Schwab client and scan engine."""
    global schwab, engine
    if schwab is None:
        schwab = SchwabClient()
        engine = ScreenEngine(schwab)
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

    # Always notify — even empty results are informative
    message = notifier.format_candidates(result)
    await notifier.send(message)

    return result


# ── FastAPI app ────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start scheduler on app startup, shut down gracefully."""
    _init_components()

    # Schedule the daily scan job
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
    """Extract hour, minute from a 5-field cron expression."""
    parts = cron_expr.strip().split()
    if len(parts) >= 2:
        return int(parts[1]), int(parts[0])  # minute, hour
    return 8, 0  # default: 8:00 AM


app = FastAPI(
    title="Wheel Scout",
    description="Daily options wheel strategy scanner for Schwab.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "schwab_configured": settings.schwab_configured,
        "discord_configured": settings.discord_configured,
        "dte_window": f"{settings.DTE_MIN}–{settings.DTE_MAX}",
    }


@app.get("/scan", response_model=ScanResult)
async def manual_scan() -> ScanResult:
    """Trigger a scan manually (on-demand)."""
    return await _run_daily_scan()
