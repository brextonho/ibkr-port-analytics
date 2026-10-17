# RUNBOOK

Operational procedures for the IBKR portfolio analytics stack. User-facing
feature documentation lives in [USAGE.md](USAGE.md); design rationale in the
[PRD](PRD-ibkr-portfolio-analytics.md).

## 1. Services

| Service | What | How it runs |
|---|---|---|
| `postgres` | warehouse | long-running compose service |
| `ingestion` | ETL, exits when done | one-shot: `docker compose run --rm ingestion` |
| `api` | FastAPI read layer, port 8000 | long-running compose service |
| `web` | dashboard dev server, port 5173 | long-running compose service |

```bash
docker compose up -d postgres api web   # start the stack (localhost-only ports)
docker compose down                     # stop; data persists in the pgdata volume
docker compose run --rm ingestion       # trigger an ingestion run now
```

All ports bind to 127.0.0.1 by design — **there is no auth on this stack**
(PRD §11.2). Do not expose it beyond localhost without adding real auth first.

## 2. Scheduled ingestion (host cron)

The cadence lives in `config/config.yaml` under `ingestion.cron` and is
mirrored into the host crontab:

```bash
./scripts/install_cron.sh     # installs/refreshes the marked crontab entry
```

- Default: `0 21 * * FRI` (Fri 21:00 UTC ≈ after US close).
- **Switching weekly → daily**: change the key to `0 21 * * MON-FRI`, re-run
  the script. No code change (PRD §5.4).
- Logs append to `ingestion-cron.log` in the repo root.
- macOS caveats: Docker Desktop must be running at fire time, and the first
  cron execution may prompt for filesystem permission (System Settings →
  Privacy & Security → Full Disk Access → `cron`).

A missed run is not an incident: the next run's 14-day overlap window
backfills it automatically (§5.2). Ingestion is idempotent — re-running any
window is always safe.

## 3. Manual runs

```bash
# live pull (needs .env in the shell)
set -a; source .env; set +a
uv run python -m ingestion --db "$DATABASE_URL"

# offline, from a manually downloaded Flex XML — no token needed
uv run python -m ingestion --config config/config.example.yaml \
    --xml ~/Downloads/statement.xml --db sqlite:///local.db

# skip the yfinance benchmark fetch (offline / rate-limited)
uv run python -m ingestion --xml ... --db ... --no-benchmark
```

The first run against an empty database requests the full 365-day window
(the Flex ceiling); later runs request `watermark − 14d → today`.

## 4. Flex token renewal (annual — diarise it)

The token is the **only secret in the system** and lives in `.env` only.
Symptom of expiry: run fails immediately with Flex error **1012**.

1. Client Portal → Settings → Account Report → Flex Web Service →
   Generate New Token (lifespan: 1 year).
2. Update `FLEX_TOKEN` in `.env`.
3. `docker compose run --rm ingestion` to confirm, check the run email or
   `/ops/runs`.

## 5. Failure playbook

First stop: the **Ops view** in the dashboard, or `GET /ops/runs`, or the
failure email. Every run writes an `ingest_runs` row with the window, row
counts, error code, and retry history. The watermark advances **only on
success**, so a failed run never corrupts state — fix the cause and re-run.

| Symptom | Meaning | Action |
|---|---|---|
| error 1012 | token expired | renew token (§4 above) |
| error 1013 | IP restriction | token was created with an IP whitelist; regenerate without one or fix egress IP |
| error 1014 / 1015 | bad query ID / token value | check `.env` against Client Portal |
| `FlexRetryExhaustedError` (1009/1019/…) | IB busy, statement never became ready | transient — re-run later; raise `retry.attempts` if chronic |
| `UnknownFlowTypeError` | a cash-transaction type outside the whitelist | classify it in `ingestion/analytics/flows.py` (external vs internal), re-run — do NOT guess |
| TWR validation OUTSIDE tolerance in run log | computed vs IB TWR drifted | see §6 |
| API answers 503 | warehouse tables missing | run ingestion once, restart the API |
| dashboard empty, API up | no rows in window | check `/ops/runs` watermark; widen `lookback_days` and re-run |
| flows don't tie warning in log | Σ external flows ≠ IB's deposits_withdrawals | inspect `cash_transactions` for a mis-classified type; the §7.4 whitelist is the fix point |

## 6. TWR validation drift

Every run chains computed daily returns over IB's reported window and
compares against IB's own TWR (`twr_ib`), logging the diff in bps.

- **Within a few bps**: normal (rounding, IB's internal conventions).
- **Off materially, first live pull**: flow-convention mismatch — flip
  `metrics.flow_convention` (`end_of_day` ↔ `beginning_of_day`) and re-run.
  The fixture validated `end_of_day`, but a window containing a real
  deposit/withdrawal is the demanding test.
- **Off materially, previously fine**: suspect a new cash-transaction type
  being misclassified, or a corporate action (splits are a known silent gap —
  Corporate Actions section is deferred, PRD §13).

## 7. Backup / restore

```bash
docker compose exec postgres pg_dump -U portfolio portfolio > backup.sql
cat backup.sql | docker compose exec -T postgres psql -U portfolio portfolio
```

Raw tables mirror Flex sections, so the warehouse is also reconstructible by
re-pulling windows from IB (365-day ceiling per request) plus the
user-maintained tables (`security_tags`, `position_notes`, `process_grade`) —
those exist **only** in your database and YAML files; back them up.

## 8. Known limitations (accepted in MVP, PRD §7.6/§13)

- FX-attribution currency weights cover positions only; idle non-SGD cash is
  treated as base currency → the drag is slightly understated.
- Weekly position snapshots mean stale weights between snapshots; switching
  to daily cadence tightens this automatically.
- Corporate actions (splits/spinoffs) are not ingested and can discontinue
  position history silently.
- No auth, no TLS: localhost only.
- IBKR Flex statements are capped at 365 days, so live pulls can never
  backfill more than a year. Workaround: download one XML per year from
  Client Portal and ingest each with `--xml` into SQLite or Postgres (USAGE.md
  → "Backfilling more than one year of history").
