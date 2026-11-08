# Operations

Running the app day to day, fixing what goes wrong, and keeping your data safe.
For first-time setup, see [SETUP.md](SETUP.md).

## Day to day

```bash
uv run portfolio serve        # dashboard at http://localhost:8000
uv run portfolio ingest       # pull now, instead of waiting for the schedule
```

The **Ops** tab, and the status in the top bar, show when data was last loaded
and whether the last pull failed. You can leave the dashboard running during a
pull; refresh the page afterwards.

Each pull asks IBKR for everything from 14 days before the last loaded date up
to yesterday. A failed pull doesn't move that date, so the next one retries the
same days. Every pull's XML is saved in `data/xml/live_<from>_<to>.xml`.

## Schedule

```bash
./scripts/install_schedule.sh            # install, or update after moving the project
./scripts/install_schedule.sh --remove   # stop scheduled pulls
launchctl kickstart gui/$UID/com.ibkr-portfolio.ingest   # run the scheduled pull now
tail -n 50 ingest.log                    # see recent pull output
```

## Renew the token (yearly)

A pull that fails straight away with error **1012** means the token has
expired.

1. Client Portal → **Settings → Account Report → Flex Web Service** → **Generate New Token**.
2. Replace `FLEX_TOKEN` in `.env`.
3. Run `uv run portfolio ingest` and check the Ops tab.

## When a pull fails

The Ops tab shows the error. Common ones:

| Error | What it means | What to do |
|---|---|---|
| `1012` | Token expired | Renew it (above) |
| `1013` | Token is limited to other IP addresses | Generate a token with no IP restriction |
| `1014`, `1015` | Query ID or token is wrong | Compare `.env` with Client Portal |
| `1003` | The statement isn't available yet | Pull later; never ask for today's date |
| `1019`, `FlexRetryExhaustedError` | IBKR was busy and the statement never became ready | Try again later |
| `StatementNotReadyError` | IBKR hadn't finished its P&L run | Pull later; scheduled pulls run in the evening for this reason |
| `IncompleteSectionError` | A Flex section is missing required fields | The message names the fields; tick them in the query (SETUP.md, step 2) |
| `BaseCurrencyChangedError` | The statement's base currency differs from the one already in the database | One database holds one base currency. Load it into a new one (`--db`), or rebuild (below) with every statement in the new currency |
| `ConfigError` | `config/config.yaml` or `.env` has a problem | The message names the setting |

The Overview's return figures come from IBKR's own daily return (the **TWR**
field). If the log warns that some dates "have no IB daily TWR", tick that
field in the query's Change in NAV section and pull again.

## Load a saved or downloaded statement

```bash
uv run portfolio ingest --xml data/xml/live_20261001_20261015.xml
```

Loading the same dates again is always safe: rows are stored once and updated
in place.

## Back up and restore

Everything lives in `portfolio.db`: IBKR data, which can be pulled again, and
your labels and notes, which can't.

```bash
sqlite3 portfolio.db ".backup 'backup-$(date +%F).db'"   # safe while the app runs
cp backup-2026-10-17.db portfolio.db                     # restore, with the app stopped
```

`portfolio.db-wal` and `portfolio.db-shm` sit next to the database while it's
open. They're SQLite's working files; don't delete them while the app runs.

To rebuild from scratch, which loses your labels and notes unless you keep a
backup:

```bash
rm portfolio.db*
uv run portfolio ingest --xml data/xml/*.xml
```

## Known limits

- The FX breakdown weights currencies by holdings only. Cash in a foreign
  currency is left out, so the exchange-rate effect is slightly understated.
- There's no login: the dashboard listens on localhost only. Don't expose it
  to a network.

## Development

```bash
uv run pytest                              # Python tests, against the demo data in SGD and USD
npm --prefix web run dev                   # live-reloading dashboard on :5173 (keep `serve` running)
npm --prefix web run build                 # rebuild what `serve` hands out
uv run python scripts/make_demo_xml.py     # regenerate the demo data
```
