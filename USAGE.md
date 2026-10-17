# App Guide

How to use the IBKR portfolio analytics app: getting your data in, reading
each dashboard view, and annotating your portfolio. Operational procedures
(cron, token renewal, failure recovery) live in [RUNBOOK.md](RUNBOOK.md).

## What this app is

A personal analytics system over your real Interactive Brokers account. A
scheduled ETL job pulls statements from IBKR's Flex Web Service, computes
portfolio analytics (time-weighted return, risk, FX attribution, exposures,
trade stats), and stores everything in a local database. A dashboard reads
the results. Base currency is **SGD**, and separating market performance from
the SGD FX drag is a headline feature.

Numbers you should trust, and why: the computed TWR is validated against
IB's own reported TWR on every run (the "TWR validation" line in the run
output), dividends are never mistaken for deposits (a classic TWR bug,
guarded by tests), and the benchmark (VWRA) is converted to SGD with the same
FX rates as your portfolio, so the comparison is honest.

## Quick start test (no IBKR credentials needed)

Uses the bundled sample statement so you can see every screen working:

```bash
uv run python -m ingestion --config config/config.example.yaml \
    --xml tests/fixtures/test_data.xml --db sqlite:///local.db

# terminal 1 — API
DATABASE_URL=sqlite:///demo.db uv run uvicorn api.main:create_app --factory

# terminal 2 — dashboard
cd web && npm run dev
```

Open **http://localhost:5173**. (API docs: http://localhost:8000/docs.)

## Getting your real data

### One-time setup in IBKR Client Portal

Two things are needed: a **Flex query** (what data to include) and a
**token** (permission to fetch it over HTTP).

**A. Create the Flex query** — Performance & Reports → Flex Queries →
Custom Flex Queries → Create. Configure per PRD §4; the load-bearing
settings:

| Setting | Value |
|---|---|
| Format | XML |
| Date format | `yyyy-MM-dd` (ibflex rejects European formats) |
| Period | Last 365 Calendar Days (fallback; the app overrides per request) |
| Profit and Loss | Base Currency P&L |
| Include Currency Rates | Yes |
| **Breakout by Day** | **Yes — critical, this is what makes NAV daily** |

