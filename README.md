# Wheel Scout 🛞

Daily options wheel strategy scanner — screens Schwab options chains, ranks cash-secured put candidates, and pushes results to Discord.

**Gio Mini Labs** — [github.com/GioMiniLabs/wheel-scout](https://github.com/GioMiniLabs/wheel-scout)

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
│  Schwab API      │  Options chains + quotes
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

The wheel strategy sells cash-secured puts on quality stocks, collects premium, and if assigned, sells covered calls at cost basis. Screening is everything.

| Tier | Filter | Rule |
|------|--------|------|
| 🚫 **T1** | Underlying price | $10–$200 |
| 🚫 **T1** | Open interest | ≥ 100 |
| 🚫 **T1** | Avg daily volume | ≥ 500K |
| 🚫 **T1** | Bid-ask spread | ≤ 5% of mid |
| 🚫 **T1** | DTE window | 21–35 days |
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
- Schwab developer account (free)
- Discord webhook URL

### 1. Clone & install

```bash
git clone https://github.com/GioMiniLabs/wheel-scout.git
cd wheel-scout
uv sync
```

### 2. Configure

```bash
cp .env.example .env
```

Fill in:

```env
SCHWAB_APP_KEY=your_schwab_app_key
SCHWAB_SECRET=your_schwab_secret
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/.../...
```

Get Schwab keys at [developer.schwab.com](https://developer.schwab.com).
Create a Discord webhook: Channel Settings → Integrations → Webhooks → New Webhook.

### 3. Run

```bash
uv run uvicorn wheel_scout.main:app --host 0.0.0.0 --port 8000
```

On first run, Schwab OAuth opens a browser for authentication. A `schwab_token.json` file is saved for subsequent runs.

### 4. Verify

```bash
# Health check
curl http://localhost:8000/health

# Trigger a manual scan
curl http://localhost:8000/scan
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Status, config check (Schwab + Discord) |
| GET | `/scan` | Trigger an on-demand scan — returns `ScanResult` |

## Configuration

All settings are in `.env` (or environment variables):

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHWAB_APP_KEY` | — | Schwab API app key |
| `SCHWAB_SECRET` | — | Schwab API secret |
| `DISCORD_WEBHOOK_URL` | — | Discord webhook for notifications |
| `DTE_MIN` | 21 | Minimum days to expiration |
| `DTE_MAX` | 35 | Maximum days to expiration |
| `MIN_ANNUALIZED_RETURN` | 15 | Min annualized return % |
| `MIN_PREMIUM` | 0.30 | Min premium per contract ($) |
| `MIN_DELTA` | 0.20 | Minimum delta (absolute) |
| `MAX_DELTA` | 0.30 | Maximum delta (absolute) |
| `SCAN_SCHEDULE_CRON` | `0 8 * * 1-5` | Cron expression (Mon-Fri 8 AM ET) |
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
├── config.py            # Pydantic Settings
├── schwab/              # Schwab API client
│   ├── client.py        # OAuth auth, chain + quote fetcher
│   └── models.py        # OptionContract, OptionChain, TickerQuote
├── scanner/             # Screening pipeline
│   ├── filters.py       # 8 deterministic filter functions
│   ├── engine.py        # 3-tier funnel orchestrator
│   ├── models.py        # Candidate + ScanResult
│   └── universe.py      # 147-ticker default list
├── earnings/            # Nasdaq earnings calendar (free, no API key)
│   └── client.py        # Async fetcher + in-memory cache
└── notifier/            # Discord output
    └── discord.py        # Webhook sender + markdown formatter
```

## License

MIT — Gio Mini Labs
