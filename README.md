# Wheel Scout 🛞

Daily options wheel strategy scanner — screens Alpaca options chains, ranks cash-secured put candidates, and pushes results to Discord.

**MiniGioLabs** — [github.com/MiniGioLabs/wheel-scout](https://github.com/MiniGioLabs/wheel-scout)

## How It Works

```
Mon-Fri 8:00 AM ET
       │
       ▼
┌─────────────────┐
│  S&P 500 + ETFs │  147 liquid tickers
└────────┬────────┘
         ▼
┌─────────────────┐
│  Alpaca API      │  Options chains + quotes + Greeks
└────────┬────────┘
         ▼
┌─────────────────┐
│  Tier 1: Hard    │  Price, spread, OI, volume, DTE
│  Tier 2: Profit  │  Ann. return ≥ 15%, Δ 0.20–0.30, premium ≥ $0.30
│  Tier 3: Quality │  Above 50-SMA, no biotech, no earnings in window
└────────┬────────┘
         ▼
┌─────────────────┐
│  Ranked Results  │  Sorted by annualized return → Discord
└─────────────────┘
```

## Screening Methodology

| Tier | Filter | Rule |
|------|--------|------|
| 🚫 **T1** | Underlying price | $10–$500 |
| 🚫 **T1** | Open interest | ≥ 100 (skip if unavailable) |
| 🚫 **T1** | Avg daily volume | ≥ 500K (skip if unavailable) |
| 🚫 **T1** | Bid-ask spread | ≤ 5% of mid |
| 🚫 **T1** | DTE window | 14–42 days (2–6 weeks) |
| 💰 **T2** | Annualized return | ≥ 15% `(premium/strike) × (365/DTE)` |
| 💰 **T2** | Put delta | 0.20–0.30 |
| 💰 **T2** | Min premium | ≥ $0.30/contract |
| 📅 **Earnings** | Upcoming earnings | ❌ Reject if in DTE window (Nasdaq API) |
| 🛡️ **T3** | Trend | Above 50-day SMA |
| 🛡️ **T3** | Sector | No biotech/pharma |

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (or pip)
- Alpaca Markets account (free paper trading)

### 1. Clone & install

```bash
git clone https://github.com/MiniGioLabs/wheel-scout.git
cd wheel-scout
uv sync
```

### 2. Get Alpaca API keys

1. Sign up at [app.alpaca.markets](https://app.alpaca.markets)
2. Switch to **Paper Trading** (left sidebar)
3. Generate API keys — copy Key ID + Secret Key

### 3. Create Discord webhook

Discord → Channel Settings → Integrations → Webhooks → New Webhook → Copy URL

### 4. Configure

```bash
cp .env.example .env
```

Fill in:

```env
ALPACA_API_KEY=your_key_id
ALPACA_SECRET_KEY=your_secret_key
ALPACA_PAPER=true
DISCORD_WEBHOOK_URL=your_webhook_url
```

### 5. Run

```bash
uv run uvicorn wheel_scout.main:app --host 0.0.0.0 --port 8000
```

### 6. Verify

```bash
# Health check
curl http://localhost:8000/health

# Trigger a manual scan
curl http://localhost:8000/scan
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Status, provider + Discord config check |
| GET | `/scan` | Trigger on-demand scan — returns `ScanResult` |

## Configuration

All settings via `.env` (or environment variables):

| Variable | Default | Description |
|----------|---------|-------------|
| `ALPACA_API_KEY` | — | Alpaca API key ID |
| `ALPACA_SECRET_KEY` | — | Alpaca API secret |
| `ALPACA_PAPER` | true | Use paper trading endpoint |
| `DISCORD_WEBHOOK_URL` | — | Discord webhook for notifications |
| `DTE_MIN` | 14 | Minimum days to expiration |
| `DTE_MAX` | 42 | Maximum days to expiration |
| `MIN_ANNUALIZED_RETURN` | 15 | Min annualized return % |
| `MIN_PREMIUM` | 0.30 | Min premium per contract ($) |
| `MIN_DELTA` | 0.20 | Minimum delta (absolute) |
| `MAX_DELTA` | 0.30 | Maximum delta (absolute) |
| `CANDIDATE_LIMIT` | 10 | Max results in Discord message |

## Docker

```bash
docker compose up -d
```

Daily scans run automatically. Manual scan:

```bash
curl http://localhost:8000/scan
```

## Project Structure

```
src/wheel_scout/
├── main.py              # FastAPI app + APScheduler
├── config.py            # Pydantic Settings (Alpaca + Discord)
├── schwab/              # Provider clients
│   ├── client.py        # Schwab client (OAuth fallback)
│   ├── alpaca_client.py # Alpaca client (instant setup)
│   └── models.py        # OptionContract, OptionChain, TickerQuote
├── scanner/             # Screening pipeline
│   ├── filters.py       # 8 deterministic filter functions
│   ├── engine.py        # 3-tier funnel orchestrator (provider-agnostic)
│   ├── models.py        # Candidate + ScanResult
│   └── universe.py      # 147-ticker default list
├── earnings/            # Nasdaq earnings calendar (free, no API key)
│   └── client.py        # Async fetcher + in-memory cache
└── notifier/            # Discord output
    └── discord.py        # Webhook sender + markdown formatter
```

## Discord Output

```
🔍 Wheel Scout — Mon Jun 22, 2026
*2–6 Week Cash-Secured Puts*
▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔
🥇 INTC — Sell Thu Jul 17 $126 Put
   Premium: $7.01/contract | Ann.Ret: 81.2% | Δ: 0.29
   Spread: $6.90–$7.12 | Underlying: $126.45 | OI: 0
🥈 INTC — Sell Thu Jul 17 $125 Put
   Premium: $6.61/contract | Ann.Ret: 77.2% | Δ: 0.29
   ...
```
