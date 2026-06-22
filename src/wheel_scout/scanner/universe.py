"""Ticker universe — the list of stocks to scan daily.

v1: Curated static list of S&P 500 + liquid ETFs.
v2: Can fetch the full optionable list from Schwab.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default universe: S&P 500 stocks + liquid ETFs
_DEFAULT_TICKERS: list[str] = [
    # Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "INTC",
    "CRM", "ADBE", "ORCL", "CSCO", "IBM", "QCOM", "TXN", "AVGO", "NOW",
    "INTU", "AMAT", "LRCX", "MU", "ADI", "PANW", "SNPS", "CDNS", "ANET",
    "PLTR", "CRWD", "DDOG", "NET", "ZS", "OKTA", "SNOW", "MDB",
    # Financials
    "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SCHW", "AXP", "V",
    "MA", "PYPL", "COF", "USB", "PNC", "TFC", "BK",
    # Healthcare (non-biotech only — no 2833-2836)
    "UNH", "JNJ", "ABBV", "MRK", "LLY", "TMO", "DHR", "ABT", "ISRG",
    "SYK", "BSX", "CI", "HUM", "ELV", "CVS", "HCA",
    # Consumer
    "AMZN", "WMT", "COST", "HD", "LOW", "TGT", "MCD", "SBUX", "NKE",
    "DIS", "CMCSA", "NFLX", "ABNB", "BKNG", "MAR", "HLT", "UBER",
    # Industrials
    "CAT", "DE", "GE", "HON", "UPS", "BA", "LMT", "RTX", "GD", "NOC",
    "UNP", "CSX", "NSC", "FDX",
    # Energy
    "XOM", "CVX", "COP", "EOG", "SLB", "PSX", "VLO", "MPC", "OXY",
    "KMI", "WMB",
    # Materials / Real Estate / Utilities
    "LIN", "APD", "ECL", "SHW", "PLD", "AMT", "CCI", "EQIX", "SPG",
    "O", "NEE", "DUK", "SO", "D", "AEP", "SRE",
    # Liquid ETFs
    "SPY", "QQQ", "IWM", "DIA", "XLF", "XLE", "XLK", "XLV", "XLI",
    "XLP", "XLU", "XLB", "XLY", "XLRE", "XLC", "EEM", "EFA", "TLT",
    "GLD", "SLV", "USO",
]


def load_tickers(path: str | None = None) -> list[str]:
    """Load the ticker universe from a file or use defaults.

    File format: one symbol per line, # comments allowed.
    Falls back to the hardcoded S&P 500 + ETF default list.
    """
    if path:
        file_path = Path(path)
    else:
        file_path = Path("tickers.txt")

    if file_path.exists():
        tickers: list[str] = []
        with open(file_path) as f:
            for line in f:
                line = line.strip().upper()
                if line and not line.startswith("#"):
                    tickers.append(line)
        logger.info("Loaded %d tickers from %s", len(tickers), file_path)
        return tickers

    logger.info("Using default universe: %d tickers", len(_DEFAULT_TICKERS))
    return list(_DEFAULT_TICKERS)