Sections to tick (six): **Net Asset Value (NAV) in Base** (uncheck "exclude
prior report date", check "exclude long/short breakout"), **Open Positions**
(⚠️ choose **Summary**, not Lot), **Trades** (⚠️ choose **Execution** only —
do **not** tick the `Symbol Summary` / `Asset Class` / `Order` options at the
top of the section, they break the parser), **Cash Transactions** (Dividends,
Deposits/Withdrawals, Withholding Tax, Broker Interest Received/Paid, Other
Fees), **Financial Instrument Information**, **Change in NAV** (Realized &
Unrealized). Field lists per PRD §4.3–4.8 — over-selecting fields is safe;
the three Trades top-options above are the only real trap.

Note the **Query ID** (info icon next to the saved query).

**B. Generate the token** — Settings → Account Report → Flex Web Service →
Generate New Token. Choose the 1-year lifespan and put a renewal reminder in
your calendar. Leave IP restriction blank for local use.

**C. Wire them up locally:**

```bash
cp .env.example .env                          # fill FLEX_TOKEN, FLEX_QUERY_ID, IBKR_ACCOUNT_ID
cp config/config.example.yaml config/config.yaml
cp config/position_notes.example.yaml config/position_notes.yaml
cp config/security_tags.example.yaml config/security_tags.yaml
```

### Pulling data — three ways

**1. Live pull (the normal path).** Fetches directly from IBKR:

```bash
set -a; source .env; set +a     # export the secrets into your shell
uv run python -m ingestion --db sqlite:///local.db
```

The **first run backfills up to 365 days** of daily NAV — a full year of
charts immediately. Later runs fetch only `watermark − 14 days → yesterday`;
the overlap makes missed runs self-heal. Every window ends at the **last
completed day, never today** — IB has no statement for a day still in
progress and rejects such a request with fatal error 1003 ("Statement is not
available"). Statement data updates once daily at IB's close of business, so
there is never a reason to pull more than once a day.

**2. Manual XML download (no token needed).** In Client Portal:
Performance & Reports → Flex Queries → ▶ Run next to your query → format XML
→ download. Then:

```bash
uv run python -m ingestion --config config/config.example.yaml \
    --xml ~/Downloads/MyStatement.xml --db sqlite:///local.db
```

Choose the date range in the run dialog — a full-year range gives the same
backfill as a live pull. This is also the fallback whenever the Flex service
is having a bad day.

**3. Scheduled (set and forget).** `./scripts/install_cron.sh` installs a
weekly Friday-night run via docker compose — see RUNBOOK §2.

**After ingesting, restart the API** if it was already running (it discovers
the warehouse tables at startup), then refresh the browser.

Re-running any pull is always safe: every write is an idempotent upsert on a
natural key. Overlapping windows never duplicate rows.

### Backfilling more than one year of history

IBKR caps every Flex statement at 365 days, so neither a live pull nor a
single manual download can reach further back than a year. To load a longer
history, run the query manually once per year (or shorter) window, download
each XML, and ingest them all.

Put the files under `data/xml/` (any path works, since `--xml` takes a path;
`data/` is gitignored so your statements stay out of git). `--xml` takes one
file per run, so loop over them from the project root. Delete `local.db` first
so the test fixture data doesn't mix with yours:

```bash
cd ~/Developer/personal/ibkr-port-analytics
rm local.db
for f in data/xml/*.xml; do
  uv run python -m ingestion --config config/config.yaml --xml "$f" \
      --db sqlite:///local.db || break
done
```

- **Order and overlaps don't matter.** Every write is an upsert on a natural
  key, and each run recomputes TWR, risk and the other derived tables over the
  full history in the database. The watermark ends up at the latest date
  across all files.
- **Live pulls afterwards** (`uv run python -m ingestion --db
  sqlite:///local.db`) continue from that watermark with the usual 14-day
  overlap.
- **Restart the API** after ingesting, from the project root.

**Into Postgres instead:** the Docker ingestion container only mounts
`./config`, not your XML folder, so it can't see the files without adding a
volume to `docker-compose.yml`. The simpler route is to run the same loop on
the host while `docker compose up postgres` is running, swapping the `--db`
argument for
`--db postgresql+psycopg://portfolio:portfolio@localhost:5432/portfolio`.

### Postgres instead of SQLite

SQLite is fine for kicking the tires; the compose stack uses Postgres:

```bash
docker compose up -d postgres api web
uv run python -m ingestion \
    --db postgresql+psycopg://portfolio:portfolio@localhost:5432/portfolio
# (or: docker compose run --rm ingestion, which uses .env)
```

## The dashboard, view by view

**Overview** — the headline. Stat cards (cumulative and annualized TWR,
excess return vs VWRA, current NAV), the NAV curve, cumulative TWR vs the
SGD-converted benchmark, and the drawdown (underwater) chart. The period
picker (1M…ALL) rescopes the charts. Hover for a crosshair; click-drag across
a chart to measure the span (NAV change split into net flows vs market, or
portfolio vs VWRA return over just that window). Click or Esc clears it.
TWR strips out your deposits/withdrawals, so this is investment performance,
not cash-flow growth — a deposit will move the NAV chart but not the TWR.

**Statistics** — exposures: where the money is, by asset class, currency,
or geography (sector and theme light up once you tag securities — see
below). Doughnut + table, from the latest snapshot. Asset-class comes from
IB's NAV components; currency and geography from position values in SGD.
Below that, a risk table: rolling volatility, Sharpe, Sortino, max drawdown.

**FX** — the SGD drag made visible: each bar is a day, split by currency,
measured in basis points of NAV. Negative bars = SGD strength cost you money
that day. Needs at least two days of FX-rate history, so it's empty until
your second ingested day (a year-long backfill has plenty).

**Positions** — the current book on one page, with search and sort: value in SGD, % of
NAV, unrealized P&L, geography, plus your thesis and sellable date where
you've added them.

**Journal** — closed trades with the process-quality stats: hit rate,
slugging ratio (average win ÷ average loss), and average holding period of
winners vs losers — the classic retail failure is cutting winners and
holding losers, and this measures whether you're doing it.

**Ops** — is the pipeline healthy: recent runs, status, windows, watermark,
durations, retry counts, error messages.

Dark mode follows your OS setting automatically.

## Annotating your portfolio

The qualitative layer lives in user-maintained tables that ingestion never
overwrites with IB data. Two ways to write it:

**YAML files (durable, versionable)** — edit `config/security_tags.yaml`
and/or `config/position_notes.yaml`, keyed by conid (find conids in the
Positions API output or IB statements):

```yaml
# config/security_tags.yaml
"375855577":            # VWRA
  theme: core-beta
"131081685":            # Metaplanet
  theme: crypto
  geography: JP
```

```yaml
# config/position_notes.yaml
"4391":                 # AMD
  thesis: "AI accelerator share gains; datacenter capex cycle."
  target_price: 250
  sellable_date: 2027-01-15
```

They're upserted on every ingestion run. `theme` immediately enables the
theme dimension in Statistics → Exposures; `geography` overrides the listing country.
Fields you omit for a conid are cleared on the next run — the file is the
source of truth for the conids it mentions.

**API (quick edits)** — via http://localhost:8000/docs (interactive) or curl:

```bash
curl -X PUT localhost:8000/positions/4391/notes \
  -H 'Content-Type: application/json' \
  -d '{"thesis": "AI accelerator share gains.", "target_price": 250}'

curl -X PUT localhost:8000/trades/{trade_id}/grade \
  -H 'Content-Type: application/json' \
  -d '{"process_grade": "A — thesis played out, sized right"}'
```

Trade grades are the point of the journal: grade the *process*, not the
outcome. A well-reasoned loser can be an A; a lucky winner with no thesis is
the leak. Don't maintain the same conid in both YAML and API — the YAML wins
on the next run.

## Email notifications

Get a run summary (window, rows, duration, TWR validation) after every
scheduled run — most valuable on failure. In `config/config.yaml`:

```yaml
notifications:
  enabled: true
  backend: smtp
  to: "you@example.com"
```

with `SMTP_USER` / `SMTP_PASSWORD` in `.env` (for Gmail: an app password). A
broken mail server never fails an ingestion run.

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| Nothing at localhost:5173 | the dashboard is its own process: `cd web && npm run dev` |
| API `GET /` shows docs, endpoints 503 | warehouse empty — ingest once, restart the API |
| Charts show two points only | you've only ingested the sample fixture — do a real pull with a wide date range |
| FX view empty | needs ≥ 2 days of FX rates — fills from your second ingested day |
| Benchmark line missing | yfinance fetch skipped/failed, or no FX rate coverage for those dates — re-run without `--no-benchmark` |
| Journal empty | no *closed* trades in the ingested window yet |
| sector/theme exposures empty | expected until you populate `config/security_tags.yaml` |
| Run fails instantly with code 1012 | token expired — RUNBOOK §4 |
| `UnknownFlowTypeError` | a new cash-transaction type needs classifying — RUNBOOK §5 |

## Running the tests

```bash
uv run pytest
```

90 tests, all offline against the bundled fixture — including the TWR
worked example (a deposit is not a 30% return) and the oracle test that
matches computed TWR against IB's own number.
