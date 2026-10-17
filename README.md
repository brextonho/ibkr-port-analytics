# IBKR Portfolio Analytics

Personal portfolio analytics on a live Interactive Brokers account, built as a
production-shaped analytics system: scheduled ETL → PostgreSQL warehouse →
read-only FastAPI → React dashboard. Base currency is SGD, and measuring the
SGD FX drag honestly is a first-class requirement.

- **[USAGE.md](USAGE.md)** — app guide: pulling data from IBKR, the dashboard views, annotations.
- **[RUNBOOK.md](RUNBOOK.md)** — operations: scheduling, token renewal, failure playbook.
- **[PRD-ibkr-portfolio-analytics.md](PRD-ibkr-portfolio-analytics.md)** — the full design.

## Status

All 14 build-order steps (PRD §15) are implemented: ingestion (models,
parser, transforms, idempotent loader, watermark, Flex client with
classified retry), the analytics layer (TWR validated against IB's own
reported TWR, risk metrics, log-space FX attribution, exposures, trade
journal, SGD-converted VWRA benchmark), YAML enrichment seeding, the FastAPI
read layer, the React dashboard, host-cron scheduling
(`scripts/install_cron.sh`), and the docs. The one remaining manual step is
yours: create the Flex query + token in IBKR Client Portal (USAGE.md) and
run the first real pull.

## Layout

| Path | What |
|---|---|
| `ingestion/` | Python ETL service: Flex fetch → parse → transform → analytics → upsert |
| `api/` | Thin read-only FastAPI over the marts (no pandas, no computation) |
| `web/` | Vite + React + TS dashboard (chart.js, grid.js), `/api` proxied to FastAPI |
| `config/` | YAML config (`config.example.yaml` → copy to gitignored `config.yaml`) |
| `tests/` | pytest suite driven by a censored real Flex XML fixture |
| `docker-compose.yml` | Postgres 16 + one-shot ingestion + api + web |

## Development

Requires [uv](https://docs.astral.sh/uv/) (manages Python 3.12 and deps).

```bash
uv sync                 # create venv, install workspace
uv run pytest           # run the suite (offline, fixture-driven)

# offline ingest of a local Flex XML into SQLite — no token needed
uv run python -m ingestion --config config/config.example.yaml \
    --xml tests/fixtures/test_data.xml --db sqlite:///local.db

# serve the API over that database, then the dashboard
DATABASE_URL=sqlite:///local.db uv run uvicorn api.main:create_app --factory
cd web && npm install && npm run dev   # http://localhost:5173
```

Live runs need `.env` (copy `.env.example`) with a Flex token and query ID
(PRD §3.2), and Postgres up: `docker compose up -d postgres`.

## Secrets

The Flex token is the only secret in the system. It is injected via
environment variables referenced from YAML (`${FLEX_TOKEN}`), never committed.
`.env` and `config/config.yaml` are gitignored.
