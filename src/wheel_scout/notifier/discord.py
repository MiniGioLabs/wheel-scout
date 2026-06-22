"""Discord webhook notifier for scan results."""

from __future__ import annotations

import logging

import httpx

from ..config import settings
from ..scanner.models import Candidate, ScanResult

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Sends formatted wheel strategy candidates to a Discord channel."""

    def __init__(self) -> None:
        self._webhook_url = settings.DISCORD_WEBHOOK_URL

    @property
    def configured(self) -> bool:
        return bool(self._webhook_url)

    def format_candidates(self, result: ScanResult) -> str:
        """Format a ScanResult into a Discord Markdown message."""
        if not result.candidates:
            return (
                f"🔍 **Wheel Scout — No candidates today**\n"
                f"Scanned {result.total_scanned} symbols across 3 tiers.\n"
                f"T1 passed: {result.passed_tier1} | "
                f"T2 passed: {result.passed_tier2} | "
                f"T3 passed: {result.passed_tier3}\n"
                f"Try widening DTE range or lowering min return threshold."
            )

        medals = ["🥇", "🥈", "🥉"]
        lines = [
            f"🔍 **Wheel Scout — {self._today_label()}**",
            f"*{settings.DTE_MIN}–{settings.DTE_MAX} DTE Cash-Secured Puts*",
            "▔" * 28,
        ]

        for i, c in enumerate(result.candidates):
            medal = medals[i] if i < 3 else f"{i+1}."
            # Format expiration date nicely (e.g., "Thu Jul 24")
            exp_label = self._format_expiry(c.expiration_date)
            lines.append(
                f"{medal} **{c.symbol}** — Sell {exp_label} ${c.strike:.0f} Put"
            )
            lines.append(
                f"   Premium: ${c.premium:.2f}/contract | "
                f"Ann.Ret: {c.annualized_return_pct:.1f}% | "
                f"Δ: {c.delta:.2f}"
            )
            lines.append(
                f"   Spread: ${c.bid:.2f}–${c.ask:.2f} | "
                f"Underlying: ${c.underlying_price:.2f} | "
                f"OI: {c.open_interest:,}"
            )

        lines.append("▔" * 28)
        lines.append(
            f"⏱ Scanned {result.total_scanned} tickers • "
            f"T1: {result.passed_tier1} → "
            f"T2: {result.passed_tier2} → "
            f"T3: {result.passed_tier3} → "
            f"**{len(result.candidates)} candidates**"
        )

        return "\n".join(lines)

    async def send(self, message: str) -> bool:
        """Send a message to the configured Discord webhook.

        Returns True on success, False on failure.
        """
        if not self.configured:
            logger.warning("Discord webhook not configured — skipping send")
            return False

        payload = {"content": message}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(self._webhook_url, json=payload)
                resp.raise_for_status()
                logger.info("Discord notification sent (%d chars)", len(message))
                return True
        except Exception as exc:
            logger.error("Discord send failed: %s", exc)
            return False

    @staticmethod
    def _today_label() -> str:
        from datetime import datetime
        return datetime.now().strftime("%a %b %d, %Y")

    @staticmethod
    def _format_expiry(iso_date: str) -> str:
        """Convert ISO date to readable format: '2026-07-17' → 'Thu Jul 17'."""
        try:
            from datetime import datetime
            dt = datetime.strptime(iso_date[:10], "%Y-%m-%d")
            return dt.strftime("%a %b %d")
        except (ValueError, IndexError):
            return iso_date
